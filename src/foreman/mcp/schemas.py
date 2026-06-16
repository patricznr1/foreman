# ============================================================
#  FOREMAN — mcp/schemas.py
#  Zweck: Pydantic-Ausgabeschemata pro MCP-Tool — der EXTERNE Vertrag, den
#         FOREMAN als offener Knoten nach außen reicht. Bewusst entkoppelt von den
#         internen Read-DTOs: nur sichere, paraphrasierte Felder; der Transparenz-
#         Wrapper als gemeinsames Feld auf jedem Leaf-Output.
#  Architektur-Einordnung: MCP-Schicht (F7), Schnittstellen-Vertrag.
#  PII (Brief §2): keine Klartext-Identitäten, keine internen Re-ID-Schlüssel.
#         Werker-Felder erscheinen nur als HMAC-Token (`acknowledged_by`/`author`),
#         Notiz-Text nur NER-maskiert. Kein Embedding-Vektor, keine users-Felder.
#  IP-Wording (Invariante III): Feldnamen/Beschreibungen ohne internes Vokabular.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

from foreman.mcp.transparency import AiTransparency
from foreman.reads.status import MachineStatus

# --- Geschlossene Wertebereiche (eigener, stabiler Außen-Vertrag) ---
# `MachineStatus` stammt aus dem geteilten Read-Core (reads.status) und wird hier
# nur referenziert — eine Wahrheit für MCP-, HTTP- und WS-Status (F5).
# Operative Risiko-Entscheidung der Ausfallvorhersage relativ zum Schwellwert.
RiskDecision = Literal["elevated_risk", "normal"]
# Wirkrichtung eines erklärenden Faktors (assoziativ, nicht kausal).
FactorDirection = Literal["increases_risk", "decreases_risk"]
# Konfidenz-Stufe einer Ereignisketten-Erklärung.
Confidence = Literal["low", "medium", "high"]


class _Leaf(BaseModel):
    """Basis aller Leaf-Ausgaben: unveränderlich, kein Schmuggel zusätzlicher Felder."""

    model_config = ConfigDict(frozen=True, extra="forbid")


# ============================================================
#  Stammdaten + Status (Nicht-KI)
# ============================================================
class MachineOut(_Leaf):
    """Maschinen-Stammdaten + aggregierter Status (gesund / Drift aktiv / offene Warnung)."""

    id: int
    line_id: int | None
    external_id: str | None  # anonymisierte Anlagen-Kennung, kein Personenbezug
    label: str
    machine_class: str | None
    manufacturer: str | None
    location: str | None
    status: MachineStatus
    open_alarm_count: int
    created_at: datetime
    transparency: AiTransparency


class MachineListOut(BaseModel):
    """Liste von Maschinen-Stammdaten."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    machines: list[MachineOut]
    count: int


# ============================================================
#  Sensortrends (Nicht-KI, aggregiert)
# ============================================================
class ReadingPoint(_Leaf):
    """Ein aggregierter Minuten-Datenpunkt eines Sensortrends."""

    bucket: datetime
    avg: float
    min: float
    max: float
    last: float | None


class ReadingsOut(_Leaf):
    """Aggregierter Sensortrend eines Datenpunkts über ein Zeitfenster."""

    machine_id: int
    data_point_id: int
    data_point_name: str
    unit: str | None
    measurement_type: str | None
    normal_min: float | None
    normal_max: float | None
    points: list[ReadingPoint]
    # True, wenn das Fenster die maximale Punktzahl überschritt und gekürzt wurde.
    truncated: bool
    transparency: AiTransparency


# ============================================================
#  Alarme + Drift-Lage (Nicht-KI)
# ============================================================
class AlarmOut(_Leaf):
    """Ein Alarm (inkl. Drift-Warnung). `acknowledged_by` ist ein opaker Token."""

    id: int
    machine_id: int
    component_id: int | None
    data_point_id: int | None
    code: str | None
    message: str | None
    severity: str
    category: str
    raised_at: datetime
    cleared_at: datetime | None
    acknowledged_at: datetime | None
    # Pseudonymer Quittierungs-Token (HMAC) — nie Klartext, nie aufzulösen.
    acknowledged_by: str | None
    created_at: datetime
    transparency: AiTransparency


class AlarmListOut(BaseModel):
    """Liste von Alarmen."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    alarms: list[AlarmOut]
    count: int


