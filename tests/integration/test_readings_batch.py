# ============================================================
#  FOREMAN — tests/integration/test_readings_batch.py
#  Zweck: Batch-Ingestion über COPY in die readings-Hypertable (§4, Research §3.4).
#  Pflicht-Test-Block: Happy-Path (+Persistenz), PK-Konflikt, Validierung, FK,
#         Auth-Fall.
# ============================================================
from __future__ import annotations

import asyncpg
from httpx import AsyncClient


async def _data_point(c: AsyncClient) -> int:
    line = await c.post("/api/v1/lines", json={"label": "L"})
    machine = await c.post(
        "/api/v1/machines", json={"label": "M", "line_id": line.json()["id"]}
    )
    dp = await c.post(
        "/api/v1/data_points",
        json={"machine_id": machine.json()["id"], "name": "temp", "kind": "analog"},
    )
    return int(dp.json()["id"])


def _batch(dp_id: int) -> dict[str, object]:
    return {
        "readings": [
            {"data_point_id": dp_id, "time": "2026-06-13T10:00:00+00:00", "value": 21.5},
            {"data_point_id": dp_id, "time": "2026-06-13T10:00:01+00:00", "value": 21.7, "quality": 0},
            {"data_point_id": dp_id, "time": "2026-06-13T10:00:02+00:00", "value": 22.0},
        ]
    }


async def test_batch_writes_to_hypertable(
    auth_client: AsyncClient, raw_conn: asyncpg.Connection
) -> None:
    dp_id = await _data_point(auth_client)
    response = await auth_client.post("/api/v1/readings", json=_batch(dp_id))
    assert response.status_code == 201, response.text
    assert response.json()["written"] == 3
    # Persistenz in der Hypertable direkt prüfen.
    count = await raw_conn.fetchval(
        "SELECT count(*) FROM readings WHERE data_point_id = $1", dp_id
    )
    assert count == 3


async def test_readings_is_a_hypertable(raw_conn: asyncpg.Connection) -> None:
    # Migration 0002 muss readings zur Hypertable gemacht haben.
    is_hyper = await raw_conn.fetchval(
        "SELECT count(*) FROM timescaledb_information.hypertables "
        "WHERE hypertable_name = 'readings'"
    )
    assert is_hyper == 1


async def test_duplicate_pk_conflicts(auth_client: AsyncClient) -> None:
    dp_id = await _data_point(auth_client)
    first = await auth_client.post("/api/v1/readings", json=_batch(dp_id))
    assert first.status_code == 201
    again = await auth_client.post("/api/v1/readings", json=_batch(dp_id))
    assert again.status_code == 409


async def test_empty_batch_422(auth_client: AsyncClient) -> None:
    response = await auth_client.post("/api/v1/readings", json={"readings": []})
    assert response.status_code == 422


async def test_unknown_data_point_400(auth_client: AsyncClient) -> None:
    response = await auth_client.post(
        "/api/v1/readings",
        json={"readings": [{"data_point_id": 999999, "time": "2026-06-13T10:00:00+00:00", "value": 1.0}]},
    )
    assert response.status_code == 400


async def test_readings_requires_auth(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/readings",
        json={"readings": [{"data_point_id": 1, "time": "2026-06-13T10:00:00+00:00", "value": 1.0}]},
    )
    assert response.status_code == 401
