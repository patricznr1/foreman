# ============================================================
#  FOREMAN — reasoners/event_chain/schema.py
#  Zweck: Output-Form des Ereignisketten-Reasoners (F6) zuerst festgenagelt —
#         EventChain (zeitlich geordnete Ereignisse rund um einen Anker) und das
#         VALIDIERTE ReasonerExplanation-Objekt (Erzähltext, referenzierte
#         source_ids, Konfidenz-/Hypothese-Markierung, Grounding-Report des
#         Gateways). Plus das API-Read-Schema und der Reconstruct-Request.
#  Architektur-Einordnung: API-/Reasoning-Vertrag (Schicht 2).
#  Sicherheit (Schutz-Doc §5.1): Der ReasonerExplanation-Validator ist der
#         Output-Guard — referenzierte Quellen MÜSSEN aus der übergebenen
#         Whitelist (`allowed_source_ids`) stammen; eingeschleuste/erfundene
#         Quellen (z. B. evt:9999) gehören in `flagged_unsupported`, nie in
#         `referenced_source_ids`. extra=forbid: kein Schmuggel zusätzlicher Felder.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from foreman.llm import GroundingReport

# Konfidenz-Stufen der Erzählung (geschlossener Wertebereich).
Confidence = Literal["low", "medium", "high"]


class ChainEventType(StrEnum):
    """Typ eines Ereignisses in der rekonstruierten Kette (Metrik-/Anzeige-Label)."""

    ANCHOR_ALARM = "anchor_alarm"  # das Anker-Ereignis selbst
    DRIFT_ALARM = "drift_alarm"  # vorausgehende Drift-Warnung (F4, code=DRIFT)
    PRIOR_ALARM = "prior_alarm"  # sonstige vorausgehende Alarme
    WORKER_NOTE = "worker_note"  # untrusted Werker-Freitext (Spotlighting-Quelle!)
    MAINTENANCE = "maintenance"  # Wartungsereignis


class ChainWindow(BaseModel):
    """Zeitfenster der Ketten-Rekonstruktion (tz-aware UTC, geschlossen [start, end])."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    start: datetime
    end: datetime

    @model_validator(mode="after")
    def _validate_window(self) -> ChainWindow:
        """Erzwingt die Fenster-Invariante: beide Grenzen tz-aware (UTC) und start ≤ end."""
        if self.start.tzinfo is None or self.end.tzinfo is None:
            raise ValueError("ChainWindow.start/end müssen tz-aware sein (UTC).")
        if self.start > self.end:
            raise ValueError("ChainWindow.start darf nicht nach end liegen.")
        return self


class ChainEvent(BaseModel):
    """Ein einzelnes Ereignis der Kette.

    `trusted` trägt die Sicherheits-Invariante in die Grounding-Quellen: strukturierte
    DB-/Reasoner-Daten (Alarm/Wartung) sind `trusted=True`; Werkernotizen-Freitext ist
    `trusted=False` (untrusted, datamarkiert, belegt keine Zahlen).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str
    event_type: ChainEventType
    occurred_at: datetime
    machine_id: int | None
    summary: str
    trusted: bool


class EventChain(BaseModel):
    """Die rekonstruierte, zeitlich geordnete Ereigniskette um einen Anker-Alarm."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    anchor_alarm_id: int
    machine_id: int | None
    window: ChainWindow
    events: tuple[ChainEvent, ...]


class ReasonerExplanation(BaseModel):
    """Das validierte Ergebnis des Reasoners — der Output-Guard (Schutz-Doc §5.1).

    `referenced_source_ids` darf ausschließlich Quellen aus `allowed_source_ids`
    enthalten (Faktor-Whitelist). Eingeschleuste/erfundene Quellen und unbelegte
    Zahlen landen in `flagged_unsupported`; sind welche vorhanden, ist die Erzählung
    zwingend als Hypothese markiert.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    anchor_alarm_id: int
    machine_id: int | None
    narrative: str = Field(min_length=1)
    allowed_source_ids: tuple[str, ...]
    referenced_source_ids: tuple[str, ...]
    flagged_unsupported: tuple[str, ...]
    is_hypothesis: bool
    confidence: Confidence
    recall_used: bool
    grounding: GroundingReport | None = None

    @model_validator(mode="after")
    def _enforce_source_whitelist(self) -> ReasonerExplanation:
        """Output-Guard: zitierte Quellen müssen in der Whitelist stehen; geflaggte
        unbelegte Inhalte erzwingen die Hypothese-Markierung (Konsistenz)."""
        allowed = set(self.allowed_source_ids)
        invalid = [s for s in self.referenced_source_ids if s not in allowed]
        if invalid:
            raise ValueError(
                f"❌ Referenzierte source_ids außerhalb der Whitelist: {sorted(invalid)}"
            )
        if self.flagged_unsupported and not self.is_hypothesis:
            raise ValueError(
                "❌ flagged_unsupported gesetzt, aber is_hypothesis=False (inkonsistent)."
            )
        return self


class ReconstructRequest(BaseModel):
    """Anfrage an POST /reconstruct: Anker-Alarm + optionales Rückblick-Fenster."""

    model_config = ConfigDict(extra="forbid")

    anchor_alarm_id: int = Field(gt=0)
    # Rückblick in Stunden ab dem Anker-Zeitpunkt; None → Service-Default.
    lookback_hours: int | None = Field(default=None, ge=1, le=8760)


class ReasonerExplanationRead(BaseModel):
    """API-Out-Schema: liest direkt aus dem persistierten ORM-Datensatz."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    anchor_alarm_id: int
    machine_id: int | None
    reasoner: str
    narrative: str
    referenced_source_ids: list[str]
    flagged_unsupported: list[str]
    is_hypothesis: bool
    confidence: Confidence
    grounded: bool | None
    recall_used: bool
    created_at: datetime
