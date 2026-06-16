"""user subscription scope (F5 WS-Abo-Autorisierung)

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-16

Fügt `users` zwei Scope-Spalten hinzu: `assigned_line_ids` + `assigned_machine_ids`
(BIGINT[], Default leeres Array). Grundlage der WebSocket-Abo-Autorisierung (F5):
die Sichtbarkeit folgt der Rollenmatrix (Designstudie 3.1) — ein `worker` sieht nur
seine Maschinen (assigned_machine_ids), ein `shift_lead` nur seine Linien
(assigned_line_ids); `manager`/`technician` sind unrestricted und ignorieren die
Felder. Leeres Array = kein Scope → default-deny für die beschränkten Rollen, damit
ein authentifizierter Client nicht jedes Maschinen-Thema mithören kann (PII-Pfad).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_EMPTY_BIGINT_ARRAY = sa.text("'{}'::bigint[]")


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "assigned_line_ids",
            postgresql.ARRAY(sa.BigInteger()),
            nullable=False,
            server_default=_EMPTY_BIGINT_ARRAY,
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "assigned_machine_ids",
            postgresql.ARRAY(sa.BigInteger()),
            nullable=False,
            server_default=_EMPTY_BIGINT_ARRAY,
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "assigned_machine_ids")
    op.drop_column("users", "assigned_line_ids")
