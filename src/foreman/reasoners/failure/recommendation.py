# ============================================================
#  FOREMAN — reasoners/failure/recommendation.py
#  Zweck: Orchestrierung der LLM-Werker-Empfehlung (F-REC) — der Erklär-Layer über
#         F-PRED und zweiter Konsument des LLM-Gateways. Pipeline (wie F6):
#         Grounding-Quellen sammeln (Vorhersage+SHAP trusted, NEXUS-Recall untrusted)
#         → gateway.complete(task=explanation) → numerischer Post-Check (Invariante I)
#         → Negativ-Guard (Invariante II) → deterministischer Vorbehalt → Persistenz
#         + Dual-Write.
#  Architektur-Einordnung: Reasoning-Schicht (F-REC). KEINE Aktorik — die Empfehlung
#         erklärt, sie schaltet nichts. On-demand (kein Auto-LLM, §14.3). Reasoner
#         importiert NUR `foreman.llm` (kein LiteLLM-Typ).
#  ZWEI INVARIANTEN (verbindlich):
#    (I)  Zahlen autoritativ vom Modell — F-REC wertet das Grounding SELBST aus
#         (fail-closed: eigener `check_grounding`, unabhängig von der global
#         abschaltbaren Gateway-Option `grounding_enabled`; der strict-Modus-
#         `GroundingViolation` wird gleichwertig behandelt). Führt der Empfehlungstext
#         eine unbelegte Zahl ein → HARTER Reject (NumericGroundingError), keine
#         Persistenz (§13.3).
#    (II) Der Sim-Vorbehalt ist deterministisch — `validation_caveat` kommt aus
#         `validation_caveat_for(...)`, nicht aus dem LLM. Zusätzlich rejectet ein
#         Negativ-Guard jede Umdeutung des Sim-Charakters im (sanitisierten) LLM-Text.
# ============================================================
from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from time import perf_counter
from typing import NoReturn

from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import FailurePredictionRecord, FailureRecommendationRecord, Machine
from foreman.ingestion.semantic import record_semantic_event
from foreman.llm import GroundingViolation, LLMGateway, Task, check_grounding
from foreman.logging_setup import ERROR, REASON, get_logger
from foreman.observability.metrics import (
    observe_failure_recommendation,
    observe_reasoner_run,
    record_failure_recommendation_recall,
)
from foreman.reasoners.failure.grounding import allowed_source_ids, build_recommendation_sources
from foreman.reasoners.failure.prompts import (
    RECOMMENDATION_SYSTEM_PROMPT,
    build_recommendation_user_prompt,
)
from foreman.reasoners.failure.recall import build_runup_query, recall_similar_runups
from foreman.reasoners.failure.schema import (
    FailurePredictionRead,
    WorkerRecommendation,
    validation_caveat_for,
)
from foreman.substrate.client import SubstrateClient

logger = get_logger("foreman.reasoners.failure.recommendation")

REASONER_NAME = "failure_recommendation"
RECOMMENDATION_EVENT_TYPE = "failure_recommendation"

# Zitat-Muster: source_ids der Form pred:42 / factor:vibration_rms / recall:0
# (alphanumerisches Suffix mit Unterstrich — Faktor-Namen sind technische Tags).
_CITATION_RE = re.compile(r"\[([a-z_]+:[a-z0-9_]+)\]")
# Output-Smuggling-Abwehr (LLM05): Markdown-Links/-Bilder → sichtbarer Text,
# HTML-Tags entfernen, gefährliche/rohe URLs (inkl. javascript:/data:) neutralisieren.
_MD_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_TAG_RE = re.compile(r"<[^>]+>")
_URL_RE = re.compile(r"(?:https?|ftp|data|javascript|vbscript):[^\s]*", re.IGNORECASE)

# Phrasen, die den simulationsbasierten Charakter ins Gegenteil verkehren würden
# (Negativ-Guard, Invariante II). Treffer OHNE Verneinung davor → Reject.
_OVERCLAIM_PHRASES = (
    "validierte prognose",
    "validierter prognose",
    "gesicherte prognose",
    "gesicherter prognose",
    "reale prognose",
    "garantierter ausfall",
    "garantiert ausfallen",
    "verlässliche vorhersage",
    "an realen ausfällen validiert",
    "real validiert",
)
_NEGATIONS = ("nicht", "keine", "kein", "ohne")


