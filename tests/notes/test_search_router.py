# ============================================================
#  FOREMAN — tests/notes/test_search_router.py
#  Zweck: HTTP-Vertrag der Archiv-Suche (Paket 1a) —
#         GET /api/v1/worker_notes/search: hybride Relevanz-Reihenfolge (RRF) als
#         FLACHE list[WorkerNoteRead] OHNE Score-Feld, exaktes Wort über Volltext,
#         Relevanz-Cutoff, GRACEFUL DEGRADATION (Embedding-Ausfall → 200 mit
#         Volltext-Treffern statt 503), machine_id-Filter, Auth-Pflicht,
#         422-Validierung und die Regression, dass /worker_notes/{id} NICHT von
#         /search geschattet wird. Embedding-Provider via dependency_override.
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
# Vollständige WorkerNoteRead-Felder (Vertrag): KEIN Score/embedding/distance.
_READ_FIELDS = {"id", "machine_id", "shift", "text", "classification", "author", "created_at"}


def _unit(index: int) -> Vector:
    vec = [0.0] * _DIM
    vec[index] = 1.0
    return vec


def _opposite() -> Vector:
    return [-1.0, *([0.0] * (_DIM - 1))]


_QUERY = _unit(0)


class _FixedProvider:
    """Liefert für jeden Text einen festen Vektor (deterministische Such-Reihenfolge)."""

    def __init__(self, vector: Vector) -> None:
        self._vector = vector

    async def embed(self, texts: Sequence[str]) -> list[Vector]:
        return [list(self._vector) for _ in texts]


class _FailProvider:
    """Simuliert ein nicht erreichbares Embedding-Backend (→ graceful Degradation)."""

    async def embed(self, texts: Sequence[str]) -> list[Vector]:
        raise ProviderUnavailable("❌ kein Backend (Test)", attempted=("ollama",))


