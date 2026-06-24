# ============================================================
#  FOREMAN — tests/integration/test_reasoner_rbac.py
#  Zweck: Serverseitige Rollen-Durchsetzung der Trigger-/Quittier-Routen (§21.18).
#         Die FE-Rollen-Matrix ist ein UX-Filter; die echte Grenze hält das Backend.
#         Geprüft: eine VERBOTENE Rolle bekommt 403 (nicht den Endpunkt), eine
#         ERLAUBTE Rolle kommt durch den Guard (kein 403 — dann greift die normale
#         Endpunkt-Logik: 200/404). Schließt die Lücke „FE-Sperre per API umgehbar".
#  Architektur-Einordnung: Quality Gate §10.3 (Integration, echte DB).
# ============================================================
from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

AuthFor = Callable[[str, str], Awaitable[dict[str, str]]]


async def _machine(client: AsyncClient, headers: dict[str, str]) -> int:
    line = (await client.post("/api/v1/lines", json={"label": "Linie 1"}, headers=headers)).json()
    machine = (
        await client.post(
            "/api/v1/machines",
            json={"label": "Maschine 1", "external_id": "RBAC-1", "line_id": line["id"]},
            headers=headers,
        )
    ).json()
    machine_id: int = machine["id"]
    return machine_id


async def _drift_alarm(client: AsyncClient, headers: dict[str, str], machine_id: int) -> int:
    resp = await client.post(
        "/api/v1/alarms",
        json={
            "machine_id": machine_id,
            "code": "DRIFT",
            "category": "process",
            "severity": "warning",
            "message": "Verhaltens-Drift erkannt",
        },
        headers=headers,
    )
    alarm_id: int = resp.json()["id"]
    return alarm_id


# --- Drift-Quittierung: Schichtleiter/Techniker/Manager dürfen, Werker NICHT ---


async def test_acknowledge_worker_ist_403(client: AsyncClient, auth_headers_for: AuthFor) -> None:
    lead = await auth_headers_for("rbac-ack-lead@x.de", "shift_lead")
    machine_id = await _machine(client, lead)
    alarm_id = await _drift_alarm(client, lead, machine_id)

    worker = await auth_headers_for("rbac-ack-wrk@x.de", "worker")
    resp = await client.post(
        f"/api/v1/reasoners/drift/alarms/{alarm_id}/acknowledge", headers=worker
    )
    assert resp.status_code == 403


async def test_acknowledge_manager_darf(client: AsyncClient, auth_headers_for: AuthFor) -> None:
    lead = await auth_headers_for("rbac-ack-lead2@x.de", "shift_lead")
    machine_id = await _machine(client, lead)
    alarm_id = await _drift_alarm(client, lead, machine_id)

    manager = await auth_headers_for("rbac-ack-mgr@x.de", "manager")
    resp = await client.post(
        f"/api/v1/reasoners/drift/alarms/{alarm_id}/acknowledge", headers=manager
    )
    # Manager-Vollzugriff (§21.18): quittiert real (HITL-Status), keine Rollen-Sperre.
    assert resp.status_code == 200


# --- Ketten-Rekonstruktion: Schichtleiter/Manager dürfen, Werker/Techniker NICHT ---


async def test_reconstruct_technician_ist_403(
    client: AsyncClient, auth_headers_for: AuthFor
) -> None:
    tech = await auth_headers_for("rbac-rec-tech@x.de", "technician")
    resp = await client.post(
        "/api/v1/reasoners/event_chain/reconstruct",
        json={"anchor_alarm_id": 1},
        headers=tech,
    )
    assert resp.status_code == 403


async def test_reconstruct_manager_kommt_durch_guard(
    client: AsyncClient, auth_headers_for: AuthFor
) -> None:
    manager = await auth_headers_for("rbac-rec-mgr@x.de", "manager")
    resp = await client.post(
        "/api/v1/reasoners/event_chain/reconstruct",
        json={"anchor_alarm_id": 999_999},
        headers=manager,
    )
    # Rolle erlaubt → KEIN 403; der Anker existiert nicht → 404 (Endpunkt-Logik).
    assert resp.status_code == 404


# --- Vorhersage/Empfehlung: Schichtleiter/Manager dürfen, Werker/Techniker NICHT ---


async def test_predict_worker_ist_403(client: AsyncClient, auth_headers_for: AuthFor) -> None:
    worker = await auth_headers_for("rbac-pred-wrk@x.de", "worker")
    resp = await client.post(
        "/api/v1/reasoners/failure/predict", json={"machine_id": 1}, headers=worker
    )
    assert resp.status_code == 403


async def test_predict_manager_kommt_durch_guard(
    client: AsyncClient, auth_headers_for: AuthFor
) -> None:
    manager = await auth_headers_for("rbac-pred-mgr@x.de", "manager")
    resp = await client.post(
        "/api/v1/reasoners/failure/predict", json={"machine_id": 999_999}, headers=manager
    )
    # Rolle erlaubt → KEIN 403; die Maschine existiert nicht → 404 (Endpunkt-Logik).
    assert resp.status_code == 404


async def test_recommendation_technician_ist_403(
    client: AsyncClient, auth_headers_for: AuthFor
) -> None:
    tech = await auth_headers_for("rbac-rec2-tech@x.de", "technician")
    resp = await client.post("/api/v1/reasoners/failure/predictions/1/recommendation", headers=tech)
    assert resp.status_code == 403


async def test_recommendation_manager_kommt_durch_guard(
    client: AsyncClient, auth_headers_for: AuthFor
) -> None:
    manager = await auth_headers_for("rbac-rec2-mgr@x.de", "manager")
    resp = await client.post(
        "/api/v1/reasoners/failure/predictions/999999/recommendation", headers=manager
    )
    # Rolle erlaubt → KEIN 403; die Vorhersage existiert nicht → 404 (Endpunkt-Logik).
    assert resp.status_code == 404
