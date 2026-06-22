# ============================================================
#  FOREMAN — tests/audit/test_audit_api.py
#  Zweck: Integrationstests Sektion I (Audit) — der HITL-Quittier-Pfad schreibt
#         genau eine pseudonyme Audit-Zeile, und die Read-API GET /api/v1/audit
#         filtert korrekt und ist auf Manager beschränkt (Werker/Techniker/
#         Schichtleiter → 403, ohne Token → 401).
#  Architektur-Einordnung: Test-Infrastruktur (Quality Gates §10.3).
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.audit.service import list_audit
from foreman.db.models import AuditLog

pytestmark = pytest.mark.integration

_PW = "supersecret1"
_DRIFT_CODE = "DRIFT"


async def _auth(client: AsyncClient, email: str, role: str) -> dict[str, str]:
    await client.post("/auth/register", json={"email": email, "password": _PW, "role": role})
    response = await client.post("/auth/login", json={"email": email, "password": _PW})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _seed_drift_alarm(client: AsyncClient, auth: dict[str, str]) -> tuple[int, int]:
    """Legt eine Maschine + eine quittierbare Drift-Warnung an. Liefert (machine_id, alarm_id)."""
    machine = (await client.post("/api/v1/machines", json={"label": "M"}, headers=auth)).json()
    alarm = (
        await client.post(
            "/api/v1/alarms",
            json={
                "machine_id": machine["id"],
                "severity": "warning",
                "category": "process",
                "code": _DRIFT_CODE,
            },
            headers=auth,
        )
    ).json()
    return int(machine["id"]), int(alarm["id"])


async def test_acknowledge_writes_single_pseudonymous_hitl_audit_entry(client: AsyncClient) -> None:
    auth = await _auth(client, "audit-mgr1@x.de", "manager")
    machine_id, alarm_id = await _seed_drift_alarm(client, auth)

    ack = await client.post(f"/api/v1/reasoners/drift/alarms/{alarm_id}/acknowledge", headers=auth)
    assert ack.status_code == 200, ack.text
    acknowledged_by = ack.json()["acknowledged_by"]

    rows = (await client.get("/api/v1/audit", headers=auth)).json()
    assert len(rows) == 1, rows
    entry = rows[0]
    assert entry["action_type"] == "hitl_acknowledge"
    assert entry["origin"] == "dashboard"
    assert entry["target_kind"] == "alarm"
    assert entry["target_id"] == alarm_id
    assert entry["machine_id"] == machine_id
    assert entry["actor_role"] == "manager"
    assert entry["detail"]["decision"] == "acknowledge"
    # §8 / Test 6: actor ist ein HMAC-Token (== acknowledged_by), nie Klartext.
    assert entry["actor"] == acknowledged_by
    assert entry["actor"].startswith("v1:")
    # Die pseudonyme Read-Sicht legt keinen Klartext-Personenbezug offen.
    assert "user_id" not in entry
    assert "audit-mgr1@x.de" not in str(entry)


async def test_audit_requires_authentication(client: AsyncClient) -> None:
    response = await client.get("/api/v1/audit")
    assert response.status_code == 401


async def test_audit_forbidden_for_worker(client: AsyncClient) -> None:
    auth = await _auth(client, "audit-wrk@x.de", "worker")
    response = await client.get("/api/v1/audit", headers=auth)
    assert response.status_code == 403


async def test_audit_forbidden_for_technician(client: AsyncClient) -> None:
    auth = await _auth(client, "audit-tec@x.de", "technician")
    response = await client.get("/api/v1/audit", headers=auth)
    assert response.status_code == 403


async def test_audit_forbidden_for_shift_lead(client: AsyncClient) -> None:
    auth = await _auth(client, "audit-shl@x.de", "shift_lead")
    response = await client.get("/api/v1/audit", headers=auth)
    assert response.status_code == 403


async def test_audit_visible_for_manager(client: AsyncClient) -> None:
    auth = await _auth(client, "audit-mgr2@x.de", "manager")
    response = await client.get("/api/v1/audit", headers=auth)
    assert response.status_code == 200
    assert response.json() == []


async def test_audit_filters_by_action_type_and_machine_and_time(client: AsyncClient) -> None:
    auth = await _auth(client, "audit-mgr3@x.de", "manager")
    machine_id, alarm_id = await _seed_drift_alarm(client, auth)
    await client.post(f"/api/v1/reasoners/drift/alarms/{alarm_id}/acknowledge", headers=auth)

    # Treffer beim passenden action_type.
    hit = await client.get("/api/v1/audit?action_type=hitl_acknowledge", headers=auth)
    assert len(hit.json()) == 1
    # Kein Treffer bei fremdem action_type.
    miss = await client.get("/api/v1/audit?action_type=mcp_retrieval", headers=auth)
    assert miss.json() == []
    # Maschinen-Filter trifft.
    by_machine = await client.get(f"/api/v1/audit?machine_id={machine_id}", headers=auth)
    assert len(by_machine.json()) == 1
    by_other = await client.get(f"/api/v1/audit?machine_id={machine_id + 999}", headers=auth)
    assert by_other.json() == []
    # Zeitfenster: until in der Vergangenheit → leer.
    past = await client.get("/api/v1/audit?until=2000-01-01T00:00:00Z", headers=auth)
    assert past.json() == []


async def test_list_audit_service_filters_by_target_actor_and_time(
    db_session: AsyncSession,
) -> None:
    """Service-Ebene: alle Filter (target_kind/target_id/actor/since/until) greifen."""
    now = datetime.now(UTC)
    db_session.add_all(
        [
            AuditLog(
                action="mcp_retrieval",
                action_type="mcp_retrieval",
                origin="mcp",
                actor="v1:consumer",
                target_kind="machine",
                target_id=1,
                machine_id=1,
                occurred_at=now,
            ),
            AuditLog(
                action="hitl_acknowledge",
                action_type="hitl_acknowledge",
                origin="dashboard",
                actor="v1:operator",
                target_kind="alarm",
                target_id=2,
                machine_id=2,
                occurred_at=now,
            ),
        ]
    )
    await db_session.commit()

    by_kind = await list_audit(db_session, target_kind="alarm")
    assert [row.target_id for row in by_kind] == [2]

    by_target_id = await list_audit(db_session, target_id=1)
    assert [row.actor for row in by_target_id] == ["v1:consumer"]

    by_actor = await list_audit(db_session, actor="v1:operator")
    assert [row.target_kind for row in by_actor] == ["alarm"]

    # Zeitfenster: until in der Vergangenheit → leer; since in der Zukunft → leer.
    assert list(await list_audit(db_session, until=now - timedelta(days=1))) == []
    assert list(await list_audit(db_session, since=now + timedelta(days=1))) == []
    assert len(await list_audit(db_session, since=now - timedelta(days=1))) == 2
