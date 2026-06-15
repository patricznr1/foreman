"""failure predictions (F-PRED Ausfallvorhersage-Reasoner)

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-15

Legt die Tabelle `failure_predictions` an (GROUND_TRUTH §5) — persistierte
Ergebnisse des Ausfallvorhersage-Reasoners (F-PRED): Wahrscheinlichkeit,
kostensensitive Entscheidung, SHAP-Top-Faktoren (JSONB) und — strukturell
erzwungen (§16) — der Sim-Vorbehalt (`validation_status`/`data_regime`/
`model_version`). On-demand erzeugt; keine Aktorik. Lese-Index nach
(machine_id, created_at) fürs Dashboard/MCP.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "failure_predictions",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("machine_id", sa.BigInteger(), sa.ForeignKey("machines.id"), nullable=False),
        sa.Column("reference_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("horizon_h", sa.Integer(), nullable=False),
        sa.Column("probability", sa.Double(), nullable=False),
        sa.Column("decision_threshold", sa.Double(), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        # Pflicht-Vorbehalt (§16): einziger Wert 'simulation_only'.
        sa.Column("validation_status", sa.String(32), nullable=False),
        sa.Column("data_regime", sa.String(32), nullable=False),
        sa.Column("model_version", sa.String(128), nullable=False),
        sa.Column("top_factors", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
    )
    op.create_index(
        "ix_failure_predictions_machine_created",
        "failure_predictions",
        ["machine_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_failure_predictions_machine_created", table_name="failure_predictions")
    op.drop_table("failure_predictions")
