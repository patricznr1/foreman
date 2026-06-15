# ============================================================
#  FOREMAN — tests/notes/test_search.py
#  Zweck: Semantische Notiz-Suche (F-SEM, Baustein 4) gegen die ECHTE DB mit
#         pgvector/HNSW — Ähnlichkeits-Reihenfolge (Cosine), machine_id-Filter,
#         k-Limit, NULL-Ausschluss, embed_and_search-Komposition + Index-Existenz.
#         Query-Vektor wird konstruiert (kein echtes Ollama).
# ============================================================
from __future__ import annotations

from collections.abc import Sequence

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import Machine, WorkerNote
from foreman.embeddings.provider import Vector
from foreman.notes import embed_and_search, search_similar_notes

_DIM = 1024


def _unit(index: int) -> Vector:
    """Einheitsvektor (1.0 an Position `index`, sonst 0) — L2-normiert."""
    vec = [0.0] * _DIM
    vec[index] = 1.0
    return vec


# Query [1,0,0,…]. Erwartete Cosine-Distanzen: identisch→0, orthogonal→1, gegen→2.
_QUERY = _unit(0)


class _FixedProvider:
    """Minimaler EmbeddingProvider, der für jeden Text einen festen Vektor liefert."""

    def __init__(self, vector: Vector) -> None:
        self._vector = vector

    async def embed(self, texts: Sequence[str]) -> list[Vector]:
        return [list(self._vector) for _ in texts]


async def _seed(
    session: AsyncSession,
) -> tuple[Machine, Machine, WorkerNote, WorkerNote, WorkerNote]:
    m1 = Machine(label="CNC-1", machine_class="cnc")
    m2 = Machine(label="CNC-2", machine_class="cnc")
    session.add_all([m1, m2])
    await session.flush()
    note_a = WorkerNote(machine_id=m1.id, text="A identisch", embedding=_unit(0))  # dist 0
    note_b = WorkerNote(machine_id=m1.id, text="B orthogonal", embedding=_unit(1))  # dist 1
    note_c = WorkerNote(
        machine_id=m2.id, text="C entgegengesetzt", embedding=[-1.0, *([0.0] * (_DIM - 1))]
    )  # dist 2
    note_null = WorkerNote(machine_id=m1.id, text="ohne Embedding", embedding=None)
    session.add_all([note_a, note_b, note_c, note_null])
    await session.flush()
    return m1, m2, note_a, note_b, note_c


@pytest.mark.integration
async def test_search_reihenfolge_nach_aehnlichkeit(db_session: AsyncSession) -> None:
    _, _, a, b, c = await _seed(db_session)
    results = await search_similar_notes(db_session, _QUERY, k=5)
    # NULL-Notiz ausgeschlossen; Reihenfolge identisch < orthogonal < entgegengesetzt.
    assert [n.id for n in results] == [a.id, b.id, c.id]


@pytest.mark.integration
async def test_search_machine_id_filter(db_session: AsyncSession) -> None:
    _, m2, _, _, c = await _seed(db_session)
    results = await search_similar_notes(db_session, _QUERY, machine_id=m2.id, k=5)
    assert [n.id for n in results] == [c.id]  # nur Maschine 2


@pytest.mark.integration
async def test_search_k_limitiert_die_treffer(db_session: AsyncSession) -> None:
    _, _, a, b, _ = await _seed(db_session)
    results = await search_similar_notes(db_session, _QUERY, k=2)
    assert [n.id for n in results] == [a.id, b.id]


@pytest.mark.integration
async def test_embed_and_search_embeddet_dann_sucht(db_session: AsyncSession) -> None:
    _, _, a, b, c = await _seed(db_session)
    provider = _FixedProvider(_QUERY)
    results = await embed_and_search(provider, db_session, "Lager läuft heiß?", k=3)
    assert [n.id for n in results] == [a.id, b.id, c.id]


@pytest.mark.integration
async def test_hnsw_index_existiert(raw_conn: asyncpg.Connection) -> None:
    row = await raw_conn.fetchrow(
        "SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_worker_notes_embedding_hnsw'"
    )
    assert row is not None
    indexdef = row["indexdef"].lower()
    assert "hnsw" in indexdef
    assert "vector_cosine_ops" in indexdef
