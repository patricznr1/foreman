# ============================================================
#  FOREMAN — notes/search.py
#  Zweck: Notiz-Suche über worker_notes. Zwei Familien, bewusst getrennt:
#         (A) Vektor-Suche (F-SEM, F6-Anbindung):
#         - `search_similar_notes`: REINE DB-Query mit einem FERTIGEN Query-Vektor
#           (kein Provider, kein Netz → ohne Embedding-Backend testbar). Cosine-
#           Distanz über den HNSW-Index (Migration 0004, vector_cosine_ops).
#         - `embed_and_search`: Komposition — embeddet erst den Query-Text, sucht dann.
#           Reicht EmbeddingError EHRLICH durch (Such-Route → 503; F6 → best-effort).
#         (B) Archiv-Hybrid (Paket 1a):
#         - `hybrid_search_notes`: REINE DB-Query, deutscher Volltext (text_tsv/GIN,
#           Migration 0012) + optionaler Vektor-Zweig, per RRF (k=60) fusioniert, mit
#           Relevanz-Cutoff. Vektor optional → ohne Embedding-Backend lauffähig.
#         - `embed_and_search_hybrid`: Komposition mit GRACEFUL DEGRADATION — fällt das
#           Embedding-Backend aus, trägt der Volltext-Zweig allein (kein 503).
#  Architektur-Einordnung: Schicht 2. Koppelt nur an `foreman.embeddings`
#         (EmbeddingProvider/Vector), nie an eine Embedding-Library. Reine,
#         DI-getriebene Funktionen (Session/Provider injiziert, §6).
#  Sicherheit: nur strukturierte Felder zurück; der Notiz-`text` bleibt untrusted
#         Freitext (die Suche ändert nur WELCHE Notizen kommen, nicht WIE sie
#         behandelt werden — §14.1/§15).
# ============================================================
from __future__ import annotations

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import WorkerNote
from foreman.embeddings.errors import EmbeddingError
from foreman.embeddings.provider import EmbeddingProvider, Vector
from foreman.logging_setup import RETRY, get_logger

logger = get_logger("foreman.notes.search")

# Default-Trefferzahl der semantischen Suche.
DEFAULT_SEARCH_K = 5

# Reciprocal-Rank-Fusion-Konstante (Cormack 2009): dämpft den Einfluss tiefer Ränge;
# k=60 ist der De-facto-Standard für Hybrid-Retrieval (docs/research/vektor-suche-pgvector.md §5).
RRF_K = 60
# Kandidaten-Pool je Zweig vor der Fusion (Volltext bzw. Vektor je bis zu so viele Treffer).
CANDIDATE_POOL = 50


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


def _vector_literal(vector: Vector) -> str:
    """Serialisiert einen Vektor ins pgvector-Textformat `[v1,v2,…]`.

    Über `CAST(:q_vec AS vector)` (automatischer I/O-Konvertierungs-Cast von Text zur
    pgvector-Typklasse) gebunden — unabhängig von asyncpg-Typ-Inferenz. `str(float(x))`
    hält die volle Round-Trip-Präzision (Python ≥ 3.1).
    """
    return "[" + ",".join(str(float(component)) for component in vector) + "]"


