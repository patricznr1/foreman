"""drift profiles (F4 Eigenprofil-Overlay — persistiertes zustandsspezifisches Normalband)

Legt `drift_profiles` an: je `data_point` EIN persistiertes Eigenprofil, am Laufende
des Drift-Reasoners (Reasoner #2) weggeschrieben. Trägt je Betriebszustand
(`state_key` = Tagesstunde) den gleitenden Median (`state_medians` JSONB) plus die EINE
robuste Rausch-Streuung `noise_sigma` und den Schwellenfaktor `effect_size_k` des
Datenpunkts — die echte Detektor-Bewertungsbasis, aus der die Read-Schicht je Trend-Bucket
den Korridor `median(state_key) ± effect_size_k · noise_sigma` expandiert.

Defense-in-Depth (§16.1-Linie): CHECK `noise_sigma > 0` / `effect_size_k > 0` weisen ein
geratenes Band an der Persistenzgrenze ab; Unique(`data_point_id`) ist das Upsert-Ziel.
FK CASCADE: das abgeleitete Profil verschwindet mit seinem Datenpunkt/seiner Maschine.

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-23
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "drift_profiles",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column(
            "data_point_id",
            sa.BigInteger(),
            sa.ForeignKey("data_points.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "machine_id",
            sa.BigInteger(),
            sa.ForeignKey("machines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("state_medians", postgresql.JSONB(), nullable=False),
        sa.Column("noise_sigma", sa.Double(), nullable=False),
        sa.Column("effect_size_k", sa.Double(), nullable=False),
        sa.Column("window_samples", sa.Integer(), nullable=False),
        sa.Column("warmup_samples", sa.Integer(), nullable=False),
        sa.Column("total_samples", sa.Integer(), nullable=False),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        # Genau ein Profil je Datenpunkt — Upsert-Ziel (ON CONFLICT data_point_id).
        sa.UniqueConstraint("data_point_id", name="uq_drift_profiles_data_point"),
        # Kein geratenes Band an der Persistenzgrenze (§16.1-Linie, Defense-in-Depth).
        sa.CheckConstraint("noise_sigma > 0", name="ck_drift_profiles_sigma_positive"),
        sa.CheckConstraint("effect_size_k > 0", name="ck_drift_profiles_k_positive"),
    )
    # Read-/Cockpit-Filter je Maschine.
    op.create_index("ix_drift_profiles_machine", "drift_profiles", ["machine_id"])


def downgrade() -> None:
    op.drop_index("ix_drift_profiles_machine", table_name="drift_profiles")
    op.drop_table("drift_profiles")
