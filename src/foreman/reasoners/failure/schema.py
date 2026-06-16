# ============================================================
#  FOREMAN — reasoners/failure/schema.py
#  Zweck: Output-Form des Ausfallvorhersage-Reasoners (F-PRED) zuerst
#         festgenagelt — FailurePrediction (Wahrscheinlichkeit + Entscheidung +
#         SHAP-Faktoren) und das API-Read-/Request-Schema.
#  Architektur-Einordnung: API-/Reasoning-Vertrag (Schicht 2).
#
#  STRUKTURELLE EHRLICHKEIT (Kern-Deliverable, §16): `validation_status` ist ein
#         PFLICHTFELD ohne Default mit dem einzigen erlaubten Wert
#         'simulation_only'. Eine FailurePrediction kann nicht ohne ihren
#         Vorbehalt existieren — kein Konstruktionsweg umgeht ihn. `data_regime`
#         und `model_version` stammen aus den Artefakt-Metadaten. extra=forbid:
#         kein Schmuggel zusätzlicher Felder.
#  Sicherheit (§13.3): Die Zahlen (probability, shap) sind autoritativ vom Modell
#         gesetzt — sie kommen NIE aus einem LLM (relevant für den späteren
#         Erklär-Layer; Konsistenz mit dem Gateway-Vertrag).
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Richtung eines SHAP-Faktors (assoziativ, NICHT kausal — siehe Model Card).
FactorDirection = Literal["increases_risk", "decreases_risk"]
# Operative Entscheidung relativ zum kostensensitiven Schwellwert.
RiskDecision = Literal["elevated_risk", "normal"]
# Der Vorbehalt: einziger erlaubter Wert, Pflichtfeld ohne Default (§16).
ValidationStatus = Literal["simulation_only"]
# Datenregime des Trainings: ausschließlich Simulation (kein Realdaten-Pfad).
DataRegime = Literal["simulation"]


