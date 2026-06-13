# ============================================================
#  FOREMAN — db/models.py
#  Zweck: Vollständiges Datenbank-Schema (GROUND_TRUTH §5) als async
#         SQLAlchemy-2.0-Modelle.
#  Architektur-Einordnung: Persistenz-Schicht (Schicht 2).
#  Hierarchie: Linie → Maschine → Komponente → Datenpunkt.
#  Datenschutz (§8): Personen-Felder (`worker_notes.author`,
#         `alarms.acknowledged_by`, `maintenance_events.performed_by`) sind
#         HMAC-Token "v{n}:{64-hex}", NIE Klartext. Klartext-Identität
#         ausschließlich in `users`. Tokenisierung im Schreibpfad (core/pseudonymize).
# ============================================================
from __future__ import annotations

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    DateTime,
    Double,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from foreman.db.base import Base, TimestampMixin

# Dimension der Embedding-Spalte (semantische Suche, später). Quelle:
# docs/research/vektor-suche-pgvector.md — vector(1024), ohne Index in F2.
EMBEDDING_DIM = 1024


class Line(Base, TimestampMixin):
    """`lines` — Fertigungsstraßen. Produktionskontext liegt auf Linien-Ebene."""

    __tablename__ = "lines"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))


class Machine(Base, TimestampMixin):
    """`machines` — Maschinen. `line_id` nullable für Einzelmaschinen."""

    __tablename__ = "machines"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    line_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("lines.id"))
    # external_id: anonymisierte Maschinen-Kennung (kein Personenbezug).
    external_id: Mapped[str | None] = mapped_column(String(255))
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    machine_class: Mapped[str | None] = mapped_column(String(128))
    manufacturer: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))


class Component(Base, TimestampMixin):
    """`components` — Komponenten einer Maschine (Spindel, Antrieb, Lager …)."""

    __tablename__ = "components"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    machine_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("machines.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    # component_type: spindle/drive/bearing/motor/axis/…
    component_type: Mapped[str | None] = mapped_column(String(64))


class DataPoint(Base, TimestampMixin):
    """`data_points` — Datenpunkte / Tags (ersetzt „sensors")."""

    __tablename__ = "data_points"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # machine_id immer gesetzt; component_id optional.
    machine_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("machines.id"), nullable=False
    )
    component_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("components.id")
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # kind: analog/digital/setpoint/counter
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    # measurement_type: voltage/current/dc_bus/temperature/speed/frequency/torque/force/signal/null
    measurement_type: Mapped[str | None] = mapped_column(String(32))
    # unit: V/A/°C/rpm/Hz/Nm/N/kN/bool/…
    unit: Mapped[str | None] = mapped_column(String(32))
    # source: opcua/modbus/mqtt/s7
    source: Mapped[str | None] = mapped_column(String(16))
    # address: Node-ID / Register
    address: Mapped[str | None] = mapped_column(String(255))
    normal_min: Mapped[float | None] = mapped_column(Double)
    normal_max: Mapped[float | None] = mapped_column(Double)


class Reading(Base):
    """`readings` — TimescaleDB-Hypertable (analoge Messwerte + digitale I/O als 0/1).

    Composite-PK `(data_point_id, time)`; in Migration 0002 wird die Tabelle auf
    `time` zur Hypertable (1-Tages-Chunks). KEINE Zusatz-Indizes (Research §3.4) —
    aggregierte Lesezugriffe laufen über die Continuous Aggregates.
    """

    __tablename__ = "readings"

    data_point_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("data_points.id"), primary_key=True
    )
    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True, nullable=False
    )
    value: Mapped[float] = mapped_column(Double, nullable=False)
    quality: Mapped[int | None] = mapped_column(SmallInteger)


class Alarm(Base, TimestampMixin):
    """`alarms` — Fehlermeldungen + Nothalt. Nothalt = category=safety, severity=emergency."""

    __tablename__ = "alarms"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    machine_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("machines.id"), nullable=False
    )
    component_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("components.id")
    )
    data_point_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("data_points.id")
    )
    code: Mapped[str | None] = mapped_column(String(64))
    message: Mapped[str | None] = mapped_column(Text)
    # severity: info/warning/alarm/critical/emergency
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    # category: process/safety/hardware/electrical/…
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    raised_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # acknowledged_by: pseudonymisiert (HMAC-Token über users.id), nullable.
    # Nachweis-Bezug; rechtsverbindlicher namentlicher Nachweis im Prüf-/Wartungs-
    # protokoll bzw. QM-System (System of Record), nicht in FOREMAN.
    acknowledged_by: Mapped[str | None] = mapped_column(String(128))


class ProductionRun(Base, TimestampMixin):
    """`production_runs` — Produktionskontext auf Linien-Ebene (Welt A)."""

    __tablename__ = "production_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    line_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("lines.id"), nullable=False
    )
    product_code: Mapped[str] = mapped_column(String(128), nullable=False)
    order_id: Mapped[str | None] = mapped_column(String(128))
    batch: Mapped[str | None] = mapped_column(String(128))
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MaintenanceEvent(Base, TimestampMixin):
    """`maintenance_events` — Wartungsereignisse."""

    __tablename__ = "maintenance_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    machine_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("machines.id"), nullable=False
    )
    component_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("components.id")
    )
    type: Mapped[str] = mapped_column(String(64), nullable=False)
    performed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text)
    # performed_by: pseudonymisiert (HMAC-Token über users.id).
    # Nachweis-Bezug; rechtsverbindlicher namentlicher Nachweis im Prüf-/Wartungs-
    # protokoll bzw. QM-System (System of Record), nicht in FOREMAN.
    performed_by: Mapped[str | None] = mapped_column(String(128))


class WorkerNote(Base, TimestampMixin):
    """`worker_notes` — Schichtberichte. KI-Felder (`classification`, `embedding`) in F2 leer.

    `text` wird VOR dem Insert per NER auf Personennamen maskiert (Restrisiko bleibt;
    nie als anonym deklariert). `author` ist ein HMAC-Token über users.id.
    `embedding` (vector(1024)) ist nullable und in F2 ohne Index/ungenutzt.
    """

    __tablename__ = "worker_notes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    machine_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("machines.id"))
    shift: Mapped[str | None] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    classification: Mapped[str | None] = mapped_column(String(32))
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    # author: pseudonymisiert (HMAC-Token über users.id).
    author: Mapped[str | None] = mapped_column(String(128))


class User(Base, TimestampMixin):
    """`users` — Auth. EINZIGER Ort der Klartext-Identität (§8)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32), nullable=False, default="worker", server_default="worker"
    )


class AuditLog(Base, TimestampMixin):
    """`audit_logs` — Protokoll sicherheits-/datenschutzrelevanter Aktionen."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    target: Mapped[str | None] = mapped_column(String(255))


class SemanticEvent(Base, TimestampMixin):
    """`semantic_events` — Spiegel der Dual-Writes ans Gedächtnis-Substrat."""

    __tablename__ = "semantic_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    machine_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("machines.id"))
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    substrate_ref: Mapped[str | None] = mapped_column(String(255))


# Häufige Lese-Zugriffe absichern (keine Indizes auf der readings-Rohtabelle, §3.4).
Index("ix_alarms_machine_raised", Alarm.machine_id, Alarm.raised_at)
Index("ix_worker_notes_machine", WorkerNote.machine_id)
Index("ix_data_points_machine", DataPoint.machine_id)
