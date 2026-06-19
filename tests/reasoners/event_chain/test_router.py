# ============================================================
#  FOREMAN — tests/reasoners/event_chain/test_router.py
#  Zweck: HTTP-Vertrag des Ereignisketten-Reasoners (F6, Baustein 7) — on-demand
#         POST /reconstruct + GET /explanations(/{id}); 404; Auth-Pflicht. Gateway
#         via dependency_override gemockt (kein LLM-Call), Substrat aus (Test-Config).
# ============================================================
from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from foreman.api.deps import get_llm_gateway, get_substrate_client
from foreman.config import Settings
from foreman.db.models import Alarm, Machine, ReasonerExplanationRecord, WorkerNote

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
            machine_id=machine.id,
            severity="warning",
            category="process",
            code="DRIFT",
            message="Verhaltens-Drift erkannt",
            raised_at=datetime.now(UTC),
        )
        note = WorkerNote(
            machine_id=machine.id, text="Lager läuft heiß", created_at=datetime.now(UTC)
        )
        session.add_all([anchor, note])
        await session.flush()
        ids = (machine.id, anchor.id, note.id)
        await session.commit()
    await engine.dispose()
    return ids


def _override_gateway(
    app: FastAPI,
    make_gateway: Callable[..., object],
    make_backend: Callable[..., object],
    reply: str,
) -> None:
    app.dependency_overrides[get_llm_gateway] = lambda: make_gateway(
        backends=[make_backend("local", reply=reply)]
    )


@pytest.mark.integration
async def test_reconstruct_route_liefert_201(
    app: FastAPI,
    auth_client: AsyncClient,
    test_settings: Settings,
    make_gateway: Callable[..., object],
    make_backend: Callable[..., object],
) -> None:
    machine_id, anchor_id, note_id = await _seed(test_settings)
    _override_gateway(
        app,
        make_gateway,
        make_backend,
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
    app: FastAPI,
    auth_client: AsyncClient,
    make_gateway: Callable[..., object],
    make_backend: Callable[..., object],
) -> None:
    _override_gateway(app, make_gateway, make_backend, reply="egal")
    resp = await auth_client.post(_RECONSTRUCT, json={"anchor_alarm_id": 999_999})
    assert resp.status_code == 404


@pytest.mark.integration
async def test_reconstruct_route_braucht_auth(
    client: AsyncClient,
    app: FastAPI,
    make_gateway: Callable[..., object],
    make_backend: Callable[..., object],
) -> None:
    _override_gateway(app, make_gateway, make_backend, reply="egal")
    resp = await client.post(_RECONSTRUCT, json={"anchor_alarm_id": 1})
    assert resp.status_code == 401


