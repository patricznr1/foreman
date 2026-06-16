"""failure recommendations (F-REC LLM-Werker-Empfehlung über der Vorhersage)

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-16

Legt die Tabelle `failure_recommendations` an (F-REC) mit FK auf
`failure_predictions`. Persistiert die gegroundete, deutsche LLM-Werker-Empfehlung
inkl. des DETERMINISTISCHEN Sim-Vorbehalts (`validation_caveat`, nicht LLM-generiert)
und der aus der Vorhersage mitgeführten autoritativen Zahlen (Wahrscheinlichkeit /
Horizont / Entscheidung). Defense-in-Depth (§16.1): der Sim-Vorbehalt + die gültige
Entscheidung werden zusätzlich durch DB-CHECK-Constraints an der Persistenzgrenze
erzwungen — ein pydantic-umgehender Direkt-Insert mit Fremdwert wird abgewiesen.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "failure_recommendations",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "prediction_id",
            sa.BigInteger(),
            sa.ForeignKey("failure_predictions.id"),
            nullable=False,
        ),
        sa.Column("machine_id", sa.BigInteger(), sa.ForeignKey("machines.id"), nullable=False),
        sa.Column("recommendation_text", sa.Text(), nullable=False),
        # validation_caveat: deterministischer Sim-Vorbehalt (Invariante II, nicht LLM).
        sa.Column("validation_caveat", sa.Text(), nullable=False),
        # Pflicht-Vorbehalt (§16): einziger Wert 'simulation_only'.
        sa.Column("validation_status", sa.String(32), nullable=False),
        sa.Column("data_regime", sa.String(32), nullable=False),
        sa.Column("model_version", sa.String(128), nullable=False),
        sa.Column("referenced_source_ids", postgresql.JSONB(), nullable=False),
        # Autoritative Zahlen aus der Vorhersage (Invariante I) — nie aus dem LLM.
        sa.Column("horizon_h", sa.Integer(), nullable=False),
        sa.Column("probability", sa.Double(), nullable=False),
        sa.Column("decision", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_NOW, nullable=False),
        # Defense-in-Depth (§16.1): Sim-Vorbehalt + gültige Entscheidung an der DB-Grenze.
        sa.CheckConstraint(
            "validation_status = 'simulation_only'",
            name="ck_failure_recommendations_validation_status",
        ),
        sa.CheckConstraint(
            "data_regime = 'simulation'", name="ck_failure_recommendations_data_regime"
        ),
        sa.CheckConstraint(
            "decision IN ('elevated_risk', 'normal')", name="ck_failure_recommendations_decision"
        ),
        # Der Vorbehalts-TEXT (das beim Werker ankommende Feld) muss den Sim-Marker
        # tragen — ein umgedeuteter Caveat (ohne 'simuliert') wird abgewiesen. Bewusst
        # marker-basiert statt exakter Text-Bindung: robust gegen Satz-Pflege, fängt aber
        # die Umdeutung (Invariante II an der Persistenzgrenze). Die App-Garantie bleibt
        # der Schema-Validator (validation_caveat_for); dies ist die zweite Linie.
        sa.CheckConstraint(
            "validation_caveat LIKE '%simuliert%'",
            name="ck_failure_recommendations_validation_caveat",
        ),
    )
    op.create_index(
        "ix_failure_recommendations_prediction",
        "failure_recommendations",
        ["prediction_id"],
    )
    op.create_index(
        "ix_failure_recommendations_machine_created",
        "failure_recommendations",
        ["machine_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_failure_recommendations_machine_created", table_name="failure_recommendations"
    )
    op.drop_index("ix_failure_recommendations_prediction", table_name="failure_recommendations")
    op.drop_table("failure_recommendations")