class DriftStatusOut(_Leaf):
    """Aktuelle Drift-Lage einer Maschine: offene Drift-Warnungen (algorithmisch erkannt)."""

    machine_id: int
    drift_active: bool
    open_drift_count: int
    warnings: list[AlarmOut]
    transparency: AiTransparency


# ============================================================
#  Ausfallvorhersage (KI) — trägt IMMER ihren Sim-Vorbehalt
# ============================================================
class PredictionFactor(_Leaf):
    """Ein erklärender Faktor der Vorhersage (Beitrag + Wirkrichtung, assoziativ).

    `contribution` ist der Beitrag des Faktors zur Risiko-Einschätzung (positiv =
    risikoerhöhend); die Wirkrichtung ist assoziativ, nicht kausal.
    """

    feature: str
    value: float
    contribution: float
    direction: FactorDirection


class FailurePredictionOut(_Leaf):
    """Gespeicherte Ausfallvorhersage. KI-Output — `transparency` führt den Sim-Vorbehalt."""

    id: int
    machine_id: int
    reference_time: datetime
    horizon_h: int
    probability: float
    decision_threshold: float
    decision: RiskDecision
    top_factors: list[PredictionFactor]
    created_at: datetime
    transparency: AiTransparency


class FailurePredictionListOut(BaseModel):
    """Liste gespeicherter Ausfallvorhersagen."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    predictions: list[FailurePredictionOut]
    count: int


# ============================================================
#  Werker-Empfehlung (KI) — trägt IMMER ihren deterministischen Vorbehalt
# ============================================================
class WorkerRecommendationOut(_Leaf):
    """Gespeicherte Werker-Empfehlung zu einer Vorhersage. KI-Output.

    Die autoritativen Zahlen (probability/horizon_h/decision) stammen aus der
    Vorhersage, nicht aus dem Text; der Sim-Vorbehalt steckt im `transparency`-Feld.
    """

    id: int
    prediction_id: int
    machine_id: int
    recommendation_text: str
    referenced_source_ids: list[str]
    horizon_h: int
    probability: float
    decision: RiskDecision
    created_at: datetime
    transparency: AiTransparency


# ============================================================
#  Ereignisketten-Erklärung (KI)
# ============================================================
class EventChainOut(_Leaf):
    """Gespeicherte Ereignisketten-Erklärung. KI-Output (freier Erzähltext).

    Trägt die Vertrauens-Marker mit: `is_hypothesis`, `flagged_unsupported`
    (unbelegte Inhalte), `confidence`, `grounded`.
    """

    id: int
    anchor_alarm_id: int
    machine_id: int | None
    narrative: str
    referenced_source_ids: list[str]
    flagged_unsupported: list[str]
    is_hypothesis: bool
    confidence: Confidence
    grounded: bool | None
    recall_used: bool
    created_at: datetime
    transparency: AiTransparency


class EventChainListOut(BaseModel):
    """Liste gespeicherter Ereignisketten-Erklärungen."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_chains: list[EventChainOut]
    count: int


# ============================================================
#  Semantische Notiz-Suche (Nicht-KI: menschlicher Notiz-Text, nur abgerufen)
# ============================================================
class NoteHitOut(_Leaf):
    """Ein Treffer der semantischen Notiz-Suche. Text NER-maskiert, Autor pseudonym."""

    id: int
    machine_id: int | None
    shift: str | None
    text: str  # bereits NER-maskiert (Personennamen entfernt); Restrisiko bleibt
    author: str | None  # pseudonymer Token (HMAC), nie Klartext
    created_at: datetime
    transparency: AiTransparency


class NoteSearchOut(BaseModel):
    """Treffer der semantischen Notiz-Suche."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    hits: list[NoteHitOut]
    count: int
