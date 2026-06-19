"""event chain + siblings snapshot (F5-FE Sektion D)

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-19

Fügt `reasoner_explanations` zwei nullable JSONB-Snapshot-Spalten hinzu:
`chain_snapshot` (serialisierte `EventChain` — die zeitlich geordnete Ereigniskette
rund um den Anker) und `siblings_snapshot` (Liste ehrlicher `SiblingReference` aus
realen NEXUS-Recall-Treffern). Begründung (§21-D): Die Kette + die Schwester-Bezüge
werden zur Rekonstruktions-Zeit bereits voll berechnet, aber bislang nicht
persistiert. Gespeicherte Erklärungen sollen die Timeline EINGEFROREN behalten
(„Momentaufnahme mit Stand", Designstudie §3.2 Pin/Persist) — Quelldaten (Alarme,
Notizen, Wartungen, das Substrat) können sich später ändern; ein Re-Fetch darf die
gezeigte Kette nicht still verschieben. JSONB-Snapshot statt FK-Ketten-Tabelle:
die Kette ist eine reine Momentaufnahme ohne eigenen Lebenszyklus, atomar mit der
Erklärungszeile, konsistent mit dem bestehenden JSONB-Muster der Tabelle
(`referenced_source_ids`/`flagged_unsupported`). Nullable → Bestandsdatensätze
bleiben gültig (liefern `chain=None`/`siblings=[]`).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "reasoner_explanations",
        sa.Column("chain_snapshot", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "reasoner_explanations",
        sa.Column("siblings_snapshot", postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("reasoner_explanations", "siblings_snapshot")
    op.drop_column("reasoner_explanations", "chain_snapshot")