class PredictionNotFoundError(LookupError):
    """Die referenzierte Vorhersage existiert nicht (→ 404 in der Route)."""

    def __init__(self, prediction_id: int) -> None:
        super().__init__(f"Vorhersage {prediction_id} nicht gefunden.")
        self.prediction_id = prediction_id


class NumericGroundingError(ValueError):
    """Die Empfehlung führte eine unbelegte Zahl ein (Invariante I) → verworfen."""

    def __init__(self, unbacked: tuple[str, ...]) -> None:
        super().__init__(f"❌ Empfehlung verworfen: unbelegte Zahl(en) {list(unbacked)}.")
        self.unbacked = unbacked


class RecommendationOverclaimError(ValueError):
    """Die Empfehlung deutete den Sim-Vorbehalt um (Invariante II) → verworfen."""

    def __init__(self, phrase: str) -> None:
        super().__init__(f"❌ Empfehlung verworfen: Umdeutung des Sim-Vorbehalts ('{phrase}').")
        self.phrase = phrase


def extract_citations(text: str) -> list[str]:
    """Findet alle [source_id]-Zitate (eindeutig, in Reihenfolge)."""
    seen: list[str] = []
    for match in _CITATION_RE.finditer(text):
        source_id = match.group(1)
        if source_id not in seen:
            seen.append(source_id)
    return seen


def sanitize_recommendation(text: str) -> str:
    """Neutralisiert HTML/Markdown-Links/rohe URLs (Output-Smuggling, LLM05).

    [source_id]-Zitate bleiben erhalten (sie haben keine `(...)`-Klammer).
    """
    cleaned = _MD_LINK_RE.sub(r"\1", text)
    cleaned = _TAG_RE.sub("", cleaned)
    cleaned = _URL_RE.sub("[link entfernt]", cleaned)
    return cleaned.strip()


def detect_overclaim(text: str) -> str | None:
    """Findet eine Phrase, die den Sim-Vorbehalt umdeutet — ohne Verneinung davor.

    Negativ-Guard (Invariante II): eine Übertreibungs-Phrase (z. B. „validierte
    Prognose") gilt nur als Umdeutung, wenn ihr kein Verneinungswort unmittelbar
    vorausgeht („nicht validierte Prognose" ist erlaubt). Die eigentliche Garantie
    kommt strukturell aus `validation_caveat` — dieser Guard ist die Zusatz-Schicht.
    """
    lowered = text.lower()
    for phrase in _OVERCLAIM_PHRASES:
        start = lowered.find(phrase)
        while start != -1:
            prefix = lowered[max(0, start - 20) : start]
            if not any(negation in prefix for negation in _NEGATIONS):
                return phrase
            start = lowered.find(phrase, start + 1)
    return None


def build_recommendation(
    *, prediction: FailurePredictionRead, narrative: str, allowed: tuple[str, ...]
) -> WorkerRecommendation:
    """Output-Guard: baut die VALIDIERTE WorkerRecommendation aus dem bereits
    sanitisierten Empfehlungstext.

    `narrative` ist der FINALE, output-sanitisierte Text — derselbe, den die Guards
    (numerischer Post-Check + Negativ-Guard) geprüft haben (kein Post-Sanitize-Schlupf,
    Invariante II). Zitierte Quellen werden gegen die Whitelist (`allowed`) geprüft: nur
    gültige → `referenced_source_ids`; erfundene Zitate werden verworfen (nie zitiert).
    Der Sim-Vorbehalt ist deterministisch (`validation_caveat_for`), die Zahlen stammen
    aus der Vorhersage.
    """
    allowed_set = set(allowed)
    referenced = tuple(c for c in extract_citations(narrative) if c in allowed_set)
    return WorkerRecommendation(
        prediction_id=prediction.id,
        machine_id=prediction.machine_id,
        recommendation_text=narrative,
        validation_caveat=validation_caveat_for(prediction.validation_status),
        validation_status=prediction.validation_status,
        data_regime=prediction.data_regime,
        model_version=prediction.model_version,
        referenced_source_ids=referenced,
        allowed_source_ids=allowed,
        horizon_h=prediction.horizon_h,
        probability=prediction.probability,
        decision=prediction.decision,
    )


