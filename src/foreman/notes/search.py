# ============================================================
#  FOREMAN — notes/search.py
#  Zweck: Semantische Notiz-Suche (F-SEM, Baustein 4) über worker_notes.embedding.
#         Zwei Ebenen, bewusst getrennt:
#         - `search_similar_notes`: REINE DB-Query mit einem FERTIGEN Query-Vektor
#           (kein Provider, kein Netz → ohne Embedding-Backend testbar). Cosine-
#           Distanz über den HNSW-Index (Migration 0004, vector_cosine_ops).
#         - `embed_and_search`: Komposition — embeddet erst den Query-Text über den
#           EmbeddingProvider, sucht dann.
#  Architektur-Einordnung: Schicht 2. Koppelt nur an `foreman.embeddings`
#         (EmbeddingProvider/Vector), nie an eine Embedding-Library. Reine,
#         DI-getriebene Funktionen (Session/Provider injiziert, §6).
#  Sicherheit: nur strukturierte Felder zurück; der Notiz-`text` bleibt untrusted
#         Freitext (die Suche ändert nur WELCHE Notizen kommen, nicht WIE sie
#         behandelt werden — §14.1/§15).
# ============================================================
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import WorkerNote
from foreman.embeddings.provider import EmbeddingProvider, Vector

# Default-Trefferzahl der semantischen Suche.
DEFAULT_SEARCH_K = 5


async def search_similar_notes(
    session: AsyncSession,
    query_embedding: Vector,
    *,
    machine_id: int | None = None,
    k: int = DEFAULT_SEARCH_K,
) -> list[WorkerNote]:
    """Liefert die `k` ähnlichsten Notizen zu einem FERTIGEN Query-Vektor (Cosine).

    Reine DB-Query — der Query-Vektor wird übergeben (kein Provider/Netz), damit die
    Selektion ohne Embedding-Backend testbar ist. Nur Notizen MIT Embedding sind
    Kandidaten (`embedding IS NOT NULL`); optional auf eine Maschine gefiltert.
    Sortiert nach Cosine-Distanz (HNSW-Index `vector_cosine_ops`, Migration 0004).
    """
    stmt = select(WorkerNote).where(WorkerNote.embedding.is_not(None))
    if machine_id is not None:
        stmt = stmt.where(WorkerNote.machine_id == machine_id)
    stmt = stmt.order_by(WorkerNote.embedding.cosine_distance(query_embedding)).limit(k)
    return list(await session.scalars(stmt))


async def embed_and_search(
    provider: EmbeddingProvider,
    session: AsyncSession,
    query_text: str,
    *,
    machine_id: int | None = None,
    k: int = DEFAULT_SEARCH_K,
) -> list[WorkerNote]:
    """Komposition: embeddet erst den Query-Text, sucht dann die ähnlichsten Notizen.

    Anders als `search_similar_notes` berührt diese Funktion den Provider (Netz/
    Modell) und kann daher einen `EmbeddingError` werfen — der Aufrufer entscheidet,
    ob das ehrlich durchgereicht (Such-Route → 503) oder best-effort gefangen wird
    (Ereignisketten-Reasoner → Zeitfenster-Fallback, §15).
    """
    vectors = await provider.embed([query_text])
    return await search_similar_notes(session, vectors[0], machine_id=machine_id, k=k)
