# ============================================================
#  FOREMAN — tests/integration/test_drift_hitl_ack.py
#  Zweck: Pflicht-Test-Block für den HITL-Quittierungs-Flow (F4, §8/§11.2).
#  Prüft: eine Drift-Warnung gilt erst nach Operator-Quittierung als erledigt;
#  acknowledged_by wird tokenisiert (kein Klartext); Auth-/Permission-Fall (401),
#  nicht gefunden (404), Nicht-Drift-Alarm (400). Keine Aktorik — nur Status.
#  Architektur-Einordnung: Quality Gate §10.3 (Integration, echte DB).
# ============================================================
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


async def _machine(client: AsyncClient) -> int:
    line = (await client.post("/api/v1/lines", json={"label": "Linie 1"})).json()
    machine = (
        await client.post(
            "/api/v1/machines",
            json={"label": "Maschine 1", "external_id": "X-1", "line_id": line["id"]},
        )
    ).json()
    machine_id: int = machine["id"]
    return machine_id


async def _drift_alarm(client: AsyncClient, machine_id: int) -> int:
    resp = await client.post(
        "/api/v1/alarms",
        json={
            "machine_id": machine_id,
            "code": "DRIFT",
            "category": "process",
            "severity": "warning",
            "message": "Verhaltens-Drift erkannt",
        },
    )
    alarm_id: int = resp.json()["id"]
    return alarm_id


async def test_drift_warnung_gilt_erst_nach_quittierung_als_erledigt(
    auth_client: AsyncClient,
) -> None:
    machine_id = await _machine(auth_client)
    alarm_id = await _drift_alarm(auth_client, machine_id)

    # Unquittiert: in der offenen Liste sichtbar.
    open_before = (
        await auth_client.get("/api/v1/reasoners/drift/alarms?acknowledged=false")
    ).json()
    assert any(a["id"] == alarm_id for a in open_before)

    # Quittieren (HITL).
    ack = await auth_client.post(f"/api/v1/reasoners/drift/alarms/{alarm_id}/acknowledge")
    assert ack.status_code == 200
    body = ack.json()
    assert body["acknowledged_at"] is not None
    # acknowledged_by ist ein HMAC-Token (v{n}:{hex}), NICHT die Klartext-user_id.
    assert isinstance(body["acknowledged_by"], str)
    assert ":" in body["acknowledged_by"]
    assert not body["acknowledged_by"].isdigit()

    # Nach Quittierung: nicht mehr in der offenen Liste.
    open_after = (
        await auth_client.get("/api/v1/reasoners/drift/alarms?acknowledged=false")
    ).json()
    assert not any(a["id"] == alarm_id for a in open_after)


async def test_quittierung_ohne_auth_ist_401(auth_client: AsyncClient) -> None:
    machine_id = await _machine(auth_client)
    alarm_id = await _drift_alarm(auth_client, machine_id)
    # Bearer-Token nach dem Setup entfernen → unauthentifiziert (Middleware blockt).
    auth_client.headers.pop("Authorization", None)
    resp = await auth_client.post(f"/api/v1/reasoners/drift/alarms/{alarm_id}/acknowledge")
    assert resp.status_code == 401


async def test_quittierung_unbekannter_alarm_ist_404(auth_client: AsyncClient) -> None:
    resp = await auth_client.post("/api/v1/reasoners/drift/alarms/999999/acknowledge")
    assert resp.status_code == 404


async def test_quittierung_nur_fuer_drift_warnungen(auth_client: AsyncClient) -> None:
    machine_id = await _machine(auth_client)
    # Ein gewöhnlicher (Nicht-Drift-)Alarm darf nicht über diesen Endpunkt quittiert werden.
    other = await auth_client.post(
        "/api/v1/alarms",
        json={
            "machine_id": machine_id,
            "code": "HW_FAULT",
            "category": "hardware",
            "severity": "alarm",
        },
    )
    alarm_id = other.json()["id"]
    resp = await auth_client.post(f"/api/v1/reasoners/drift/alarms/{alarm_id}/acknowledge")
    assert resp.status_code == 400
