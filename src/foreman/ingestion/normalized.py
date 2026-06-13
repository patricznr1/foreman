# ============================================================
#  FOREMAN — ingestion/normalized.py
#  Zweck: Internes Normalformat der Datenakquise (F3) — das einheitliche
#         Format, das ALLE Adapter ausgeben und die Ingestion konsumiert.
#  Architektur-Einordnung: Ingestion-Vertrag (Schicht 2). Das Reasoning/die DB
#         kennen das Quellprotokoll nicht; jeder Adapter normalisiert auf diese
#         Modelle.
#  Zeit (§Constraints): alle Zeitstempel tz-aware UTC. Naive Eingaben werden als
#         UTC interpretiert, aware Eingaben nach UTC konvertiert — damit die
#         Zeitachse über alle erzeugten Readings/Events konsistent bleibt.
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def ensure_utc(value: datetime) -> datetime:
    """Erzwingt tz-aware UTC: naive → als UTC interpretiert, aware → konvertiert."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class NormalizedReading(BaseModel):
    """Ein normalisierter Messwert — passt 1:1 auf die `readings`-Hypertable (§5).

    `data_point_id` ist die echte DB-ID (nach dem Topologie-Seeding aufgelöst).
    `value` trägt analoge Messwerte ebenso wie digitale I/O als 0.0/1.0.
    `quality` ist optional (None = nicht bewertet); fehlende Intervalle werden
    gar nicht erst erzeugt, statt als 0 geschrieben.
    """

    model_config = ConfigDict(frozen=True)

    time: datetime
    data_point_id: int
    value: float
    quality: int | None = None

    @field_validator("time")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class EventKind(StrEnum):
    """Diskrete Ereignis-Arten, die ein Adapter neben Readings liefern kann."""

    ALARM = "alarm"
    PRODUCTION_RUN = "production_run"
    MAINTENANCE = "maintenance"
    WORKER_NOTE = "worker_note"


class _EventBase(BaseModel):
    """Gemeinsame Basis aller diskreten Ereignisse.

    `occurred_at` ist der maßgebliche Strom-Zeitstempel (für die zeitliche
    Sortierung im gemischten Reading/Event-Strom). Die zieltabellen-spezifischen
    Zeitfelder werden im IngestionService daraus abgeleitet.
    """

    model_config = ConfigDict(frozen=True)

    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def _utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class AlarmEvent(_EventBase):
    """Fehlermeldung/Nothalt → Zieltabelle `alarms` (occurred_at = raised_at)."""

    kind: Literal["alarm"] = "alarm"
    machine_id: int
    component_id: int | None = None
    data_point_id: int | None = None
    code: str | None = None
    message: str | None = None
    severity: str
    category: str


class ProductionRunRecord(_EventBase):
    """Produktionslauf-Grenzen → Zieltabelle `production_runs` (Linien-Ebene).

    Trägt Start und (sofern bekannt) Ende eines Laufs. occurred_at = started_at.
    """

    kind: Literal["production_run"] = "production_run"
    line_id: int
    product_code: str
    order_id: str | None = None
    batch: str | None = None
    started_at: datetime
    ended_at: datetime | None = None

    @field_validator("started_at", "ended_at")
    @classmethod
    def _utc_bounds(cls, value: datetime | None) -> datetime | None:
        return ensure_utc(value) if value is not None else None

    @model_validator(mode="after")
    def _occurred_gleich_started(self) -> ProductionRunRecord:
        # occurred_at (Strom-Sortierung) und started_at (fachlicher Laufstart) müssen
        # denselben Instant tragen — sonst driften Dispatch- und Laufzeitachse auseinander.
        if self.occurred_at != self.started_at:
            raise ValueError(
                "ProductionRunRecord: occurred_at muss started_at entsprechen."
            )
        return self


class MaintenanceRecord(_EventBase):
    """Wartungsereignis → Zieltabelle `maintenance_events` (occurred_at = performed_at).

    `performed_by_ref` ist die rohe (synthetische) Werker-/User-Referenz; der
    IngestionService tokenisiert sie VOR dem Insert (Nachweis-Bezug, §8) — nie
    Klartext in der Nutzdatenbank.
    """

    kind: Literal["maintenance"] = "maintenance"
    machine_id: int
    component_id: int | None = None
    type: str
    description: str | None = None
    performed_by_ref: str | None = None


class WorkerNoteRecord(_EventBase):
    """Werker-Notiz → Zieltabelle `worker_notes` (occurred_at = created_at).

    `text` ist roher Freitext; der IngestionService maskiert Personennamen per
    NER VOR dem Insert. `author_ref` ist die rohe User-Referenz und wird
    tokenisiert (§8) — kein Klartext-Personenbezug in der Nutzdatenbank.
    """

    kind: Literal["worker_note"] = "worker_note"
    machine_id: int | None = None
    shift: str | None = None
    text: str
    author_ref: str | None = None


# Diskriminierte Union über das `kind`-Feld — der IngestionService dispatcht
# typsicher (mypy --strict) per Pattern-Matching auf die konkreten Klassen.
NormalizedEvent = Annotated[
    AlarmEvent | ProductionRunRecord | MaintenanceRecord | WorkerNoteRecord,
    Field(discriminator="kind"),
]
