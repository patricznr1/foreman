"""failure predictions check constraints (F-PRED Sim-Vorbehalt an der Persistenzgrenze)

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-15

Härtet das Kern-Deliverable der strukturellen Ehrlichkeit (§16.1): der Sim-Vorbehalt
(`validation_status='simulation_only'`, `data_regime='simulation'`) und die gültige
Entscheidung werden zusätzlich durch DB-CHECK-Constraints an der Persistenzgrenze
erzwungen — nicht nur app-seitig (Pydantic). Ein pydantic-umgehender Direkt-Insert
mit Fremdwert wird damit von der Datenbank abgewiesen (Defense-in-Depth).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_failure_predictions_validation_status",
        "failure_predictions",
        "validation_status = 'simulation_only'",
    )
    op.create_check_constraint(
        "ck_failure_predictions_data_regime",
        "failure_predictions",
        "data_regime = 'simulation'",
    )
    op.create_check_constraint(
        "ck_failure_predictions_decision",
        "failure_predictions",
        "decision IN ('elevated_risk', 'normal')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_failure_predictions_decision", "failure_predictions", type_="check")
    op.drop_constraint("ck_failure_predictions_data_regime", "failure_predictions", type_="check")
    op.drop_constraint(
        "ck_failure_predictions_validation_status", "failure_predictions", type_="check"
    )
