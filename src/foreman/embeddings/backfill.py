# ============================================================
#  FOREMAN — embeddings/backfill.py
#  Zweck: Idempotenter Backfill-Runner (F-SEM, Baustein 3) — zieht fehlende
#         worker_notes-Embeddings nach (`embedding IS NULL`), batcht sie und
#         schreibt die Vektoren zurück. Der „Nachhol"-Pfad zum best-effort-Insert:
#         war der Provider beim Schreiben nicht erreichbar, blieb `embedding=NULL`;
#         dieser Runner holt es nach.
#  Architektur-Einordnung: Vordergrund-Prozess (GROUND_TRUTH §3 — kein Job-Worker),
#         analog zum Simulations-Runner. Aufruf: `python -m foreman.embeddings.backfill`.
#  Idempotenz: nach dem Embedden ist `embedding` gesetzt → fällt aus dem
#         `IS NULL`-Filter; ein zweiter Lauf findet nichts mehr.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, keine PII/keine
#         Notiz-Texte/keine Vektoren in Logs.
# ============================================================
from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from foreman.config import get_settings
from foreman.db.models import WorkerNote
from foreman.embeddings.config import get_embedding_settings
from foreman.embeddings.provider import EmbeddingProvider, LocalEmbeddingProvider
from foreman.logging_setup import OK, get_logger

logger = get_logger("foreman.embeddings.backfill")


async def backfill_embeddings(
    session: AsyncSession, provider: EmbeddingProvider, *, batch_size: int
) -> int:
    """Embeddet alle worker_notes mit `embedding IS NULL` (idempotent, batchweise).

    Holt wiederholt den nächsten Batch noch nicht eingebetteter Notizen, embeddet
    deren (NER-maskierten) Text in EINEM Batch-Call und schreibt die Vektoren
    zurück. Gibt die Gesamtzahl nachgezogener Embeddings zurück. Anders als der
    Insert-Schreibpfad ist der Backfill NICHT best-effort: ein Provider-Fehler
    propagiert (der Operator soll ihn sehen) — bereits committete Batches bleiben.
    """
    if batch_size < 1:
        # batch_size=0 liefe still als No-Op (LIMIT 0 → keine Zeilen → sofortiger
        # break) trotz vorhandener NULL-Zeilen; negative Werte scheitern DB-seitig.
        raise ValueError(f"batch_size muss >= 1 sein (erhalten: {batch_size}).")
    total = 0
    while True:
        stmt = (
            select(WorkerNote)
            .where(WorkerNote.embedding.is_(None))
            .order_by(WorkerNote.id)
            .limit(batch_size)
        )
        notes = list(await session.scalars(stmt))
        if not notes:
            break
        vectors = await provider.embed([note.text for note in notes])
        for note, vector in zip(notes, vectors, strict=True):
            note.embedding = vector
        await session.commit()
        total += len(notes)
    return total


async def _run(
    *, batch_size: int | None = None, db_url: str | None = None
) -> int:  # pragma: no cover
    """IO-Schale: baut Provider + DB-Engine aus der Config und fährt den Backfill."""
    embed_settings = get_embedding_settings()
    resolved_batch = batch_size if batch_size is not None else embed_settings.batch_size
    url = db_url if db_url is not None else get_settings().database_url
    provider = LocalEmbeddingProvider.from_settings(embed_settings)
    engine = create_async_engine(url)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            written = await backfill_embeddings(session, provider, batch_size=resolved_batch)
    finally:
        await engine.dispose()
    logger.info("%s Backfill fertig: %d Notiz-Embeddings nachgezogen.", OK, written)
    return written


def main() -> None:  # pragma: no cover - CLI-Einstieg
    parser = argparse.ArgumentParser(
        description="Zieht fehlende worker_notes-Embeddings nach (idempotent)."
    )
    parser.add_argument(
        "--batch-size", type=int, default=None, help="Batch-Größe (Default aus der Config)."
    )
    parser.add_argument(
        "--db-url", type=str, default=None, help="DB-URL (Default aus der Config/.env)."
    )
    args = parser.parse_args()
    asyncio.run(_run(batch_size=args.batch_size, db_url=args.db_url))


if __name__ == "__main__":  # pragma: no cover
    main()
