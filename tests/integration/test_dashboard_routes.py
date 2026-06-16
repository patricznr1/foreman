# ============================================================
#  FOREMAN — tests/integration/test_dashboard_routes.py
#  Zweck: Die HTTP-Read-Routen des Dashboards (F5): /overview (Flotten-Lagebild,
#         manager/shift_lead) und /machines/{id}/trend (Sensortrend + Normalband).
#         Verifiziert die mit dem WS-Push geteilte Autorisierung — der PII-/Scope-
#         Strich hält auch auf HTTP (Worker → 403).
# ============================================================
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

_PW = "supersecret1"


async def _auth(client: AsyncClient, email: str, role: str) -> dict[str, str]:
    await client.post("/auth/register", json={"email": email, "password": _PW, "role": role})
    response = await client.post("/auth/login", json={"email": email, "password": _PW})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _seed_machine_with_data_point(
    client: AsyncClient, auth: dict[str, str]
) -> tuple[int, int]:
    line = (await client.post("/api/v1/lines", json={"label": "L"}, headers=auth)).json()
    machine = (
        await client.post(
            "/api/v1/machines", json={"label": "M", "line_id": line["id"]}, headers=auth
        )
    ).json()
    data_point = (
        await client.post(
            "/api/v1/data_points",
            json={"machine_id": machine["id"], "name": "vib", "kind": "analog"},
            headers=auth,
        )
    ).json()
    return int(machine["id"]), int(data_point["id"])


async def test_overview_returns_fleet_for_manager(client: AsyncClient) -> None:
    auth = await _auth(client, "ovw-mgr@x.de", "manager")
    machine_id, _ = await _seed_machine_with_data_point(client, auth)

    response = await client.get("/api/v1/overview", headers=auth)

    assert response.status_code == 200, response.text
    body = response.json()
    assert "by_status" in body and "open_alarm_total" in body
    assert any(machine["id"] == machine_id for machine in body["machines"])


async def test_overview_forbidden_for_worker(client: AsyncClient) -> None:
    auth = await _auth(client, "ovw-wrk@x.de", "worker")
    response = await client.get("/api/v1/overview", headers=auth)
    assert response.status_code == 403


async def test_overview_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/overview")
    assert response.status_code == 401


async def test_machine_trend_returns_metadata_for_manager(client: AsyncClient) -> None:
    auth = await _auth(client, "trd-mgr@x.de", "manager")
    machine_id, _ = await _seed_machine_with_data_point(client, auth)

    response = await client.get(
        f"/api/v1/machines/{machine_id}/trend?datapoint=vib&hours=48", headers=auth
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data_point_name"] == "vib"
    assert isinstance(body["points"], list)
    assert body["profile_band"] is None


async def test_machine_trend_unknown_datapoint_404(client: AsyncClient) -> None:
    auth = await _auth(client, "trd-mgr2@x.de", "manager")
    machine_id, _ = await _seed_machine_with_data_point(client, auth)

    response = await client.get(f"/api/v1/machines/{machine_id}/trend?datapoint=nope", headers=auth)
    assert response.status_code == 404


async def test_machine_trend_forbidden_for_worker(client: AsyncClient) -> None:
    manager_auth = await _auth(client, "trd-mgr3@x.de", "manager")
    machine_id, _ = await _seed_machine_with_data_point(client, manager_auth)
    worker_auth = await _auth(client, "trd-wrk@x.de", "worker")

    response = await client.get(
        f"/api/v1/machines/{machine_id}/trend?datapoint=vib", headers=worker_auth
    )
    assert response.status_code == 403
