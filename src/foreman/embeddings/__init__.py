# ============================================================
#  FOREMAN — embeddings/__init__.py
#  Zweck: Öffentliche Schnittstelle der Embedding-Schicht (F-SEM). Das ist die
#         EINZIGE Fläche, die ein Aufrufer (Ingestion, Suche, Ereignisketten-
#         Reasoner) berührt — das EmbeddingProvider-Protokoll + die konkrete
#         LocalEmbeddingProvider-Implementierung, der Vector-Typ, die
#         Embedding-Settings und die Fehlerhierarchie. Kein Export exponiert einen
#         Backend-/Library-Typ (Ollama/httpx, sentence-transformers) — harte
#         Architektur-Grenze des Briefings; die Libraries leben ausschließlich in
#         backends.py.
#  Architektur-Einordnung: Schicht 2 — die parallele, gleich geformte Schicht zum
#         LLM-Gateway (§13). Embeddings sind ein anderer Pfad als Completion und
#         gehören NICHT ins LLMGateway gequetscht.
# ============================================================
from __future__ import annotations

from foreman.embeddings.config import EmbeddingSettings, Priority, get_embedding_settings
from foreman.embeddings.errors import (
    DimensionMismatch,
    EmbeddingError,
    EmbeddingTimeout,
    ProviderUnavailable,
)
from foreman.embeddings.provider import (
    EmbeddingProvider,
    LocalEmbeddingProvider,
    Vector,
    embed_best_effort,
)

# Öffentliche Aufrufer-Schnittstelle (sortiert; Gruppen: Provider, Config,
# Fehlerhierarchie — Details im Modul-Header). KEINE Backend-/Library-Typen.
__all__ = [
    "DimensionMismatch",
    "EmbeddingError",
    "EmbeddingProvider",
    "EmbeddingSettings",
    "EmbeddingTimeout",
    "LocalEmbeddingProvider",
    "Priority",
    "ProviderUnavailable",
    "Vector",
    "embed_best_effort",
    "get_embedding_settings",
]
