# ============================================================
#  FOREMAN — notes/__init__.py
#  Zweck: Notiz-Such-Schicht über worker_notes. Öffentliche Fläche:
#         (A) Vektor-Suche (F-SEM): reine DB-Query (search_similar_notes) +
#             Komposition (embed_and_search, EmbeddingError ehrlich).
#         (B) Archiv-Hybrid (Paket 1a): deutscher Volltext + Vektor per RRF mit
#             Relevanz-Cutoff (hybrid_search_notes) + graceful Komposition
#             (embed_and_search_hybrid, degradiert auf Volltext statt 503).
#  Architektur-Einordnung: Schicht 2. Koppelt nur an `foreman.embeddings`
#         (EmbeddingProvider), nie an eine Embedding-Library.
# ============================================================
from __future__ import annotations

from foreman.notes.search import (
    DEFAULT_SEARCH_K,
    embed_and_search,
    embed_and_search_hybrid,
    hybrid_search_notes,
    search_similar_notes,
)

__all__ = [
    "DEFAULT_SEARCH_K",
    "embed_and_search",
    "embed_and_search_hybrid",
    "hybrid_search_notes",
    "search_similar_notes",
]
