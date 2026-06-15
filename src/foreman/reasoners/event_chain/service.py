# ============================================================
#  FOREMAN — reasoners/event_chain/service.py
#  Zweck: Orchestrierung des Ereignisketten-Reasoners (F6, Baustein 5/6) —
#         Sammeln (chain) → Grounden (recall + grounding_sources) → Synthetisieren
#         (gateway.complete, task=synthesis) → Output-Guard (ReasonerExplanation)
#         → Persistieren (reasoner_explanations) + best-effort Dual-Write als
#         semantic_event ans Substrat (§12.4).
#  Architektur-Einordnung: Reasoning-Schicht (F6). Der Reasoner sieht NUR das
#         LLMGateway (kein LiteLLM). KEINE Aktorik — er erklärt, schaltet nichts.
#  Sicherheit (Schutz-Doc §5.1): Der Output-Guard ist die scharfe Numerik-/Quellen-
#         Abwehr — referenzierte Quellen MÜSSEN aus der Whitelist stammen; erfundene
#         Quellen + unbelegte Zahlen (aus dem Gateway-Grounding-Report) werden
#         geflaggt; die Erzählung wird vor Persistenz output-sanitisiert (LLM05).
#  Konvention (§6): Type Hints überall, deutsche Kommentare, keine PII/keine
#         Notiz-Texte in Logs.
# ============================================================
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from time import perf_counter

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import (
    Alarm,
    Machine,
    MaintenanceEvent,
    ReasonerExplanationRecord,
    WorkerNote,
)
from foreman.embeddings import EmbeddingProvider
from foreman.ingestion.semantic import record_semantic_event
from foreman.llm import GroundingReport, LLMGateway, Task
from foreman.logging_setup import ERROR, REASON, get_logger
from foreman.notes import embed_and_search
from foreman.observability.metrics import (
    observe_reasoner_run,
    record_event_chain_explanation,
    record_event_chain_recall,
)
from foreman.reasoners.event_chain.chain import reconstruct_chain
from foreman.reasoners.event_chain.grounding_sources import (
    allowed_source_ids,
    build_grounding_sources,
)
from foreman.reasoners.event_chain.prompts import (
    EVENT_CHAIN_SYSTEM_PROMPT,
    build_event_chain_user_prompt,
)
from foreman.reasoners.event_chain.recall import build_recall_query, recall_similar_incidents
from foreman.reasoners.event_chain.schema import (
    ChainWindow,
    Confidence,
    EventChain,
    ReasonerExplanation,
)
from foreman.substrate.client import SubstrateClient

logger = get_logger("foreman.reasoners.event_chain")

REASONER_NAME = "event_chain"
EVENT_CHAIN_EVENT_TYPE = "event_chain_reconstructed"
# Default-Rückblick ab dem Anker (Drift wirkt über Stunden bis Tage; Notizen „2
# Schichten vor Ausfall"). On-demand pro Request überschreibbar.
DEFAULT_LOOKBACK = timedelta(days=7)

# source_id-Form für die Zitat-Extraktion: <präfix>:<zahl> (alarm:12, note:3, recall:0).
# Fängt auch erfundene Quellen (evt:9999) → werden gegen die Whitelist geprüft.
_CITATION_RE = re.compile(r"\[([a-z_]+:\d+)\]")
# Output-Sanitisierung (LLM05): HTML/XML-Tags, Markdown-Links/-Bilder, rohe URLs.
_TAG_RE = re.compile(r"<[^>]*>")
_MD_LINK_RE = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
# URL-/Scheme-Neutralisierung inkl. gefährlicher Nicht-HTTP-Schemata (javascript:,
# data:, vbscript:, ftp:, file:) — nicht nur http(s). `:(?://)?\S+` deckt sowohl
# `scheme://host` als auch `scheme:payload` (z. B. javascript:alert(1)) ab.
_URL_RE = re.compile(
    r"(?:https?|ftp|file|data|javascript|vbscript):(?://)?\S+", re.IGNORECASE
)


class AnchorNotFoundError(LookupError):
    """Der referenzierte Anker-Alarm existiert nicht (→ 404 in der Route)."""

    def __init__(self, anchor_alarm_id: int) -> None:
        super().__init__(f"Anker-Alarm {anchor_alarm_id} nicht gefunden.")
        self.anchor_alarm_id = anchor_alarm_id


def extract_citations(narrative: str) -> list[str]:
    """Zieht alle [source_id]-Zitate aus der Erzählung (eindeutig, in Reihenfolge)."""
    seen: dict[str, None] = {}
    for match in _CITATION_RE.finditer(narrative):
        seen.setdefault(match.group(1), None)
    return list(seen)


