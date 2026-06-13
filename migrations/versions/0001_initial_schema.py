"""initial schema (GROUND_TRUTH §5)

Revision ID: 0001
Revises:
Create Date: 2026-06-13

Legt alle Tabellen aus GROUND_TRUTH §5 an (Hierarchie Linie → Maschine →
Komponente → Datenpunkt + readings/alarms/production_runs/maintenance_events/
worker_notes/users/audit_logs/semantic_events) mit PK-/FK-Constraints und den
nötigen Lese-Indizes. Die `readings`-Tabelle entsteht hier als gewöhnliche
Tabelle; die Umwandlung in eine TimescaleDB-Hypertable + Columnstore + CAGGs +
Retention erfolgt in 0002. Die `worker_notes.embedding`-Spalte (vector(1024))
wird ebenfalls erst in 0002 ergänzt — zusammen mit der `vector`-Extension.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOW = sa.text("now()")


def upgrade() -> None:
    # --- users (einziger Ort der Klartext-Identität, §8) ---
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "role", sa.String(32), nullable=False, server_default=sa.text("'worker'")
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    # --- lines ---
    op.create_table(
        "lines",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
    )

    # --- audit_logs ---
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(128), nullable=False),
        sa.Column("target", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
    )

    # --- machines ---
    op.create_table(
        "machines",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("line_id", sa.BigInteger(), sa.ForeignKey("lines.id"), nullable=True),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("machine_class", sa.String(128), nullable=True),
        sa.Column("manufacturer", sa.String(255), nullable=True),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
    )

    # --- semantic_events ---
    op.create_table(
        "semantic_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("machine_id", sa.BigInteger(), sa.ForeignKey("machines.id"), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("substrate_ref", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
    )

    # --- components ---
    op.create_table(
        "components",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("machine_id", sa.BigInteger(), sa.ForeignKey("machines.id"), nullable=False),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("component_type", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
    )

    # --- data_points (ersetzt „sensors") ---
    op.create_table(
        "data_points",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("machine_id", sa.BigInteger(), sa.ForeignKey("machines.id"), nullable=False),
        sa.Column("component_id", sa.BigInteger(), sa.ForeignKey("components.id"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("measurement_type", sa.String(32), nullable=True),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("source", sa.String(16), nullable=True),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column("normal_min", sa.Double(), nullable=True),
        sa.Column("normal_max", sa.Double(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
    )
    op.create_index("ix_data_points_machine", "data_points", ["machine_id"])

    # --- readings (in 0002 → Hypertable). PK (data_point_id, time). ---
    op.create_table(
        "readings",
        sa.Column("data_point_id", sa.BigInteger(), sa.ForeignKey("data_points.id"), nullable=False),
        sa.Column("time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("value", sa.Double(), nullable=False),
        sa.Column("quality", sa.SmallInteger(), nullable=True),
        sa.PrimaryKeyConstraint("data_point_id", "time", name="pk_readings"),
    )

    # --- alarms (Nothalt = category=safety, severity=emergency) ---
    op.create_table(
        "alarms",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("machine_id", sa.BigInteger(), sa.ForeignKey("machines.id"), nullable=False),
        sa.Column("component_id", sa.BigInteger(), sa.ForeignKey("components.id"), nullable=True),
        sa.Column("data_point_id", sa.BigInteger(), sa.ForeignKey("data_points.id"), nullable=True),
        sa.Column("code", sa.String(64), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("raised_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        # acknowledged_by: HMAC-Token über users.id (pseudonymisiert), nullable.
        sa.Column("acknowledged_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
    )
    op.create_index("ix_alarms_machine_raised", "alarms", ["machine_id", "raised_at"])

    # --- production_runs (Linien-Ebene) ---
    op.create_table(
        "production_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("line_id", sa.BigInteger(), sa.ForeignKey("lines.id"), nullable=False),
        sa.Column("product_code", sa.String(128), nullable=False),
        sa.Column("order_id", sa.String(128), nullable=True),
        sa.Column("batch", sa.String(128), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
    )

    # --- maintenance_events ---
    op.create_table(
        "maintenance_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("machine_id", sa.BigInteger(), sa.ForeignKey("machines.id"), nullable=False),
        sa.Column("component_id", sa.BigInteger(), sa.ForeignKey("components.id"), nullable=True),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("performed_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        # performed_by: HMAC-Token über users.id (pseudonymisiert).
        sa.Column("performed_by", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
    )

    # --- worker_notes (embedding-Spalte folgt in 0002 mit der vector-Extension) ---
    op.create_table(
        "worker_notes",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("machine_id", sa.BigInteger(), sa.ForeignKey("machines.id"), nullable=True),
        sa.Column("shift", sa.String(16), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("classification", sa.String(32), nullable=True),
        # author: HMAC-Token über users.id (pseudonymisiert).
        sa.Column("author", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
    )
    op.create_index("ix_worker_notes_machine", "worker_notes", ["machine_id"])


def downgrade() -> None:
    op.drop_index("ix_worker_notes_machine", table_name="worker_notes")
    op.drop_table("worker_notes")
    op.drop_table("maintenance_events")
    op.drop_table("production_runs")
    op.drop_index("ix_alarms_machine_raised", table_name="alarms")
    op.drop_table("alarms")
    op.drop_table("readings")
    op.drop_index("ix_data_points_machine", table_name="data_points")
    op.drop_table("data_points")
    op.drop_table("components")
    op.drop_table("semantic_events")
    op.drop_table("machines")
    op.drop_table("audit_logs")
    op.drop_table("lines")
    op.drop_table("users")
