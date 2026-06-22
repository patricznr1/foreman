"""audit trail + topology source (Sektion I)

Erweitert das nackte `audit_logs`-Skelett zum echten, UNVERÄNDERLICHEN Audit-Trail
(zugleich AI-Act-/Art.-50-Nachweis-Beleg, §10.5): additive Spalten (actor/actor_role/
action_type/target_kind/target_id/machine_id/origin/detail/occurred_at), CHECK-Constraints
auf den geschlossenen Vokabularen (Defense-in-Depth analog failure_*), Lese-Indizes und
ein Append-Only-Trigger, der UPDATE/DELETE DB-seitig abweist. Bestehende Spalten bleiben
unangetastet; der Legacy-`user_id`-FK wird vom Schreibpfad nicht mehr befüllt (§8).

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Append-only erzwingen: jeder UPDATE/DELETE auf audit_logs wird abgewiesen. Bewusst
# KEIN BEFORE-TRUNCATE-Trigger — TRUNCATE feuert keine Row-Trigger, und die Test-/
# Admin-Reset-Pfade (TRUNCATE … CASCADE) müssen die Tabelle leeren können.
# Je ein einzelnes Statement pro op.execute (asyncpg-Prepared-Statement erlaubt kein
# Mehrfach-Kommando, vgl. 0002).
_CREATE_FUNCTION = """
CREATE OR REPLACE FUNCTION foreman_block_audit_logs_mutation()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION
        'audit_logs ist append-only: % ist nicht erlaubt (Sektion I, Migration 0010).',
        TG_OP;
END;
$$;
"""

_CREATE_TRIGGER = """
CREATE TRIGGER trg_audit_logs_append_only
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW
    EXECUTE FUNCTION foreman_block_audit_logs_mutation();
"""


def upgrade() -> None:
    # --- Additive Spalten (bestehende id/user_id/action/target/created_at unberührt) ---
    op.add_column("audit_logs", sa.Column("actor", sa.String(128), nullable=True))
    op.add_column("audit_logs", sa.Column("actor_role", sa.String(32), nullable=True))
    op.add_column("audit_logs", sa.Column("action_type", sa.String(64), nullable=True))
    op.add_column("audit_logs", sa.Column("target_kind", sa.String(32), nullable=True))
    op.add_column("audit_logs", sa.Column("target_id", sa.BigInteger(), nullable=True))
    op.add_column("audit_logs", sa.Column("machine_id", sa.BigInteger(), nullable=True))
    op.add_column("audit_logs", sa.Column("origin", sa.String(16), nullable=True))
    op.add_column("audit_logs", sa.Column("detail", postgresql.JSONB(), nullable=True))
    op.add_column(
        "audit_logs",
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=True,
        ),
    )

    # --- CHECK-Constraints (geschlossene, erweiterbare Vokabulare; NULL für Altzeilen) ---
    op.create_check_constraint(
        "ck_audit_logs_action_type",
        "audit_logs",
        "action_type IS NULL OR action_type IN ('hitl_acknowledge', 'mcp_retrieval')",
    )
    op.create_check_constraint(
        "ck_audit_logs_origin",
        "audit_logs",
        "origin IS NULL OR origin IN ('dashboard', 'mcp', 'system')",
    )

    # --- Lese-Indizes (jüngste zuerst + häufige Filter) ---
    op.create_index("ix_audit_logs_occurred", "audit_logs", ["occurred_at"])
    op.create_index("ix_audit_logs_action_occurred", "audit_logs", ["action_type", "occurred_at"])
    op.create_index("ix_audit_logs_machine", "audit_logs", ["machine_id"])
    op.create_index("ix_audit_logs_target", "audit_logs", ["target_kind", "target_id"])

    # --- Unveränderlichkeit DB-seitig (Defense-in-Depth) ---
    op.execute(_CREATE_FUNCTION)
    op.execute(_CREATE_TRIGGER)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_append_only ON audit_logs;")
    op.execute("DROP FUNCTION IF EXISTS foreman_block_audit_logs_mutation();")
    op.drop_index("ix_audit_logs_target", table_name="audit_logs")
    op.drop_index("ix_audit_logs_machine", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action_occurred", table_name="audit_logs")
    op.drop_index("ix_audit_logs_occurred", table_name="audit_logs")
    op.drop_constraint("ck_audit_logs_origin", "audit_logs", type_="check")
    op.drop_constraint("ck_audit_logs_action_type", "audit_logs", type_="check")
    op.drop_column("audit_logs", "occurred_at")
    op.drop_column("audit_logs", "detail")
    op.drop_column("audit_logs", "origin")
    op.drop_column("audit_logs", "machine_id")
    op.drop_column("audit_logs", "target_id")
    op.drop_column("audit_logs", "target_kind")
    op.drop_column("audit_logs", "action_type")
    op.drop_column("audit_logs", "actor_role")
    op.drop_column("audit_logs", "actor")