async def hybrid_search_notes(
    session: AsyncSession,
    query_text: str,
    *,
    query_embedding: Vector | None,
    machine_id: int | None = None,
    k: int = DEFAULT_SEARCH_K,
    max_distance: float,
) -> list[WorkerNote]:
    """Hybride Archiv-Suche: deutscher Volltext + Vektor, per RRF fusioniert, mit Cutoff.

    REINE DB-Funktion (kein Provider/Netz — wie `search_similar_notes` ohne Embedding-
    Backend testbar). Zwei Zweige gegen denselben Kandidatenraum, `machine_id` als harter
    Filter in BEIDEN Zweigen (falls gesetzt):
      • Volltext: `websearch_to_tsquery('german', …)` gegen `text_tsv`, Rang via `ts_rank`.
      • Vektor (nur wenn `query_embedding` gesetzt): Cosine-Distanz (`<=>`) gegen `embedding`.
    Fusion per Reciprocal Rank Fusion (k=60); Ergebnis-Reihenfolge = fusionierter Rang.

    RELEVANZ-CUTOFF (der Riegel gegen das Müll-Auffüllen): ein Kandidat bleibt nur, wenn
    er (a) einen Volltext-Match hat ODER (b) seine Vektor-Distanz unter `max_distance`
    liegt. Reine Vektor-Treffer oberhalb der Schwelle fallen raus — exakte Wörter kommen
    über den Volltext garantiert rein, semantisch-vages Zeug bleibt draußen.

    GRACEFUL DEGRADATION: ist `query_embedding` None (Embedding-Backend ausgefallen),
    trägt der Volltext-Zweig allein (kein Vektor-Zweig, kein Distanz-Cutoff). Matcht auch
    der Volltext nichts, ist das Ergebnis regulär leer.

    Die Roh-SQL liefert nur die `id`s in Relevanz-Reihenfolge; die Notiz-Objekte werden
    danach geladen und in genau diese Reihenfolge gebracht (Vertrag: `list[WorkerNote]`,
    KEIN Score nach außen).
    """
    machine_filter = " AND machine_id = :machine_id" if machine_id is not None else ""
    params: dict[str, object] = {"q_text": query_text, "k": k}

    if query_embedding is not None:
        params["q_vec"] = _vector_literal(query_embedding)
        params["candidate_pool"] = max(CANDIDATE_POOL, k)
        params["max_distance"] = max_distance
        params["rrf_k"] = RRF_K
        sql = f"""
            WITH vector_hits AS (
                SELECT id,
                       row_number() OVER (ORDER BY embedding <=> CAST(:q_vec AS vector)) AS rnk,
                       (embedding <=> CAST(:q_vec AS vector)) AS distance
                FROM worker_notes
                WHERE embedding IS NOT NULL{machine_filter}
                ORDER BY embedding <=> CAST(:q_vec AS vector)
                LIMIT :candidate_pool
            ),
            fulltext_hits AS (
                SELECT id,
                       row_number() OVER (
                           ORDER BY ts_rank(text_tsv, websearch_to_tsquery('german', :q_text)) DESC
                       ) AS rnk
                FROM worker_notes
                WHERE text_tsv @@ websearch_to_tsquery('german', :q_text){machine_filter}
                LIMIT :candidate_pool
            )
            SELECT COALESCE(v.id, f.id) AS id
            FROM vector_hits v
            FULL OUTER JOIN fulltext_hits f ON v.id = f.id
            WHERE f.id IS NOT NULL OR v.distance < :max_distance
            ORDER BY (COALESCE(1.0 / (:rrf_k + v.rnk), 0.0)
                      + COALESCE(1.0 / (:rrf_k + f.rnk), 0.0)) DESC,
                     COALESCE(v.id, f.id) ASC
            LIMIT :k
        """
    else:
        # Degradierter Pfad: nur Volltext (Embedding-Backend nicht verfügbar). Alle
        # Treffer sind Volltext-Matches → der Cutoff (a) ist per Konstruktion erfüllt.
        sql = f"""
            SELECT id
            FROM worker_notes
            WHERE text_tsv @@ websearch_to_tsquery('german', :q_text){machine_filter}
            ORDER BY ts_rank(text_tsv, websearch_to_tsquery('german', :q_text)) DESC, id ASC
            LIMIT :k
        """

    if machine_id is not None:
        params["machine_id"] = machine_id

    result = await session.execute(text(sql), params)
    ordered_ids: list[int] = [int(note_id) for note_id in result.scalars()]
    if not ordered_ids:
        return []

    notes = await session.scalars(select(WorkerNote).where(WorkerNote.id.in_(ordered_ids)))
    by_id: dict[int, WorkerNote] = {note.id: note for note in notes}
    # Die Roh-SQL-Reihenfolge (RRF-Rang) ist maßgeblich — die IN-Abfrage gibt sie nicht her.
    return [by_id[note_id] for note_id in ordered_ids if note_id in by_id]


async def embed_and_search_hybrid(
    provider: EmbeddingProvider,
    session: AsyncSession,
    query_text: str,
    *,
    machine_id: int | None = None,
    k: int = DEFAULT_SEARCH_K,
    max_distance: float,
) -> list[WorkerNote]:
    """Komposition für die Archiv-Suche: Query einbetten, dann hybrid suchen.

    Anders als `embed_and_search` (das den `EmbeddingError` ehrlich als 503 durchreicht)
    degradiert diese Funktion **graceful**: fällt das Embedding-Backend aus, sucht der
    Volltext-Zweig allein weiter (KEIN 503). Das Archiv muss auch ohne Embedding-Backend
    funktionieren (Standalone-Argument). `max_distance` steuert den Relevanz-Cutoff.
    """
    query_embedding: Vector | None
    try:
        query_embedding = (await provider.embed([query_text]))[0]
    except EmbeddingError as exc:
        # Graceful: kein Vektor-Zweig, Volltext trägt allein. Kein Query-Text/keine PII im Log (§15.7).
        logger.warning(
            "%s Archiv-Suche degradiert auf Volltext (Embedding-Backend nicht verfügbar): %s",
            RETRY,
            exc,
        )
        query_embedding = None

    return await hybrid_search_notes(
        session,
        query_text,
        query_embedding=query_embedding,
        machine_id=machine_id,
        k=k,
        max_distance=max_distance,
    )
