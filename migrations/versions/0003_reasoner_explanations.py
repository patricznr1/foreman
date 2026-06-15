"""reasoner explanations (F6 Ereignisketten-Reasoner)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-14

Legt die Tabelle `reasoner_explanations` an (GROUND_TRUTH §5) — persistierte
Ergebnisse der LLM-Reasoner (zuerst Ereignisketten, F6): Anker-Referenz, Erzähltext,
referenzierte/geflaggte Quellen, Konfidenz-/Hypothese-Markierung, Grounding-Befund.
Reasoner-übergreifend (Spalte `reasoner`), abfragbar fürs Dashboard/MCP. Die
Reasoner-Erklärung ist ein diskretes Ereignis und wird zusätzlich als
`semantic_event` ans Substrat gespiegelt (§12.4, kein eigenes Schema hier).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "reasoner_explanations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("anchor_alarm_id", sa.BigInteger(), sa.ForeignKey("alarms.id"), nullable=False),
        sa.Column("machine_id", sa.BigInteger(), sa.ForeignKey("machines.id"), nullable=True),
        sa.Column(
            "reasoner",
            sa.String(64),
            nullable=False,
            server_default=sa.text("'event_chain'"),
        ),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("referenced_source_ids", postgresql.JSONB(), nullable=False),
        sa.Column(
            "flagged_unsupported",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("is_hypothesis", sa.Boolean(), nullable=False),
        sa.Column("confidence", sa.String(16), nullable=False),
        sa.Column("grounded", sa.Boolean(), nullable=True),
        sa.Column("recall_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
    )
    op.create_index("ix_reasoner_explanations_anchor", "reasoner_explanations", ["anchor_alarm_id"])
    op.create_index(
        "ix_reasoner_explanations_machine_created",
        "reasoner_explanations",
        ["machine_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_reasoner_explanations_machine_created", table_name="reasoner_explanations")
    op.drop_index("ix_reasoner_explanations_anchor", table_name="reasoner_explanations")
    op.drop_table("reasoner_explanations")
