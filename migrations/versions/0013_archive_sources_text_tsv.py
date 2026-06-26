"""Archiv-Quellen Wartung + Alarme: deutsche Volltext-Spuren (text_tsv generated + GIN)

Erweitert das Archiv (Paket 1b) um zwei weitere durchsuchbare Quellen — additiv zur
worker_notes-Spur aus Migration `0012` (1a, unangetastet). Je Tabelle eine generierte,
persistierte deutsche Volltext-Spalte + GIN-Index. Der FREITEXT trägt primär
(`description` / `message`), die strukturierten Codes (`type` / `code`) ergänzen den
durchsuchbaren Vektor:

  - maintenance_events.text_tsv = to_tsvector('german', coalesce(description,'') || ' ' || coalesce(type,''))
  - alarms.text_tsv            = to_tsvector('german', coalesce(message,'')     || ' ' || coalesce(code,''))

'german' als konstante regconfig → der Ausdruck ist IMMUTABLE (Pflicht für GENERATED).
Die Spalten werden vom Schreibpfad NIE angefasst (kein ORM-Attribut nötig; die
Volltext-Query liest `text_tsv` direkt in rohem SQL). GIN-Index ist der Standard für
`@@` / `ts_rank`.

Betriebs-Hinweis: Beim MVP-Bestand läuft `CREATE INDEX` regulär transaktional. Bei
großem Bestand wäre der Index im laufenden Betrieb per `CREATE INDEX CONCURRENTLY`
außerhalb einer Transaktion anzulegen (eigene, nicht-transaktionale Migration) — hier
bewusst nicht nötig. pgvector/HNSW unberührt (Alarme/Wartung tragen kein Embedding).

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-26
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (Tabelle, Volltext-Ausdruck, Index-Name) — Freitext primär, Code ergänzend.
_SOURCES = (
    (
        "maintenance_events",
        "to_tsvector('german', coalesce(description,'') || ' ' || coalesce(type,''))",
        "ix_maintenance_events_text_tsv_gin",
    ),
    (
        "alarms",
        "to_tsvector('german', coalesce(message,'') || ' ' || coalesce(code,''))",
        "ix_alarms_text_tsv_gin",
    ),
)


def upgrade() -> None:
    for table, expression, index_name in _SOURCES:
        op.execute(
            f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS text_tsv tsvector "
            f"GENERATED ALWAYS AS ({expression}) STORED;"
        )
        op.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} USING gin (text_tsv);")


def downgrade() -> None:
    for table, _expression, index_name in _SOURCES:
        op.execute(f"DROP INDEX IF EXISTS {index_name};")
        op.execute(f"ALTER TABLE {table} DROP COLUMN IF EXISTS text_tsv;")
