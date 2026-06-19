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
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from foreman.llm import GroundingReport

if TYPE_CHECKING:
    # Nur für die Typannotation von `from_record` — kein Laufzeit-Import (vermeidet
    # eine harte schema → db.models-Kopplung; db.models importiert kein Schema).
    from foreman.db.models import ReasonerExplanationRecord

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


class SiblingReference(BaseModel):
    """Eine EHRLICHE, strukturierte Schwester-Referenz auf einen ähnlichen
    Vergangenheits-Vorfall — abgeleitet AUSSCHLIESSLICH aus einem realen
    NEXUS-Recall-Treffer (§14.1). Keine erfundenen Geschwister: liefert der Recall
    nichts, entsteht keine Referenz (die Liste bleibt leer, kein Platzhalter).

    Strukturierte Ziele sind nur gesetzt, wenn sie real auflösbar sind:
    `machine_id`/`machine_class`/`explanation_id` bleiben `None`, wenn der Treffer
    keinen verlässlichen Maschinen-/Erklärungs-Bezug trägt. `similarity_basis`
    benennt ehrlich, WORAN die Ähnlichkeit hängt (geteilte Anker-Signatur);
    `excerpt` ist der sanitisierte Kurz-Auszug des erinnerten Falls (untrusted
    Freitext, reine Anzeige — nie Instruktion).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    # Opake NEXUS-Referenz des Treffers (falls der Recall eine ID mitliefert).
    recall_ref: str | None
    # Aufgelöste Ziel-Maschine — nur wenn der Treffer einen echten Bezug trägt.
    machine_id: int | None
    # Maschinenklasse der Ziel-Maschine (aus der DB aufgelöst, falls machine_id).
    machine_class: str | None
    # Klickbares Ziel: eine real existierende Schwester-Erklärung (falls vorhanden).
    explanation_id: int | None
    # Ehrliche Ähnlichkeits-Basis (woran liegt die Ähnlichkeit) — PII-frei.
    similarity_basis: str
    # Sanitisierter Kurz-Auszug des erinnerten Vorfalls (untrusted, reine Anzeige).
    excerpt: str


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


class ReasonerExplanationDetailRead(ReasonerExplanationRead):
    """API-Out-Schema der DETAIL-Sicht (POST /reconstruct, GET /explanations/{id}).

    Superset von `ReasonerExplanationRead`: zusätzlich die EINGEFRORENE
    Ketten-Momentaufnahme (`chain`) und die Schwester-Referenzen (`siblings`) aus
    dem Persistenz-Snapshot — beide werden NIE bei Re-Fetch neu abgeleitet, sondern
    so ausgeliefert, wie sie zur Rekonstruktions-Zeit berechnet wurden („Stand X",
    §3.2 Pin/Persist). Pre-Snapshot-Datensätze (vor Migration 0009) liefern
    `chain=None` und `siblings=[]`.
    """

    chain: EventChain | None = None
    siblings: list[SiblingReference] = Field(default_factory=list)

    @classmethod
    def from_record(cls, record: ReasonerExplanationRecord) -> ReasonerExplanationDetailRead:
        """Baut die Detail-Sicht aus dem ORM-Datensatz inkl. eingefrorener Snapshots.

        Die JSONB-Snapshots werden gegen die typisierten Schemata validiert (defensiv:
        ein leerer/fehlender Snapshot → `chain=None` bzw. `siblings=[]`).
        """
        chain = EventChain.model_validate(record.chain_snapshot) if record.chain_snapshot else None
        siblings = [
            SiblingReference.model_validate(item) for item in (record.siblings_snapshot or [])
        ]
        return cls(
            id=record.id,
            anchor_alarm_id=record.anchor_alarm_id,
            machine_id=record.machine_id,
            reasoner=record.reasoner,
            narrative=record.narrative,
            referenced_source_ids=list(record.referenced_source_ids),
            flagged_unsupported=list(record.flagged_unsupported),
            is_hypothesis=record.is_hypothesis,
            confidence=record.confidence,  # type: ignore[arg-type]
            grounded=record.grounded,
            recall_used=record.recall_used,
            created_at=record.created_at,
            chain=chain,
            siblings=siblings,
        )
