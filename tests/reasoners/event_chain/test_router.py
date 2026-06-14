# ============================================================
#  FOREMAN — tests/reasoners/event_chain/test_router.py
#  Zweck: HTTP-Vertrag des Ereignisketten-Reasoners (F6, Baustein 7) — on-demand
#         POST /reconstruct + GET /explanations(/{id}); 404; Auth-Pflicht. Gateway
#         via dependency_override gemockt (kein LLM-Call), Substrat aus (Test-Config).
# ============================================================
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from foreman.api.deps import get_llm_gateway
from foreman.config import Settings
from foreman.db.models import Alarm, Machine, WorkerNote

_RECONSTRUCT = "/api/v1/reasoners/event_chain/reconstruct"
_EXPLANATIONS = "/api/v1/reasoners/event_chain/explanations"


async def _seed(test_settings: Settings) -> tuple[int, int, int]:
    """Seedet (committed) Maschine + Anker-Alarm + Notiz in die Test-DB."""
    engine = create_async_engine(test_settings.database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with maker() as session:
        machine = Machine(label="CNC-1", machine_class="cnc")
        session.add(machine)
        await session.flush()
        anchor = Alarm(
            machine_id=machine.id, severity="warning", category="process",
            code="DRIFT", message="Verhaltens-Drift erkannt", raised_at=datetime.now(UTC),
        )
        note = WorkerNote(machine_id=machine.id, text="Lager läuft heiß", created_at=datetime.now(UTC))
        session.add_all([anchor, note])
        await session.flush()
        ids = (machine.id, anchor.id, note.id)
        await session.commit()
    await engine.dispose()
    return ids


def _override_gateway(
    app: FastAPI, make_gateway: Callable[..., object], make_backend: Callable[..., object], reply: str
) -> None:
    app.dependency_overrides[get_llm_gateway] = lambda: make_gateway(
        backends=[make_backend("local", reply=reply)]
    )


@pytest.mark.integration
async def test_reconstruct_route_liefert_201(
    app: FastAPI, auth_client: AsyncClient, test_settings: Settings,
    make_gateway: Callable[..., object], make_backend: Callable[..., object],
) -> None:
    machine_id, anchor_id, note_id = await _seed(test_settings)
    _override_gateway(
        app, make_gateway, make_backend,
        reply=f"Rund um [alarm:{anchor_id}] meldete [note:{note_id}] einen Hinweis.",
    )
    resp = await auth_client.post(_RECONSTRUCT, json={"anchor_alarm_id": anchor_id})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["anchor_alarm_id"] == anchor_id
    assert body["machine_id"] == machine_id
    assert f"alarm:{anchor_id}" in body["referenced_source_ids"]
    assert body["confidence"] in {"low", "medium", "high"}
    assert "id" in body and "created_at" in body


@pytest.mark.integration
async def test_reconstruct_route_unbekannter_anker_404(
    app: FastAPI, auth_client: AsyncClient,
    make_gateway: Callable[..., object], make_backend: Callable[..., object],
) -> None:
    _override_gateway(app, make_gateway, make_backend, reply="egal")
    resp = await auth_client.post(_RECONSTRUCT, json={"anchor_alarm_id": 999_999})
    assert resp.status_code == 404


@pytest.mark.integration
async def test_reconstruct_route_braucht_auth(
    client: AsyncClient, app: FastAPI,
    make_gateway: Callable[..., object], make_backend: Callable[..., object],
) -> None:
    _override_gateway(app, make_gateway, make_backend, reply="egal")
    resp = await client.post(_RECONSTRUCT, json={"anchor_alarm_id": 1})
    assert resp.status_code == 401


@pytest.mark.integration
async def test_list_und_get_explanations(
    app: FastAPI, auth_client: AsyncClient, test_settings: Settings,
    make_gateway: Callable[..., object], make_backend: Callable[..., object],
) -> None:
    machine_id, anchor_id, _ = await _seed(test_settings)
    _override_gateway(app, make_gateway, make_backend, reply=f"Siehe [alarm:{anchor_id}].")
    created = await auth_client.post(_RECONSTRUCT, json={"anchor_alarm_id": anchor_id})
    explanation_id = created.json()["id"]

    listing = await auth_client.get(_EXPLANATIONS, params={"machine_id": machine_id})
    assert listing.status_code == 200
    assert any(item["id"] == explanation_id for item in listing.json())

    single = await auth_client.get(f"{_EXPLANATIONS}/{explanation_id}")
    assert single.status_code == 200
    assert single.json()["id"] == explanation_id

    missing = await auth_client.get(f"{_EXPLANATIONS}/999999")
    assert missing.status_code == 404