def sanitize_narrative(narrative: str) -> str:
    """Neutralisiert HTML/Markdown-Links/rohe URLs (Output-Smuggling, LLM05).

    Tags werden entfernt, Markdown-Links/-Bilder auf ihren sichtbaren Text reduziert,
    rohe URLs durch einen Platzhalter ersetzt. [source_id]-Zitate bleiben erhalten
    (sie haben keine `(...)`-Klammer und sind keine Tags)."""
    cleaned = _MD_LINK_RE.sub(r"\1", narrative)
    cleaned = _TAG_RE.sub("", cleaned)
    cleaned = _URL_RE.sub("[link entfernt]", cleaned)
    return cleaned.strip()


def _confidence(
    *, referenced: tuple[str, ...], flagged: tuple[str, ...], grounding: GroundingReport | None
) -> Confidence:
    """Leitet die Konfidenz ab: geflaggt → low; belegt + gegroundet → high; sonst medium."""
    if flagged:
        return "low"
    grounded_ok = grounding is None or grounding.grounded
    if referenced and grounded_ok:
        return "high"
    return "medium"


def build_explanation(
    *,
    anchor_alarm_id: int,
    machine_id: int | None,
    narrative: str,
    allowed: tuple[str, ...],
    grounding: GroundingReport | None,
    recall_used: bool,
) -> ReasonerExplanation:
    """Output-Guard: baut das VALIDIERTE ReasonerExplanation-Objekt aus der rohen
    Gateway-Antwort.

    Zitierte Quellen werden gegen die Whitelist (`allowed`) geprüft: gültige →
    `referenced_source_ids`; erfundene → `flagged_unsupported`. Unbelegte Zahlen aus
    dem Gateway-Grounding-Report kommen ebenfalls in `flagged_unsupported`. Sind
    Inhalte geflaggt, ist die Erzählung zwingend Hypothese. Die Erzählung wird vor
    Persistenz sanitisiert.
    """
    allowed_set = set(allowed)
    citations = extract_citations(narrative)
    referenced = tuple(c for c in citations if c in allowed_set)
    invented = [c for c in citations if c not in allowed_set]
    unbacked = list(grounding.unbacked) if grounding is not None else []
    flagged = tuple(sorted(set(invented) | set(unbacked)))
    confidence = _confidence(referenced=referenced, flagged=flagged, grounding=grounding)
    return ReasonerExplanation(
        anchor_alarm_id=anchor_alarm_id,
        machine_id=machine_id,
        narrative=sanitize_narrative(narrative),
        allowed_source_ids=allowed,
        referenced_source_ids=referenced,
        flagged_unsupported=flagged,
        is_hypothesis=bool(flagged),
        confidence=confidence,
        recall_used=recall_used,
        grounding=grounding,
    )


