# ============================================================
#  FOREMAN — tests/integration/test_realtime_notify.py
#  Zweck: NOTIFY-Producer (F5) — verifiziert Vorgabe 4: GENAU EIN pg_notify pro
#         Aufruf, transaktional auf dem Commit, no-op bei leerem ChangeSet.
# ============================================================
from __future__ import annotations

import asyncio

import asyncpg
import pytest
from httpx import AsyncClient

from foreman.adapters.simulation.adapter import SimulationAdapter
from foreman.adapters.simulation.scenario import load_scenario_by_name
from foreman.core.pseudonymize import Pseudonymizer
from foreman.core.redact import Redactor
from foreman.ingestion.service import IngestionService
from foreman.realtime.channels import DASHBOARD_CHANNEL, ChangeSet, decode_change
from foreman.realtime.notify import notify_changes

pytestmark = pytest.mark.integration


async def _wait_for(received: list[str], *, expected: int, attempts: int = 100) -> None:
    """Wartet bis `expected` Notifikationen da sind (asyncpg liefert async)."""
    for _ in range(attempts):
        if len(received) >= expected:
            return
        await asyncio.sleep(0.02)


async def test_notify_emits_single_transactional_notification(
    db_session: object, raw_conn: asyncpg.Connection
) -> None:
    received: list[str] = []
    await raw_conn.add_listener(
        DASHBOARD_CHANNEL, lambda _c, _p, _chan, payload: received.append(payload)
    )

    emitted = await notify_changes(
        db_session,  # type: ignore[arg-type]
        ChangeSet(
            machines=frozenset({5}),
            data_points=frozenset({12}),
            kinds=frozenset({"reading"}),
        ),
    )
    await db_session.commit()  # type: ignore[attr-defined]
    await _wait_for(received, expected=1)

    assert emitted is True
    assert len(received) == 1, "genau EIN NOTIFY pro Aufruf"
    change = decode_change(received[0])
    assert change.machines == frozenset({5})
    assert change.data_points == frozenset({12})


async def test_notify_is_noop_for_empty_changeset(
    db_session: object, raw_conn: asyncpg.Connection
) -> None:
    received: list[str] = []
    await raw_conn.add_listener(
        DASHBOARD_CHANNEL, lambda _c, _p, _chan, payload: received.append(payload)
    )

    emitted = await notify_changes(db_session, ChangeSet())  # type: ignore[arg-type]
    await db_session.commit()  # type: ignore[attr-defined]
    await asyncio.sleep(0.2)

    assert emitted is False
    assert received == []


async def _seed_data_point(client: AsyncClient) -> int:
    """Seedet Linie→Maschine→Datenpunkt über die API und gibt die data_point_id."""
    line = await client.post("/api/v1/lines", json={"label": "L"})
    machine = await client.post(
        "/api/v1/machines", json={"label": "M", "line_id": line.json()["id"]}
    )
    data_point = await client.post(
        "/api/v1/data_points",
        json={"machine_id": machine.json()["id"], "name": "temp", "kind": "analog"},
    )
    return int(data_point.json()["id"])


async def test_post_readings_emits_change_notification(
    auth_client: AsyncClient, raw_conn: asyncpg.Connection
) -> None:
    """Der HTTP-Schreibpfad signalisiert seinen Batch (ein NOTIFY, transaktional)."""
    received: list[str] = []
    await raw_conn.add_listener(
        DASHBOARD_CHANNEL, lambda _c, _p, _chan, payload: received.append(payload)
    )
    data_point_id = await _seed_data_point(auth_client)

    response = await auth_client.post(
        "/api/v1/readings",
        json={
            "readings": [
                {"data_point_id": data_point_id, "time": "2026-06-16T10:00:00+00:00", "value": 1.0}
            ]
        },
    )
    assert response.status_code == 201, response.text
    await _wait_for(received, expected=1)

    assert len(received) == 1, "ein NOTIFY pro Batch"
    change = decode_change(received[0])
    assert data_point_id in change.data_points
    assert "reading" in change.kinds


async def test_backfill_ingest_emits_one_change_notification(
    db_session: object,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    """Der separate Ingest-Prozess signalisiert je Commit genau einmal (Vorgabe 4)."""
    received: list[str] = []
    await raw_conn.add_listener(
        DASHBOARD_CHANNEL, lambda _c, _p, _chan, payload: received.append(payload)
    )
    adapter = SimulationAdapter(load_scenario_by_name("minimal_bearing_drift"), seed=1)
    service = IngestionService(
        db_session,  # type: ignore[arg-type]
        pseudonymizer=pseudonymizer,
        redactor=fake_redactor,
        batch_size=500,
    )

    await service.ingest(adapter)  # backfill → genau ein finaler Commit
    await _wait_for(received, expected=1)

    assert len(received) == 1, "genau ein NOTIFY pro Commit"
    change = decode_change(received[-1])
    assert change.data_points, "Readings wurden berührt"
    assert "reading" in change.kinds
    assert "alarm" in change.kinds  # minimal_bearing_drift erzeugt einen Alarm