@dataclass
class RecommendationService:
    """DB-Anbindung des Werker-Empfehlungs-Reasoners (F-REC).

    Reine Logik (Recall/Grounding/Prompt/Guards) liegt in den Nachbar-Modulen; diese
    Klasse ist die IO-Schale (Session + Gateway + optional Substrat). On-demand, keine
    Aktorik. `substrate=None` → Empfehlung ohne historischen Kontext (best-effort).
    """

    session: AsyncSession
    gateway: LLMGateway
    substrate: SubstrateClient | None = None
    recall_max_results: int = 5

    async def recommend(self, prediction_id: int) -> FailureRecommendationRecord:
        """Erzeugt on-demand eine Werker-Empfehlung zu einer Vorhersage und persistiert sie.

        Wirft `PredictionNotFoundError` (fehlende Vorhersage), `NumericGroundingError`
        (unbelegte Zahl, Invariante I) oder `RecommendationOverclaimError` (Umdeutung
        des Vorbehalts, Invariante II). In allen Reject-Fällen wird NICHTS persistiert.
        """
        t0 = perf_counter()
        try:
            record = await self._run(prediction_id)
        except PredictionNotFoundError:
            observe_reasoner_run(REASONER_NAME, perf_counter() - t0, success=False)
            raise
        except (NumericGroundingError, RecommendationOverclaimError):
            # Reject ist ein gewollter Schutz-Ausgang (Invariante I/II), kein Crash —
            # aber als nicht-erfolgreicher Lauf gezählt (die Empfehlung wurde verworfen).
            observe_reasoner_run(REASONER_NAME, perf_counter() - t0, success=False)
            raise
        except Exception:
            observe_reasoner_run(REASONER_NAME, perf_counter() - t0, success=False)
            logger.exception(
                "%s Werker-Empfehlung fehlgeschlagen prediction_id=%s", ERROR, prediction_id
            )
            raise
        observe_reasoner_run(REASONER_NAME, perf_counter() - t0, success=True)
        return record

    @staticmethod
    def _reject_numeric(data_regime: str, prediction_id: int, unbacked: Sequence[str]) -> NoReturn:
        """Invariante-I-Reject: zählt die Metrik, loggt PII-frei, wirft NumericGroundingError.

        `unbacked` nimmt sowohl den `GroundingReport.unbacked` (tuple, eigener Post-Check)
        als auch den `GroundingViolation.unbacked` (list, strict-Modus) entgegen.
        `NoReturn`: nach dem Aufruf läuft kein Code weiter (mypy weiß, dass `response`
        im GroundingViolation-Pfad nicht weiterverwendet wird).
        """
        observe_failure_recommendation(data_regime=data_regime, result="rejected_numeric")
        logger.warning(
            "%s reasoner=failure_recommendation prediction_id=%s REJECT unbelegte Zahlen=%s",
            REASON,
            prediction_id,
            len(unbacked),
        )
        raise NumericGroundingError(tuple(unbacked))

    async def _run(self, prediction_id: int) -> FailureRecommendationRecord:
        pred_record = await self.session.get(FailurePredictionRecord, prediction_id)
        if pred_record is None:
            raise PredictionNotFoundError(prediction_id)
        prediction = FailurePredictionRead.model_validate(pred_record)

        machine = await self.session.get(Machine, prediction.machine_id)
        # NEXUS-Recall ähnlicher Vorläufe (best-effort, blockiert nie).
        recall_items = await recall_similar_runups(
            self.substrate,
            build_runup_query(machine, prediction),
            max_results=self.recall_max_results,
        )
        record_failure_recommendation_recall("hit" if recall_items else "miss")

        sources = build_recommendation_sources(prediction, recall_items)
        try:
            response = await self.gateway.complete(
                task=Task.EXPLANATION,
                system_prompt=RECOMMENDATION_SYSTEM_PROMPT,
                user_prompt=build_recommendation_user_prompt(prediction),
                sources=sources,
            )
        except GroundingViolation as exc:
            # grounding_strict=True am Gateway → die unbelegte Zahl wird schon dort
            # verworfen. F-REC behandelt das als denselben Invariante-I-Reject (422 +
            # Metrik), nicht als unbehandelten 500.
            self._reject_numeric(prediction.data_regime, prediction_id, exc.unbacked)

        # Der ausgelieferte Text ist der output-sanitisierte (LLM05) — die Guards UND
        # die Persistenz sehen DENSELBEN Text (kein Post-Sanitize-Schlupf, Invariante II).
        narrative = sanitize_recommendation(response.text)

        # --- Invariante I: numerischer Post-Check, FAIL-CLOSED (§13.3) ---
        # F-REC wertet das Grounding SELBST aus (nicht response.grounding) — unabhängig
        # von der global abschaltbaren Gateway-Option `grounding_enabled`. Ein
        # Hart-Reject-Reasoner darf sich nie auf eine optionale Gateway-Policy verlassen:
        # ist der Check dort aus, prüft F-REC trotzdem (fail-closed).
        report = check_grounding(narrative, sources)
        if report.unbacked:
            self._reject_numeric(prediction.data_regime, prediction_id, report.unbacked)

        # --- Invariante II: Negativ-Guard gegen Umdeutung des Sim-Vorbehalts ---
        overclaim = detect_overclaim(narrative)
        if overclaim is not None:
            observe_failure_recommendation(
                data_regime=prediction.data_regime, result="rejected_overclaim"
            )
            logger.warning(
                "%s reasoner=failure_recommendation prediction_id=%s REJECT Umdeutung Vorbehalt",
                REASON,
                prediction_id,
            )
            raise RecommendationOverclaimError(overclaim)

        recommendation = build_recommendation(
            prediction=prediction,
            narrative=narrative,
            allowed=allowed_source_ids(sources),
        )
        record = await self._persist(recommendation)
        await self._mirror(recommendation)
        observe_failure_recommendation(data_regime=prediction.data_regime, result="issued")
        # Strukturierter Log (§11.1): Umfang/Vorbehalt, KEINE PII/kein Empfehlungstext.
        logger.info(
            "%s reasoner=failure_recommendation prediction_id=%s machine_id=%s referenced=%s "
            "validation_status=%s recall=%s",
            REASON,
            prediction_id,
            prediction.machine_id,
            len(recommendation.referenced_source_ids),
            recommendation.validation_status,
            bool(recall_items),
        )
        return record

    async def _persist(self, recommendation: WorkerRecommendation) -> FailureRecommendationRecord:
        record = FailureRecommendationRecord(
            prediction_id=recommendation.prediction_id,
            machine_id=recommendation.machine_id,
            recommendation_text=recommendation.recommendation_text,
            validation_caveat=recommendation.validation_caveat,
            validation_status=recommendation.validation_status,
            data_regime=recommendation.data_regime,
            model_version=recommendation.model_version,
            referenced_source_ids=list(recommendation.referenced_source_ids),
            horizon_h=recommendation.horizon_h,
            probability=recommendation.probability,
            decision=recommendation.decision,
        )
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def _mirror(self, recommendation: WorkerRecommendation) -> None:
        """Spiegelt die Empfehlung als diskretes semantic_event (§12.4).

        Gespiegelt wird eine STRUKTURIERTE, PII-freie Zusammenfassung mit
        `data_regime=simulation` — damit das Gedächtnis die Sim-Empfehlung nie als
        reale Prognose ablegt. NICHT der rohe Empfehlungstext. Best-effort via F3.
        """
        payload = {
            "reasoner": REASONER_NAME,
            "prediction_id": recommendation.prediction_id,
            "machine_id": recommendation.machine_id,
            "decision": recommendation.decision,
            "horizon_h": recommendation.horizon_h,
            "referenced_source_ids": list(recommendation.referenced_source_ids),
            "validation_status": recommendation.validation_status,
            # Pflicht: der Sim-Charakter wandert mit ins Gedächtnis (§16).
            "data_regime": recommendation.data_regime,
        }
        content = (
            f"Werker-Empfehlung zu Vorhersage {recommendation.prediction_id} an Maschine "
            f"{recommendation.machine_id}: Entscheidung {recommendation.decision}, Horizont "
            f"{recommendation.horizon_h} h (simulationsbasiert, nicht validiert)."
        )
        await record_semantic_event(
            self.session,
            machine_id=recommendation.machine_id,
            event_type=RECOMMENDATION_EVENT_TYPE,
            payload=payload,
            content=content,
            substrate=self.substrate,
        )
        # Der DB-Spiegel wird immer geschrieben; der Substrat-Dual-Write bleibt
        # best-effort (in record_semantic_event gekapselt).
        await self.session.flush()
