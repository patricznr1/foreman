# ============================================================
#  FOREMAN — tests/archive/test_archive_router.py
#  Zweck: HTTP-Vertrag der quellenübergreifenden Archiv-Suche (Paket 1b) —
#         GET /api/v1/archive/search: ArchiveHit als FLACHE Liste OHNE Score-Feld,
#         Quellen-Filter (CSV + wiederholbar + Default alle), machine_id-Filter,
#         422 bei unbekannter Quelle / fehlendem q, Auth-Pflicht, graceful
#         degradation (Embedding-Ausfall → 200 statt 503). Embedding-Provider via
#         dependency_override.
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
from foreman.db.models import Alarm, Machine, MaintenanceEvent, WorkerNote
from foreman.embeddings.errors import ProviderUnavailable
from foreman.embeddings.provider import Vector

_SEARCH = "/api/v1/archive/search"
_DIM = 1024
_HIT_FIELDS = {"source_type", "id", "machine_id", "timestamp", "excerpt", "detail"}


def _unit(index: int) -> Vector:
    vec = [0.0] * _DIM
    vec[index] = 1.0
    return vec


_QUERY = _unit(0)


class _FixedProvider:
    def __init__(self, vector: Vector) -> None:
        self._vector = vector

    async def embed(self, texts: Sequence[str]) -> list[Vector]:
        return [list(self._vector) for _ in texts]


class _FailProvider:
    async def embed(self, texts: Sequence[str]) -> list[Vector]:
        raise ProviderUnavailable("❌ kein Backend (Test)", attempted=("ollama",))


async def _seed(test_settings: Settings) -> tuple[int, int, int, int]:
    """Seedet (committed) eine Maschine + je eine Notiz/Wartung/Alarm mit Fett-Bezug.
    Liefert (machine_id, note_id, maintenance_id, alarm_id)."""
    engine = create_async_engine(test_settings.database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with maker() as session:
        m = Machine(label="CNC-1", machine_class="cnc")
        session.add(m)
        await session.flush()
        note = WorkerNote(machine_id=m.id, text="Lager mit Fett geschmiert", embedding=_unit(0))
        maint = MaintenanceEvent(
            machine_id=m.id, type="lubrication", description="Fett nachgefüllt"
        )
        alarm = Alarm(
            machine_id=m.id,
            severity="warning",
            category="process",
            code="LUB-1",
            message="Fett knapp",
        )
        session.add_all([note, maint, alarm])
        await session.flush()
        ids = (m.id, note.id, maint.id, alarm.id)
        await session.commit()
    await engine.dispose()
    return ids


@pytest.mark.integration
async def test_archive_route_default_alle_quellen_flach_ohne_score(
    app: FastAPI, auth_client: AsyncClient, test_settings: Settings
) -> None:
    """Default (kein sources) durchsucht alle drei Quellen; flache ArchiveHit-Liste ohne Score."""
    await _seed(test_settings)
    app.dependency_overrides[get_embedding_provider] = lambda: _FixedProvider(_QUERY)
    resp = await auth_client.get(_SEARCH, params={"q": "Fett", "k": 10})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert {item["source_type"] for item in body} == {"note", "maintenance", "alarm"}
    assert set(body[0]) == _HIT_FIELDS
    for forbidden in ("score", "rrf_score", "embedding", "distance"):
        assert all(forbidden not in item for item in body)


@pytest.mark.integration
async def test_archive_route_quellen_filter_csv(
    app: FastAPI, auth_client: AsyncClient, test_settings: Settings
) -> None:
    """Quellen-Filter als CSV (?sources=note,alarm) blendet die Wartung aus."""
    await _seed(test_settings)
    app.dependency_overrides[get_embedding_provider] = lambda: _FixedProvider(_QUERY)
    resp = await auth_client.get(_SEARCH, params={"q": "Fett", "sources": "note,alarm"})
    assert resp.status_code == 200, resp.text
    assert {item["source_type"] for item in resp.json()} <= {"note", "alarm"}
    assert "maintenance" not in {item["source_type"] for item in resp.json()}


@pytest.mark.integration
async def test_archive_route_quellen_filter_wiederholbar(
    app: FastAPI, auth_client: AsyncClient, test_settings: Settings
) -> None:
    """Quellen-Filter als wiederholbarer Param (?sources=maintenance) liefert nur Wartung."""
    _, _, maint_id, _ = await _seed(test_settings)
    app.dependency_overrides[get_embedding_provider] = lambda: _FixedProvider(_QUERY)
    resp = await auth_client.get(_SEARCH, params=[("q", "Fett"), ("sources", "maintenance")])
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body and all(item["source_type"] == "maintenance" for item in body)
    assert maint_id in [item["id"] for item in body]


@pytest.mark.integration
async def test_archive_route_unbekannte_quelle_422(app: FastAPI, auth_client: AsyncClient) -> None:
    app.dependency_overrides[get_embedding_provider] = lambda: _FixedProvider(_QUERY)
    resp = await auth_client.get(_SEARCH, params={"q": "Fett", "sources": "gibtsnicht"})
    assert resp.status_code == 422


@pytest.mark.integration
async def test_archive_route_machine_id_filter(
    app: FastAPI, auth_client: AsyncClient, test_settings: Settings
) -> None:
    machine_id, _, _, _ = await _seed(test_settings)
    app.dependency_overrides[get_embedding_provider] = lambda: _FixedProvider(_QUERY)
    resp = await auth_client.get(_SEARCH, params={"q": "Fett", "machine_id": machine_id})
    assert resp.status_code == 200
    assert all(item["machine_id"] == machine_id for item in resp.json())
    # Fremde Maschine → keine Treffer.
    resp_other = await auth_client.get(
        _SEARCH, params={"q": "Fett", "machine_id": machine_id + 999}
    )
    assert resp_other.status_code == 200
    assert resp_other.json() == []


@pytest.mark.integration
async def test_archive_route_braucht_auth(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_embedding_provider] = lambda: _FixedProvider(_QUERY)
    resp = await client.get(_SEARCH, params={"q": "Fett"})
    assert resp.status_code == 401


@pytest.mark.integration
async def test_archive_route_q_fehlt_422(app: FastAPI, auth_client: AsyncClient) -> None:
    app.dependency_overrides[get_embedding_provider] = lambda: _FixedProvider(_QUERY)
    resp = await auth_client.get(_SEARCH)
    assert resp.status_code == 422


@pytest.mark.integration
async def test_archive_route_graceful_degradation_volltext(
    app: FastAPI, auth_client: AsyncClient, test_settings: Settings
) -> None:
    """Embedding-Ausfall → 200 (kein 503): Notiz-Volltext + Wartung + Alarm tragen weiter."""
    await _seed(test_settings)
    app.dependency_overrides[get_embedding_provider] = lambda: _FailProvider()
    resp = await auth_client.get(_SEARCH, params={"q": "Fett", "k": 10})
    assert resp.status_code == 200, resp.text
    assert {"note", "maintenance", "alarm"} <= {item["source_type"] for item in resp.json()}
