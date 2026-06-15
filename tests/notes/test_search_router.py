# ============================================================
#  FOREMAN — tests/notes/test_search_router.py
#  Zweck: HTTP-Vertrag der semantischen Suche (F-SEM, Baustein 4) —
#         GET /api/v1/worker_notes/search: Treffer-Reihenfolge, machine_id-Filter,
#         Auth-Pflicht, 503 bei Backend-Ausfall, 422-Validierung, und die
#         Regression, dass /worker_notes/{id} NICHT von /search geschattet wird.
#         Embedding-Provider via dependency_override (kein echtes Ollama).
# ============================================================
from __future__ import annotations

from collections.abc import Sequence

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from foreman.api.deps import get_embedding_provider
from foreman.config import Settings
from foreman.db.models import Machine, WorkerNote
from foreman.embeddings.errors import ProviderUnavailable
from foreman.embeddings.provider import Vector

_SEARCH = "/api/v1/worker_notes/search"
_DIM = 1024


def _unit(index: int) -> Vector:
    vec = [0.0] * _DIM
    vec[index] = 1.0
    return vec


_QUERY = _unit(0)


class _FixedProvider:
    """Liefert für jeden Text einen festen Vektor (deterministische Such-Reihenfolge)."""

    def __init__(self, vector: Vector) -> None:
        self._vector = vector

    async def embed(self, texts: Sequence[str]) -> list[Vector]:
        return [list(self._vector) for _ in texts]


class _FailProvider:
    """Simuliert ein nicht erreichbares Embedding-Backend (→ 503)."""

    async def embed(self, texts: Sequence[str]) -> list[Vector]:
        raise ProviderUnavailable("❌ kein Backend (Test)", attempted=("ollama",))


async def _seed(test_settings: Settings) -> tuple[int, int, int, int, int]:
    """Seedet (committed) zwei Maschinen + drei eingebettete Notizen."""
    engine = create_async_engine(test_settings.database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with maker() as session:
        m1 = Machine(label="CNC-1", machine_class="cnc")
        m2 = Machine(label="CNC-2", machine_class="cnc")
        session.add_all([m1, m2])
        await session.flush()
        a = WorkerNote(machine_id=m1.id, text="A identisch", embedding=_unit(0))
        b = WorkerNote(machine_id=m1.id, text="B orthogonal", embedding=_unit(1))
        c = WorkerNote(machine_id=m2.id, text="C gegen", embedding=[-1.0, *([0.0] * (_DIM - 1))])
        session.add_all([a, b, c])
        await session.flush()
        ids = (m1.id, m2.id, a.id, b.id, c.id)
        await session.commit()
    await engine.dispose()
    return ids


@pytest.mark.integration
async def test_search_route_liefert_treffer_in_reihenfolge(
    app: FastAPI, auth_client: AsyncClient, test_settings: Settings
) -> None:
    _, _, a_id, b_id, c_id = await _seed(test_settings)
    app.dependency_overrides[get_embedding_provider] = lambda: _FixedProvider(_QUERY)
    resp = await auth_client.get(_SEARCH, params={"q": "Lager heiß?", "k": 3})
    assert resp.status_code == 200, resp.text
    ids = [item["id"] for item in resp.json()]
    assert ids == [a_id, b_id, c_id]
    # Datenschutz: der Vektor wird NICHT ausgeliefert.
    assert "embedding" not in resp.json()[0]


@pytest.mark.integration
async def test_search_route_machine_id_filter(
    app: FastAPI, auth_client: AsyncClient, test_settings: Settings
) -> None:
    _, m2_id, _, _, c_id = await _seed(test_settings)
    app.dependency_overrides[get_embedding_provider] = lambda: _FixedProvider(_QUERY)
    resp = await auth_client.get(_SEARCH, params={"q": "x", "machine_id": m2_id})
    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()] == [c_id]


@pytest.mark.integration
async def test_search_route_braucht_auth(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_embedding_provider] = lambda: _FixedProvider(_QUERY)
    resp = await client.get(_SEARCH, params={"q": "x"})
    assert resp.status_code == 401


@pytest.mark.integration
async def test_search_route_backend_ausfall_503(
    app: FastAPI, auth_client: AsyncClient, test_settings: Settings
) -> None:
    await _seed(test_settings)
    app.dependency_overrides[get_embedding_provider] = lambda: _FailProvider()
    resp = await auth_client.get(_SEARCH, params={"q": "x"})
    assert resp.status_code == 503


@pytest.mark.integration
async def test_search_route_q_fehlt_422(app: FastAPI, auth_client: AsyncClient) -> None:
    app.dependency_overrides[get_embedding_provider] = lambda: _FixedProvider(_QUERY)
    resp = await auth_client.get(_SEARCH)  # ohne q
    assert resp.status_code == 422


@pytest.mark.integration
async def test_crud_get_note_nicht_von_search_geschattet(
    app: FastAPI, auth_client: AsyncClient, test_settings: Settings
) -> None:
    """Regression: die Such-Route verdeckt nicht GET /worker_notes/{note_id}."""
    _, _, a_id, _, _ = await _seed(test_settings)
    resp = await auth_client.get(f"/api/v1/worker_notes/{a_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == a_id
