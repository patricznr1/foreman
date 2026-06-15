# ============================================================
#  FOREMAN — tests/embeddings/test_backfill.py
#  Zweck: Backfill-Runner (F-SEM, Baustein 2) gegen die ECHTE DB — nur NULL-Zeilen,
#         Idempotenz (zweiter Lauf findet nichts), Batch-Verarbeitung. Provider über
#         das Mock-Backend (kein echtes Ollama).
# ============================================================
from __future__ import annotations

from collections.abc import Callable

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import WorkerNote
from foreman.embeddings import LocalEmbeddingProvider
from foreman.embeddings.backfill import backfill_embeddings

MakeProvider = Callable[..., LocalEmbeddingProvider]
MakeBackend = Callable[..., object]


async def _null_count(session: AsyncSession) -> int:
    stmt = select(func.count()).select_from(WorkerNote).where(WorkerNote.embedding.is_(None))
    return int((await session.scalar(stmt)) or 0)


async def _seed_notes(session: AsyncSession, n_without: int, *, n_with: int = 0) -> None:
    for i in range(n_without):
        session.add(WorkerNote(text=f"Notiz ohne Embedding {i}", shift="frueh"))
    for i in range(n_with):
        # Bereits embeddete Notiz (darf NICHT erneut angefasst werden).
        session.add(WorkerNote(text=f"Notiz mit Embedding {i}", embedding=[0.0] * 1024))
    await session.commit()


@pytest.mark.integration
async def test_backfill_embeddet_nur_null_zeilen(
    db_session: AsyncSession,
    make_provider: MakeProvider,
    make_embed_backend: MakeBackend,
) -> None:
    await _seed_notes(db_session, n_without=2, n_with=1)
    provider = make_provider(
        backends=[make_embed_backend("ollama", dim=1024)], priority="ollama_only"
    )

    written = await backfill_embeddings(db_session, provider, batch_size=10)

    assert written == 2  # nur die zwei NULL-Zeilen, nicht die bereits embeddete
    assert await _null_count(db_session) == 0


@pytest.mark.integration
async def test_backfill_ist_idempotent(
    db_session: AsyncSession,
    make_provider: MakeProvider,
    make_embed_backend: MakeBackend,
) -> None:
    await _seed_notes(db_session, n_without=3)
    provider = make_provider(
        backends=[make_embed_backend("ollama", dim=1024)], priority="ollama_only"
    )

    first = await backfill_embeddings(db_session, provider, batch_size=10)
    second = await backfill_embeddings(db_session, provider, batch_size=10)

    assert first == 3
    assert second == 0  # zweiter Lauf findet nichts mehr


@pytest.mark.integration
async def test_backfill_verarbeitet_in_batches(
    db_session: AsyncSession,
    make_provider: MakeProvider,
    make_embed_backend: MakeBackend,
) -> None:
    await _seed_notes(db_session, n_without=5)
    backend = make_embed_backend("ollama", dim=1024)
    provider = make_provider(backends=[backend], priority="ollama_only")

    written = await backfill_embeddings(db_session, provider, batch_size=2)

    assert written == 5
    # 5 Notizen / Batch 2 → 3 Batch-Calls (2 + 2 + 1).
    assert backend.calls == 3  # type: ignore[attr-defined]


@pytest.mark.integration
async def test_backfill_lehnt_batch_size_kleiner_eins_ab(
    db_session: AsyncSession,
    make_provider: MakeProvider,
    make_embed_backend: MakeBackend,
) -> None:
    provider = make_provider(
        backends=[make_embed_backend("ollama", dim=1024)], priority="ollama_only"
    )
    with pytest.raises(ValueError, match="batch_size"):
        await backfill_embeddings(db_session, provider, batch_size=0)