class TopFactor(BaseModel):
    """Ein erklärender Faktor der Vorhersage (SHAP-TreeExplainer-Attribution).

    `shap` ist der Beitrag des Features zur Log-Odds der Vorhersage; `direction`
    ist seine Wirkrichtung (assoziativ, nicht kausal — die Model Card grenzt das
    explizit ab). Die Zahlen sind autoritativ vom Modell, nie aus einem LLM.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    feature: str = Field(min_length=1)
    value: float
    shap: float
    direction: FactorDirection


class FailurePrediction(BaseModel):
    """Das validierte Ergebnis des Ausfallvorhersage-Reasoners.

    Der Output-Guard der Ehrlichkeit: `validation_status` ist Pflicht (kein
    Default, nur 'simulation_only'), `data_regime`/`model_version` kommen aus den
    Artefakt-Metadaten. So trägt JEDE Vorhersage ihren Sim-Vorbehalt mit —
    Persistenz, Dashboard, MCP und der spätere Erklär-Layer müssen ihn führen.
    `created_at`/`id` werden erst bei der Persistenz vergeben (siehe
    FailurePredictionRead), analog zum Ereignisketten-Reasoner (§14).
    """

    # protected_namespaces=(): `model_version` ist ein Brief-mandatiertes Feld —
    # Pydantics `model_`-Namespace-Schutz wird hier bewusst aufgehoben.
    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    machine_id: int
    reference_time: datetime
    horizon_h: int = Field(gt=0)
    probability: float = Field(ge=0.0, le=1.0)
    decision_threshold: float = Field(ge=0.0, le=1.0)
    decision: RiskDecision
    top_factors: tuple[TopFactor, ...]
    # --- Strukturelle Ehrlichkeit (Pflicht, nicht umgehbar) ---
    validation_status: ValidationStatus
    data_regime: DataRegime
    model_version: str = Field(min_length=1)

    @model_validator(mode="after")
    def _enforce_invariants(self) -> FailurePrediction:
        """Erzwingt tz-aware reference_time und Konsistenz decision↔Schwellwert."""
        if self.reference_time.tzinfo is None:
            raise ValueError("FailurePrediction.reference_time muss tz-aware sein (UTC).")
        expected = "elevated_risk" if self.probability >= self.decision_threshold else "normal"
        if self.decision != expected:
            raise ValueError(
                f"❌ decision='{self.decision}' inkonsistent zu probability="
                f"{self.probability} / threshold={self.decision_threshold} "
                f"(erwartet '{expected}')."
            )
        return self


class PredictRequest(BaseModel):
    """Anfrage an POST /predict: Maschine + Bezugszeitpunkt + Vorlauf-Fenster.

    `reference_time` None → Service-Default (jetzt, UTC). `lookback_hours` None →
    Service-Default. Der Horizont kommt NICHT aus dem Request, sondern aus dem
    geladenen Artefakt (das Modell wurde für genau diesen Horizont trainiert).
    """

    model_config = ConfigDict(extra="forbid")

    machine_id: int = Field(gt=0)
    reference_time: datetime | None = None
    lookback_hours: int | None = Field(default=None, ge=1, le=8760)

    @model_validator(mode="after")
    def _reference_tz_aware(self) -> PredictRequest:
        if self.reference_time is not None and self.reference_time.tzinfo is None:
            raise ValueError("reference_time muss tz-aware sein (mit Zeitzonen-Offset).")
        return self


class FailurePredictionRead(BaseModel):
    """API-Out-Schema: liest direkt aus dem persistierten ORM-Datensatz.

    Führt den Sim-Vorbehalt (`validation_status`, `data_regime`, `model_version`)
    in JEDER Antwort mit — kein Konsument bekommt eine Vorhersage ohne ihn.
    """

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    machine_id: int
    reference_time: datetime
    horizon_h: int
    probability: float
    decision_threshold: float
    decision: RiskDecision
    top_factors: list[TopFactor]
    validation_status: ValidationStatus
    data_regime: DataRegime
    model_version: str
    created_at: datetime


# ============================================================
#  F-REC — LLM-Werker-Empfehlung (Erklär-Layer über der Vorhersage)
# ============================================================

# Deterministische Vorbehalts-Sätze je validation_status. NICHT vom LLM erzeugt —
# der Sim-Vorbehalt ist strukturell garantiert (Invariante II, Brief §2.4): er
# hängt nie am fehlbaren LLM-Text, sondern an diesem festen Mapping.
_VALIDATION_CAVEATS: dict[str, str] = {
    "simulation_only": (
        "Diese Einschätzung beruht auf simulierten Verläufen und ist nicht an "
        "realen Ausfällen validiert."
    ),
}


def validation_caveat_for(validation_status: ValidationStatus) -> str:
    """Der deterministische Vorbehalts-Satz zu einem validation_status.

    Garantiert (Invariante II): der Sim-Vorbehalt wird nie vom LLM formuliert,
    sondern hier festgelegt — jede WorkerRecommendation trägt exakt diesen Satz,
    unabhängig davon, was das LLM schreibt.
    """
    return _VALIDATION_CAVEATS[validation_status]


class WorkerRecommendation(BaseModel):
    """Die validierte LLM-Werker-Empfehlung über einer FailurePrediction (F-REC).

    Der Erklär-Layer über F-PRED: das LLM verschmilzt die statistische Vorhersage,
    die SHAP-Faktoren und den semantischen NEXUS-Kontext zu einer handlungsleitenden
    deutschen Empfehlung. Zwei Invarianten sind strukturell erzwungen:
    (I) Zahlen autoritativ vom Modell — `probability`/`horizon_h`/`decision` werden
        aus der Vorhersage mitgeführt, nicht vom LLM gesetzt (der numerische
        Post-Check im Service rejectet erfundene Zahlen, §13.3).
    (II) Der Sim-Vorbehalt ist deterministisch — `validation_caveat` MUSS exakt
        `validation_caveat_for(validation_status)` sein; er hängt nie am LLM-Text.
    `created_at`/`id` werden erst bei der Persistenz vergeben (WorkerRecommendationRead).
    """

    model_config = ConfigDict(frozen=True, extra="forbid", protected_namespaces=())

    prediction_id: int
    machine_id: int
    recommendation_text: str = Field(min_length=1)
    # Deterministischer Vorbehalt (Invariante II) — nicht LLM-generiert.
    validation_caveat: str = Field(min_length=1)
    # --- Strukturelle Ehrlichkeit (Pflicht, aus der Vorhersage mitgeführt) ---
    validation_status: ValidationStatus
    data_regime: DataRegime
    model_version: str = Field(min_length=1)
    # --- Output-Guard: Quellen-Whitelist (Brief §2.3) ---
    referenced_source_ids: tuple[str, ...]
    allowed_source_ids: tuple[str, ...]
    # --- Autoritative Zahlen aus der Vorhersage (Invariante I) ---
    horizon_h: int = Field(gt=0)
    probability: float = Field(ge=0.0, le=1.0)
    decision: RiskDecision

    @model_validator(mode="after")
    def _enforce_caveat_and_whitelist(self) -> WorkerRecommendation:
        """Erzwingt den deterministischen Vorbehalt + den Quellen-Whitelist-Guard."""
        expected_caveat = validation_caveat_for(self.validation_status)
        if self.validation_caveat != expected_caveat:
            raise ValueError(
                "❌ validation_caveat weicht vom deterministischen Sim-Vorbehalt ab "
                "(Invariante II: der Vorbehalt darf nicht durch LLM-Text ersetzt werden)."
            )
        allowed = set(self.allowed_source_ids)
        invalid = [s for s in self.referenced_source_ids if s not in allowed]
        if invalid:
            raise ValueError(
                f"❌ Referenzierte source_ids außerhalb der Whitelist: {sorted(invalid)}"
            )
        return self


class WorkerRecommendationRead(BaseModel):
    """API-Out-Schema der Werker-Empfehlung: liest direkt aus dem ORM-Datensatz.

    Führt den Sim-Vorbehalt (`validation_caveat`, `validation_status`,
    `data_regime`, `model_version`) in JEDER Antwort mit — kein Konsument bekommt
    eine Empfehlung ohne ihn.
    """

    model_config = ConfigDict(from_attributes=True, protected_namespaces=())

    id: int
    prediction_id: int
    machine_id: int
    recommendation_text: str
    validation_caveat: str
    validation_status: ValidationStatus
    data_regime: DataRegime
    model_version: str
    referenced_source_ids: list[str]
    horizon_h: int
    probability: float
    decision: RiskDecision
    created_at: datetime