@pytest.mark.integration
async def test_list_und_get_explanations(
    app: FastAPI,
    auth_client: AsyncClient,
    test_settings: Settings,
    make_gateway: Callable[..., object],
    make_backend: Callable[..., object],
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


# ----------------------------------------------------------------
#  A1 — Kette ausgeliefert + als eingefrorener Snapshot persistiert (§21-D)
# ----------------------------------------------------------------
@pytest.mark.integration
async def test_reconstruct_liefert_kette_und_leere_siblings(
    app: FastAPI,
    auth_client: AsyncClient,
    test_settings: Settings,
    make_gateway: Callable[..., object],
    make_backend: Callable[..., object],
) -> None:
    machine_id, anchor_id, _note_id = await _seed(test_settings)
    _override_gateway(app, make_gateway, make_backend, reply=f"Rund um [alarm:{anchor_id}].")
    resp = await auth_client.post(_RECONSTRUCT, json={"anchor_alarm_id": anchor_id})
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # Kette ist mitgeliefert und trägt den Anker.
    assert body["chain"] is not None
    chain = body["chain"]
    assert chain["anchor_alarm_id"] == anchor_id
    assert chain["machine_id"] == machine_id
    assert any(event["source_id"] == f"alarm:{anchor_id}" for event in chain["events"])
    assert any(event["event_type"] == "anchor_alarm" for event in chain["events"])
    # Substrat aus → KEINE erfundenen Geschwister, leere strukturierte Liste.
    assert body["siblings"] == []
    # Eingefroren persistiert: GET /{id} liefert dieselbe Kette zurück (nicht neu abgeleitet).
    explanation_id = body["id"]
    fetched = await auth_client.get(f"{_EXPLANATIONS}/{explanation_id}")
    assert fetched.status_code == 200
    assert fetched.json()["chain"]["events"] == chain["events"]
    assert fetched.json()["siblings"] == []


@pytest.mark.integration
async def test_siblings_endpunkt_leer_und_404(
    app: FastAPI,
    auth_client: AsyncClient,
    test_settings: Settings,
    make_gateway: Callable[..., object],
    make_backend: Callable[..., object],
) -> None:
    _, anchor_id, _ = await _seed(test_settings)
    _override_gateway(app, make_gateway, make_backend, reply=f"Siehe [alarm:{anchor_id}].")
    created = await auth_client.post(_RECONSTRUCT, json={"anchor_alarm_id": anchor_id})
    explanation_id = created.json()["id"]

    siblings = await auth_client.get(f"{_EXPLANATIONS}/{explanation_id}/siblings")
    assert siblings.status_code == 200
    assert siblings.json() == []  # ohne Substrat: leer, kein Fake

    missing = await auth_client.get(f"{_EXPLANATIONS}/999999/siblings")
    assert missing.status_code == 404


@pytest.mark.integration
@pytest.mark.parametrize(
    "payload",
    [
        {"anchor_alarm_id": 0},
        {"anchor_alarm_id": -3},
        {"anchor_alarm_id": 1, "lookback_hours": 0},
        {"anchor_alarm_id": 1, "lookback_hours": 9000},
    ],
)
async def test_reconstruct_validierung_422(
    app: FastAPI,
    auth_client: AsyncClient,
    make_gateway: Callable[..., object],
    make_backend: Callable[..., object],
    payload: dict[str, int],
) -> None:
    _override_gateway(app, make_gateway, make_backend, reply="egal")
    resp = await auth_client.post(_RECONSTRUCT, json=payload)
    assert resp.status_code == 422, (payload, resp.text)


# ----------------------------------------------------------------
#  A2 — Ehrliche Schwester-Referenzen aus realen Recall-Treffern (§21-D)
# ----------------------------------------------------------------
class _FakeSubstrate:
    """Test-Doppel des Substrat-Clients: liefert einen klassen-bezogenen Treffer
    (mit machine_id) und einen reinen Text-Treffer (ohne Bezug → null-Ziele)."""

    def __init__(self, *, sister_machine_id: int) -> None:
        self._sister = sister_machine_id

    async def recall(self, query: str, *, max_results: int = 5) -> dict[str, Any]:
        return {
            "results": [
                {
                    "content": "An der Schwestermaschine lief das Lager heiß; Schmierung war Ursache.",
                    "id": "mem-42",
                    "metadata": {"machine_id": self._sister},
                },
                {"content": "Hinweis ohne strukturierten Bezug."},
            ]
        }


async def _seed_with_sister(test_settings: Settings) -> tuple[int, int, int]:
    """Seedet Anker-Maschine + Schwestermaschine (gleiche Klasse) + eine bereits
    gespeicherte Schwester-Erklärung. Gibt (anchor_id, sister_id, sister_expl_id)."""
    engine = create_async_engine(test_settings.database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with maker() as session:
        anchor_machine = Machine(label="CNC-1", machine_class="cnc")
        sister = Machine(label="CNC-2", machine_class="cnc")
        session.add_all([anchor_machine, sister])
        await session.flush()
        now = datetime.now(UTC)
        anchor = Alarm(
            machine_id=anchor_machine.id,
            severity="warning",
            category="process",
            code="DRIFT",
            raised_at=now,
        )
        sister_alarm = Alarm(
            machine_id=sister.id,
            severity="warning",
            category="process",
            code="DRIFT",
            raised_at=now - timedelta(days=1),
        )
        session.add_all([anchor, sister_alarm])
        await session.flush()
        sister_expl = ReasonerExplanationRecord(
            anchor_alarm_id=sister_alarm.id,
            machine_id=sister.id,
            reasoner="event_chain",
            narrative="Frühere Kette an der Schwestermaschine.",
            referenced_source_ids=[f"alarm:{sister_alarm.id}"],
            flagged_unsupported=[],
            is_hypothesis=False,
            confidence="high",
            recall_used=False,
        )
        session.add(sister_expl)
        await session.flush()
        ids = (anchor.id, sister.id, sister_expl.id)
        await session.commit()
    await engine.dispose()
    return ids


@pytest.mark.integration
async def test_reconstruct_schwester_referenzen_ehrlich(
    app: FastAPI,
    auth_client: AsyncClient,
    test_settings: Settings,
    make_gateway: Callable[..., object],
    make_backend: Callable[..., object],
) -> None:
    anchor_id, sister_id, sister_expl_id = await _seed_with_sister(test_settings)
    _override_gateway(app, make_gateway, make_backend, reply=f"Siehe [alarm:{anchor_id}].")
    app.dependency_overrides[get_substrate_client] = lambda: _FakeSubstrate(
        sister_machine_id=sister_id
    )

    resp = await auth_client.post(_RECONSTRUCT, json={"anchor_alarm_id": anchor_id})
    assert resp.status_code == 201, resp.text
    siblings = resp.json()["siblings"]
    # Genau zwei Referenzen — eine je realem Recall-Treffer (⊆ reale Treffer).
    assert len(siblings) == 2
    resolved = siblings[0]
    assert resolved["machine_id"] == sister_id
    assert resolved["machine_class"] == "cnc"
    assert resolved["explanation_id"] == sister_expl_id
    assert "Ähnlich anhand" in resolved["similarity_basis"]
    assert resolved["excerpt"]  # sanitisierter Auszug vorhanden
    assert resolved["recall_ref"] == "mem-42"
    # Zweiter Treffer ohne Bezug → ehrlich null-Ziele, KEIN erfundenes Geschwister.
    bare = siblings[1]
    assert bare["machine_id"] is None
    assert bare["machine_class"] is None
    assert bare["explanation_id"] is None

    # Eingefroren: der /siblings-Endpunkt liefert dieselben Referenzen aus dem Snapshot.
    explanation_id = resp.json()["id"]
    via_endpoint = await auth_client.get(f"{_EXPLANATIONS}/{explanation_id}/siblings")
    assert via_endpoint.status_code == 200
    assert len(via_endpoint.json()) == 2
