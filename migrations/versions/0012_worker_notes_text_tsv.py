"""worker_notes deutsche Volltext-Spur (text_tsv generated column + GIN) — Archiv-Hybrid

Legt die lexikalische Spur für die hybride Archiv-Suche an (Paket 1a). **Additiv** zur
HNSW-Vektor-Spur aus Migration `0004` — der HNSW-Index auf `worker_notes.embedding`
bleibt vollständig unangetastet (Vektor- und Volltext-Zweig laufen nebeneinander, per
RRF fusioniert; Quelle: `docs/research/vektor-suche-pgvector.md` §5).

  - `text_tsv` = `tsvector GENERATED ALWAYS AS (to_tsvector('german', coalesce(text, ''))) STORED`:
    DB-seitig erzeugte, persistierte Spalte. Deutsche FTS-Konfiguration (`'german'` als
    konstante `regconfig` → der Ausdruck ist IMMUTABLE, Pflicht für generierte Spalten).
    `coalesce(text, '')` ist defensiv (Spalte ist NOT NULL, aber so bricht ein künftiger
    NULL-Pfad die Generierung nicht). Der Schreibpfad fasst die Spalte NIE an (kein
    ORM-Attribut nötig — die Hybrid-Query referenziert `text_tsv` direkt in rohem SQL).
  - GIN-Index `ix_worker_notes_text_tsv_gin` auf `text_tsv` (Standard-Index für `@@`/`ts_rank`).

Betriebs-Hinweis: Beim kleinen MVP-Bestand läuft `CREATE INDEX` regulär **transaktional**
(wie die übrigen FOREMAN-Migrationen) — unkritisch. Bei großem Bestand wäre der Index im
laufenden Betrieb per `CREATE INDEX CONCURRENTLY` **außerhalb einer Transaktion** anzulegen
(Schreibsperren vermeiden); das verlangt eine eigene, nicht-transaktionale Migration und ist
hier bewusst nicht nötig. pgvector-Version bleibt unverändert (keine HNSW-Berührung).

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-26
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

COLUMN_NAME = "text_tsv"
INDEX_NAME = "ix_worker_notes_text_tsv_gin"


def upgrade() -> None:
    # Generierte, persistierte deutsche Volltext-Spur (immutable: 'german' als Konstante).
    op.execute(
        f"ALTER TABLE worker_notes ADD COLUMN IF NOT EXISTS {COLUMN_NAME} tsvector "
        "GENERATED ALWAYS AS (to_tsvector('german', coalesce(text, ''))) STORED;"
    )
    # GIN-Index für den Volltext-Zweig der Hybrid-Query (`@@` / `ts_rank`).
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {INDEX_NAME} ON worker_notes USING gin ({COLUMN_NAME});"
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME};")
    op.execute(f"ALTER TABLE worker_notes DROP COLUMN IF EXISTS {COLUMN_NAME};")