@dataclass
class EventChainService:
    """DB-/Gateway-Anbindung des Ereignisketten-Reasoners.

    Reine Logik (Ketten-Bau, Quellen-Bau, Output-Guard) liegt in den Modulen
    chain/grounding_sources/service-Helfer; diese Klasse ist die dünne IO-Schale
    (Session, Gateway, optionales Substrat).
    """

    session: AsyncSession
    gateway: LLMGateway
    substrate: SubstrateClient | None = None
    # F-SEM (§15): optionaler Embedding-Provider für die semantische Notiz-Auswahl.
    # None → reines F6-Verhalten (nur Zeitfenster-Notizen).
    embedding_provider: EmbeddingProvider | None = None
    lookback: timedelta = DEFAULT_LOOKBACK
    recall_max_results: int = 5
    semantic_max_results: int = 5
    _last: ReasonerExplanation | None = field(default=None, init=False, repr=False)

    async def reconstruct(
        self, anchor_alarm_id: int, *, lookback: timedelta | None = None
    ) -> ReasonerExplanationRecord:
        """Rekonstruiert on-demand die Ereigniskette um einen Anker und persistiert
        die Erklärung. Wirft `AnchorNotFoundError`, wenn der Anker fehlt."""
        t0 = perf_counter()
        try:
            record = await self._run(anchor_alarm_id, lookback or self.lookback)
        except AnchorNotFoundError:
            observe_reasoner_run(REASONER_NAME, perf_counter() - t0, success=False)
            raise
        except Exception:
            observe_reasoner_run(REASONER_NAME, perf_counter() - t0, success=False)
            logger.exception(
                "%s Ereignisketten-Reasoner fehlgeschlagen anchor=%s", ERROR, anchor_alarm_id
            )
            raise
        observe_reasoner_run(REASONER_NAME, perf_counter() - t0, success=True)
        return record

    async def _run(self, anchor_alarm_id: int, lookback: timedelta) -> ReasonerExplanationRecord:
        anchor = await self.session.get(Alarm, anchor_alarm_id)
        if anchor is None:
            raise AnchorNotFoundError(anchor_alarm_id)

        machine_id = anchor.machine_id  # alarms.machine_id ist NOT NULL → immer gesetzt
        window = time_window(anchor.raised_at, lookback)
        machine = await self.session.get(Machine, machine_id)
        # F-SEM (§15): semantisch ähnliche Notizen ERGÄNZEN die zeitnahen (Union,
        # dedupliziert in reconstruct_chain). best-effort → Fallback auf Zeitfenster.
        chain = reconstruct_chain(
            anchor=anchor,
            window=window,
            prior_alarms=await self._load_alarms(machine_id, window),
            worker_notes=await self._load_worker_notes(machine_id, window),
            maintenance_events=await self._load_maintenance(machine_id, window),
            semantic_notes=await self._load_semantic_notes(anchor, machine),
        )

        # NEXUS-Recall ähnlicher Vorfälle (best-effort, blockiert nie).
        recall_items = await recall_similar_incidents(
            self.substrate, build_recall_query(anchor, machine), max_results=self.recall_max_results
        )
        record_event_chain_recall("hit" if recall_items else "miss")

        # Grounding-Quellen (worker_notes/recall untrusted) → Gateway-Synthese.
        sources = build_grounding_sources(chain, recall_items)
        response = await self.gateway.complete(
            task=Task.SYNTHESIS,
            system_prompt=EVENT_CHAIN_SYSTEM_PROMPT,
            user_prompt=build_event_chain_user_prompt(chain),
            sources=sources,
        )

        explanation = build_explanation(
            anchor_alarm_id=anchor.id,
            machine_id=machine_id,
            narrative=response.text,
            allowed=allowed_source_ids(sources),
            grounding=response.grounding,
            recall_used=bool(recall_items),
        )
        self._last = explanation

        record = await self._persist(explanation)
        await self._mirror(explanation, chain)
        record_event_chain_explanation(flagged=bool(explanation.flagged_unsupported))
        # Strukturierter Log (§11.1): Umfang/Flags/Konfidenz, KEINE PII/keine Notiz-Texte.
        logger.info(
            "%s reasoner=event_chain anchor=%s events=%s referenced=%s flagged=%s "
            "confidence=%s recall=%s",
            REASON,
            anchor.id,
            len(chain.events),
            len(explanation.referenced_source_ids),
            len(explanation.flagged_unsupported),
            explanation.confidence,
            bool(recall_items),
        )
        return record

    async def _load_alarms(self, machine_id: int, window: ChainWindow) -> list[Alarm]:
        stmt = (
            select(Alarm)
            .where(
                Alarm.machine_id == machine_id,
                Alarm.raised_at >= window.start,
                Alarm.raised_at <= window.end,
            )
            .order_by(Alarm.raised_at)
        )
        return list(await self.session.scalars(stmt))

    async def _load_worker_notes(
        self, machine_id: int, window: ChainWindow
    ) -> list[WorkerNote]:
        stmt = (
            select(WorkerNote)
            .where(
                WorkerNote.machine_id == machine_id,
                WorkerNote.created_at >= window.start,
                WorkerNote.created_at <= window.end,
            )
            .order_by(WorkerNote.created_at)
        )
        return list(await self.session.scalars(stmt))

    async def _load_maintenance(
        self, machine_id: int, window: ChainWindow
    ) -> list[MaintenanceEvent]:
        stmt = (
            select(MaintenanceEvent)
            .where(
                MaintenanceEvent.machine_id == machine_id,
                MaintenanceEvent.performed_at >= window.start,
                MaintenanceEvent.performed_at <= window.end,
            )
            .order_by(MaintenanceEvent.performed_at)
        )
        return list(await self.session.scalars(stmt))

    async def _load_semantic_notes(self, anchor: Alarm, machine: Machine | None) -> list[WorkerNote]:
        """Zieht semantisch ähnliche Notizen derselben Maschine — STRIKT best-effort (§15).

        Kein Provider gesetzt / Suche oder Embedding nicht verfügbar → leere Liste
        (Fallback auf die reine Zeitfenster-Auswahl), exakt wie der NEXUS-Recall in
        §14.1. Es wird NIE eine Exception nach oben gereicht. Die Query ist die
        PII-freie Anker-Signatur; die Treffer sind FENSTER-EXEMPT (das ist der Sinn
        der semantischen Auswahl) und werden in `reconstruct_chain` dedupliziert."""
        if self.embedding_provider is None:
            return []
        query = build_anchor_signature(anchor, machine)
        try:
            return await embed_and_search(
                self.embedding_provider,
                self.session,
                query,
                machine_id=anchor.machine_id,
                k=self.semantic_max_results,
            )
        except Exception as exc:
            # Bewusst breit (best-effort): JEDER Such-/Embedding-Fehler → kein
            # semantischer Anteil, nie Abbruch (Zeitfenster-Notizen tragen).
            logger.warning(
                "%s Semantische Notiz-Suche fehlgeschlagen (best-effort, Zeitfenster-Fallback): %s",
                REASON,
                exc,
            )
            return []

    async def _persist(self, explanation: ReasonerExplanation) -> ReasonerExplanationRecord:
        record = ReasonerExplanationRecord(
            anchor_alarm_id=explanation.anchor_alarm_id,
            machine_id=explanation.machine_id,
            reasoner=REASONER_NAME,
            narrative=explanation.narrative,
            referenced_source_ids=list(explanation.referenced_source_ids),
            flagged_unsupported=list(explanation.flagged_unsupported),
            is_hypothesis=explanation.is_hypothesis,
            confidence=explanation.confidence,
            grounded=explanation.grounding.grounded if explanation.grounding is not None else None,
            recall_used=explanation.recall_used,
        )
        self.session.add(record)
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def _mirror(self, explanation: ReasonerExplanation, chain: EventChain) -> None:
        """Spiegelt das Reasoning-Ergebnis als diskretes semantic_event (§12.4).

        Gespiegelt wird eine STRUKTURIERTE, PII-freie Zusammenfassung — NICHT der
        rohe Erzähltext (defensiv: kein potenziell eingeschleuster Freitext ins
        Gedächtnis-Substrat). Best-effort über F3 `record_semantic_event`."""
        payload = {
            "reasoner": REASONER_NAME,
            "anchor_alarm_id": explanation.anchor_alarm_id,
            "machine_id": explanation.machine_id,
            "event_count": len(chain.events),
            "confidence": explanation.confidence,
            "is_hypothesis": explanation.is_hypothesis,
            "referenced_source_ids": list(explanation.referenced_source_ids),
            "flagged_unsupported": list(explanation.flagged_unsupported),
        }
        hint = " (Hypothese)" if explanation.is_hypothesis else ""
        content = (
            f"Ereigniskette zu Alarm {explanation.anchor_alarm_id} an Maschine "
            f"{explanation.machine_id}: {len(chain.events)} Ereignisse, "
            f"Konfidenz {explanation.confidence}{hint}."
        )
        await record_semantic_event(
            self.session,
            machine_id=explanation.machine_id,
            event_type=EVENT_CHAIN_EVENT_TYPE,
            payload=payload,
            content=content,
            substrate=self.substrate,
        )
        # Spiegel-Zeile sofort flushen (§12.4: der DB-Spiegel wird immer geschrieben);
        # der Substrat-Dual-Write bleibt best-effort (in record_semantic_event gekapselt).
        await self.session.flush()


def time_window(anchor_raised_at: datetime, lookback: timedelta) -> ChainWindow:
    """Reines Helfer-Mapping: Anker-Zeitpunkt + Rückblick → [start, end]-Fenster."""
    return ChainWindow(start=anchor_raised_at - lookback, end=anchor_raised_at)


def build_anchor_signature(anchor: Alarm, machine: Machine | None) -> str:
    """Baut die PII-freie Anker-Signatur für die semantische Notiz-Suche (§15).

    Kombiniert Maschinenkontext (Klasse) mit Alarm-Code/-Message/-Kategorie. Code
    und Message sind System-/SPS-Text (kein Werker-Freitext; §8-Restrisiko bewusst),
    nie ein Personen-Bezug. Die Signatur wird eingebettet und gegen
    `worker_notes.embedding` gesucht — sie wird NIE geloggt oder persistiert.
    """
    parts: list[str] = []
    if machine is not None and machine.machine_class:
        parts.append(f"Maschine {machine.machine_class}")
    if anchor.code:
        parts.append(anchor.code)
    if anchor.message:
        parts.append(anchor.message)
    if anchor.category:
        parts.append(anchor.category)
    return " ".join(parts) if parts else "Vorfall"
