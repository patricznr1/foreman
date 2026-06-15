# ============================================================
#  FOREMAN — notes/__init__.py
#  Zweck: Semantische Notiz-Suche (F-SEM) — die Such-Schicht über
#         worker_notes.embedding (HNSW/Cosine). Öffentliche Fläche: die reine
#         DB-Query (search_similar_notes, Vektor rein) + die Komposition
#         (embed_and_search, embeddet erst den Query-Text).
#  Architektur-Einordnung: Schicht 2. Koppelt nur an `foreman.embeddings`
#         (EmbeddingProvider), nie an eine Embedding-Library.
# ============================================================
from __future__ import annotations

from foreman.notes.search import DEFAULT_SEARCH_K, embed_and_search, search_similar_notes

__all__ = [
    "DEFAULT_SEARCH_K",
    "embed_and_search",
    "search_similar_notes",
]
