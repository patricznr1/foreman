"""worker_notes embedding HNSW index (F-SEM, semantische Notiz-Suche)

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-14

Legt den HNSW-Index auf `worker_notes.embedding` an (GROUND_TRUTH §5/§15) — ab
F-SEM wird die Embedding-Spalte für die semantische Notiz-Auswahl genutzt (vorher
leer/ungenutzt, §14.3). Parameter aus `docs/research/vektor-suche-pgvector.md`:

  - Index-Typ HNSW (kontinuierliche Inserts ohne Rebuild — anders als IVFFlat),
  - Operator-Klasse `vector_cosine_ops` (Cosine-Distanz; Embeddings sind L2-normiert),
  - Bauparameter m = 16, ef_construction = 200 (Recall/Latenz-Balance, moderater Bestand).

Betriebs-Hinweis: Im laufenden Betrieb mit großem Bestand wird der Index per
`CREATE INDEX CONCURRENTLY` (außerhalb einer Transaktion) angelegt. Pflicht ist die
pgvector-EXTENSION ≥ 0.8.2 im Postgres-Image (CVE-2026-3172 bei parallelen HNSW-Builds)
— das ist die DB-/Deployment-Komponente, NICHT der Python-Adapter `pgvector` im
pyproject (der nur das SQLAlchemy-Mapping liefert und für HNSW/Cosine keine 0.8.x
braucht). In der Migration läuft der Index transaktional (wie die übrigen
FOREMAN-Migrationen) — beim MVP-Bestand unkritisch. `hnsw.ef_search` (Query-Zeit)
bleibt Session-/Server-Default (Start 40).
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

INDEX_NAME = "ix_worker_notes_embedding_hnsw"


def upgrade() -> None:
    op.execute(
        f"CREATE INDEX IF NOT EXISTS {INDEX_NAME} "
        "ON worker_notes USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 200);"
    )


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX_NAME};")