async def _seed(
    test_settings: Settings, specs: list[dict[str, object]]
) -> tuple[dict[str, int], dict[str, int]]:
    """Seedet (committed) Maschinen + Notizen aus `specs` (Keys: key/machine/text/embedding).

    Liefert (machine_ids je machine-Key, note_ids je note-Key)."""
    engine = create_async_engine(test_settings.database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with maker() as session:
        machines: dict[str, Machine] = {}
        for machine_key in {str(spec["machine"]) for spec in specs}:
            machine = Machine(label=machine_key, machine_class="cnc")
            session.add(machine)
            machines[machine_key] = machine
        await session.flush()
        notes: dict[str, WorkerNote] = {}
        for spec in specs:
            note = WorkerNote(
                machine_id=machines[str(spec["machine"])].id,
                text=str(spec["text"]),
                embedding=spec["embedding"],  # type: ignore[arg-type]
            )
            session.add(note)
            notes[str(spec["key"])] = note
        await session.flush()
        machine_ids = {key: machine.id for key, machine in machines.items()}
        note_ids = {key: note.id for key, note in notes.items()}
        await session.commit()
    await engine.dispose()
    return machine_ids, note_ids


@pytest.mark.integration
async def test_search_route_relevanz_reihenfolge_flach_ohne_score(
    app: FastAPI, auth_client: AsyncClient, test_settings: Settings
) -> None:
    """Vertrag: flache list[WorkerNoteRead], Reihenfolge = Relevanz (RRF-Rang),
    KEIN Score-/Vektor-Feld. Volltext+Vektor-Treffer rankt vor reinem Vektor-Treffer."""
    _, note_ids = await _seed(
        test_settings,
        [
            {"key": "match", "machine": "m1", "text": "Lager Fett heiß", "embedding": _unit(0)},
            {"key": "vec", "machine": "m1", "text": "Beleuchtung getauscht", "embedding": _unit(0)},
        ],
    )
    app.dependency_overrides[get_embedding_provider] = lambda: _FixedProvider(_QUERY)
    resp = await auth_client.get(_SEARCH, params={"q": "Fett", "k": 5})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert [item["id"] for item in body] == [note_ids["match"], note_ids["vec"]]
    # Vertrag: genau die WorkerNoteRead-Felder, kein Score/Vektor.
    assert set(body[0]) == _READ_FIELDS
    for forbidden in ("embedding", "score", "rrf_score", "distance", "rank"):
        assert forbidden not in body[0]


@pytest.mark.integration
async def test_search_route_exaktes_wort_via_volltext(
    app: FastAPI, auth_client: AsyncClient, test_settings: Settings
) -> None:
    """Exaktes Wort 'Fett' kommt über den Volltext-Zweig rein — obwohl der Query-
    Vektor (Gegenvektor, Distanz 2.0) die Notiz nie über den Cutoff brächte."""
    _, note_ids = await _seed(
        test_settings,
        [
            {
                "key": "fett",
                "machine": "m1",
                "text": "Lager lief heiß, zu wenig Fett",
                "embedding": _opposite(),
            }
        ],
    )
    app.dependency_overrides[get_embedding_provider] = lambda: _FixedProvider(_QUERY)
    resp = await auth_client.get(_SEARCH, params={"q": "Fett"})
    assert resp.status_code == 200, resp.text
    assert note_ids["fett"] in [item["id"] for item in resp.json()]


@pytest.mark.integration
async def test_search_route_cutoff_unterdrueckt_vages(
    app: FastAPI, auth_client: AsyncClient, test_settings: Settings
) -> None:
    """Cutoff: eine ferne Vektor-Notiz (Distanz 1.0 > 0.55) ohne Volltext-Match wird
    NICHT zurückgegeben (kein Müll-Auffüllen)."""
    await _seed(
        test_settings,
        [{"key": "fern", "machine": "m1", "text": "Beleuchtung erneuert", "embedding": _unit(1)}],
    )
    app.dependency_overrides[get_embedding_provider] = lambda: _FixedProvider(_QUERY)
    resp = await auth_client.get(_SEARCH, params={"q": "Schmierung"})
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.integration
async def test_search_route_backend_ausfall_degradiert_volltext(
    app: FastAPI, auth_client: AsyncClient, test_settings: Settings
) -> None:
    """GRACEFUL DEGRADATION: fällt das Embedding-Backend aus, antwortet die Route mit
    200 und Volltext-Treffern — NICHT mehr 503. Exakte-Wort-Treffer bleiben erhalten."""
    _, note_ids = await _seed(
        test_settings,
        [
            {
                "key": "fett",
                "machine": "m1",
                "text": "Spindel nachgefettet, Fett alt",
                "embedding": _unit(1),
            }
        ],
    )
    app.dependency_overrides[get_embedding_provider] = lambda: _FailProvider()
    resp = await auth_client.get(_SEARCH, params={"q": "Fett"})
    assert resp.status_code == 200, resp.text
    assert note_ids["fett"] in [item["id"] for item in resp.json()]


@pytest.mark.integration
async def test_search_route_machine_id_filter(
    app: FastAPI, auth_client: AsyncClient, test_settings: Settings
) -> None:
    """machine_id filtert hart in beiden Zweigen — nur die Notiz der Zielmaschine kommt."""
    machine_ids, note_ids = await _seed(
        test_settings,
        [
            {"key": "m1n", "machine": "m1", "text": "Lager Fett", "embedding": _unit(0)},
            {"key": "m2n", "machine": "m2", "text": "Lager Fett", "embedding": _unit(0)},
        ],
    )
    app.dependency_overrides[get_embedding_provider] = lambda: _FixedProvider(_QUERY)
    resp = await auth_client.get(_SEARCH, params={"q": "Fett", "machine_id": machine_ids["m2"]})
    assert resp.status_code == 200
    assert [item["id"] for item in resp.json()] == [note_ids["m2n"]]


@pytest.mark.integration
async def test_search_route_braucht_auth(app: FastAPI, client: AsyncClient) -> None:
    app.dependency_overrides[get_embedding_provider] = lambda: _FixedProvider(_QUERY)
    resp = await client.get(_SEARCH, params={"q": "x"})
    assert resp.status_code == 401


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
    _, note_ids = await _seed(
        test_settings,
        [{"key": "a", "machine": "m1", "text": "A identisch", "embedding": _unit(0)}],
    )
    resp = await auth_client.get(f"/api/v1/worker_notes/{note_ids['a']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == note_ids["a"]
