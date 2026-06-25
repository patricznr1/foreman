# ============================================================
#  FOREMAN — tests/topology/test_topology.py
#  Zweck: Tests Sektion I (Topologie). Service-Ebene: die Knoten werden EHRLICH
#         aus realen Quellen abgeleitet (data_points.source + jüngste readings-
#         Aktivität, Substrat-Health, MCP-Grenze) — kein erfundener Knoten, Status
#         nur wo messbar, simulation als intern, [VISION] leer/markiert. HTTP-Ebene:
#         Rollen-Split (Manager voll · Schichtleiter nur Status · Rest 403/401).
#  Architektur-Einordnung: Test-Infrastruktur (Quality Gates §10.3).
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import AuditLog, DataPoint, Machine, Reading
from foreman.schemas.substrate import SubstrateSmokeResult
from foreman.topology.service import build_topology

pytestmark = pytest.mark.integration

_FRESH = timedelta(hours=1)


async def _seed_source(session: AsyncSession, *, source: str, reading_age: timedelta | None) -> int:
    """Legt Maschine + Datenpunkt einer Quelle an, optional mit einem Reading."""
    machine = Machine(label="M")
    session.add(machine)
    await session.flush()
    dp = DataPoint(machine_id=machine.id, name=f"dp-{source}", kind="analog", source=source)
    session.add(dp)
    await session.flush()
    if reading_age is not None:
        session.add(Reading(data_point_id=dp.id, time=datetime.now(UTC) - reading_age, value=1.0))
    await session.commit()
    return int(machine.id)


def _by_id(view: object) -> dict[str, object]:
    return {node.id: node for node in view.nodes}  # type: ignore[attr-defined]


async def test_recent_source_is_connected_and_inbound(db_session: AsyncSession) -> None:
    await _seed_source(db_session, source="opcua", reading_age=timedelta(minutes=5))
    view = await build_topology(
        db_session,
        substrate_client=None,
        mcp_token_configured=False,
        fresh_window=_FRESH,
        probe_substrate=False,
        include_audit=True,
    )
    node = _by_id(view)["source:opcua"]
    assert node.kind == "ingest_source"
    assert node.direction == "liefert"
    assert node.status == "verbunden"
    assert node.last_activity is not None
    assert node.internal is False


async def test_source_without_readings_is_unknown_never_green(db_session: AsyncSession) -> None:
    await _seed_source(db_session, source="modbus", reading_age=None)
    view = await build_topology(
        db_session,
        substrate_client=None,
        mcp_token_configured=False,
        fresh_window=_FRESH,
        probe_substrate=False,
        include_audit=True,
    )
    node = _by_id(view)["source:modbus"]
    assert node.last_activity is None
    assert node.status == "unbekannt"
    assert node.status != "verbunden"


async def test_stale_source_is_inactive(db_session: AsyncSession) -> None:
    await _seed_source(db_session, source="s7", reading_age=timedelta(days=3))
    view = await build_topology(
        db_session,
        substrate_client=None,
        mcp_token_configured=False,
        fresh_window=_FRESH,
        probe_substrate=False,
        include_audit=True,
    )
    assert _by_id(view)["source:s7"].status == "inaktiv"


async def test_simulation_source_marked_internal(db_session: AsyncSession) -> None:
    await _seed_source(db_session, source="simulation", reading_age=timedelta(minutes=1))
    view = await build_topology(
        db_session,
        substrate_client=None,
        mcp_token_configured=False,
        fresh_window=_FRESH,
        probe_substrate=False,
        include_audit=True,
    )
    assert _by_id(view)["source:simulation"].internal is True


async def test_simulation_source_active_within_stream_window(db_session: AsyncSession) -> None:
    # Jüngstes Sim-Reading im engen Stream-Fenster (< 5 min) → verbunden (aktiv tickend).
    await _seed_source(db_session, source="simulation", reading_age=timedelta(minutes=2))
    view = await build_topology(
        db_session,
        substrate_client=None,
        mcp_token_configured=False,
        fresh_window=_FRESH,
        probe_substrate=False,
        include_audit=True,
    )
    assert _by_id(view)["source:simulation"].status == "verbunden"


async def test_simulation_source_uses_stream_window_not_generic(db_session: AsyncSession) -> None:
    # Sim-Reading älter als das enge Stream-Fenster (5 min), aber JÜNGER als das
    # generische 1h-Fenster → trotzdem inaktiv. So bleibt die Kachel mit dem Live-
    # Badge konsistent (beide messen den Sim-Stream gegen dieselbe enge Schwelle).
    await _seed_source(db_session, source="simulation", reading_age=timedelta(minutes=10))
    view = await build_topology(
        db_session,
        substrate_client=None,
        mcp_token_configured=False,
        fresh_window=_FRESH,
        probe_substrate=False,
        include_audit=True,
    )
    assert _by_id(view)["source:simulation"].status == "inaktiv"


async def test_external_source_keeps_generic_fresh_window(db_session: AsyncSession) -> None:
    # Nur die interne Sim nutzt das enge Stream-Fenster — eine externe Quelle 10 min
    # alt bleibt unter dem generischen 1h-Fenster „verbunden" (keine Sonderbehandlung).
    await _seed_source(db_session, source="opcua", reading_age=timedelta(minutes=10))
    view = await build_topology(
        db_session,
        substrate_client=None,
        mcp_token_configured=False,
        fresh_window=_FRESH,
        probe_substrate=False,
        include_audit=True,
    )
    assert _by_id(view)["source:opcua"].status == "verbunden"


async def test_unconfigured_substrate_is_inactive(db_session: AsyncSession) -> None:
    view = await build_topology(
        db_session,
        substrate_client=None,
        mcp_token_configured=False,
        fresh_window=_FRESH,
        probe_substrate=True,
        include_audit=True,
    )
    assert _by_id(view)["substrate"].status == "inaktiv"
    assert _by_id(view)["substrate"].direction == "beides"


async def test_mcp_node_reflects_audit_activity_when_configured(db_session: AsyncSession) -> None:
    db_session.add(
        AuditLog(
            action="mcp_retrieval",
            action_type="mcp_retrieval",
            origin="mcp",
            actor="v1:consumer",
            actor_role="mcp_client",
            occurred_at=datetime.now(UTC),
        )
    )
    await db_session.commit()
    view = await build_topology(
        db_session,
        substrate_client=None,
        mcp_token_configured=True,
        fresh_window=_FRESH,
        probe_substrate=False,
        include_audit=True,
    )
    mcp = _by_id(view)["mcp"]
    assert mcp.kind == "mcp_boundary"
    assert mcp.direction == "liest"
    assert mcp.status == "verbunden"
    assert mcp.detail is not None
    assert mcp.detail["consumer_count"] == 1


async def test_vision_category_marked_and_never_connected(db_session: AsyncSession) -> None:
    view = await build_topology(
        db_session,
        substrate_client=None,
        mcp_token_configured=False,
        fresh_window=_FRESH,
        probe_substrate=False,
        include_audit=True,
    )
    assert len(view.vision) >= 1
    assert all(node.vision is True for node in view.vision)
    assert all(node.status != "verbunden" for node in view.vision)
    # Kein erfundenes Drittsystem im realen Knoten-Set.
    real_kinds = {node.kind for node in view.nodes}
    assert real_kinds <= {"ingest_source", "substrate", "mcp_boundary"}


# --- HTTP-Ebene: Rollen-Split ---

_PW = "supersecret1"


async def _auth(client: AsyncClient, email: str, role: str) -> dict[str, str]:
    await client.post("/auth/register", json={"email": email, "password": _PW, "role": role})
    response = await client.post("/auth/login", json={"email": email, "password": _PW})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_topology_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/topology")).status_code == 401


async def test_topology_forbidden_for_worker_and_technician(client: AsyncClient) -> None:
    wrk = await _auth(client, "topo-wrk@x.de", "worker")
    tec = await _auth(client, "topo-tec@x.de", "technician")
    assert (await client.get("/api/v1/topology", headers=wrk)).status_code == 403
    assert (await client.get("/api/v1/topology", headers=tec)).status_code == 403


async def test_topology_full_for_manager(client: AsyncClient) -> None:
    auth = await _auth(client, "topo-mgr@x.de", "manager")
    response = await client.get("/api/v1/topology", headers=auth)
    assert response.status_code == 200, response.text
    body = response.json()
    assert "nodes" in body and "vision" in body
    assert len(body["vision"]) >= 1


async def test_topology_status_only_for_shift_lead(client: AsyncClient) -> None:
    auth = await _auth(client, "topo-shl@x.de", "shift_lead")
    response = await client.get("/api/v1/topology", headers=auth)
    assert response.status_code == 200, response.text
    body = response.json()
    # Schichtleiter sieht Verbindungsstatus, aber KEINE Audit-abgeleiteten Details.
    mcp = next(node for node in body["nodes"] if node["kind"] == "mcp_boundary")
    assert mcp["status"] is not None
    assert mcp["detail"] is None or "consumer_count" not in (mcp["detail"] or {})


# --- Substrat-Live-Probe (best-effort smoke) ---


async def _build_with_substrate(db_session: AsyncSession) -> object:
    return await build_topology(
        db_session,
        substrate_client=object(),  # nicht None → Probe-Pfad; smoke wird gemockt
        mcp_token_configured=False,
        fresh_window=_FRESH,
        probe_substrate=True,
        include_audit=True,
    )


async def test_substrate_probe_connected(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _ok(_client: object) -> SubstrateSmokeResult:
        return SubstrateSmokeResult(ok=True, latency_ms=1.5)

    monkeypatch.setattr("foreman.topology.service.run_substrate_smoke", _ok)
    node = _by_id(await _build_with_substrate(db_session))["substrate"]
    assert node.status == "verbunden"
    assert node.detail is not None and node.detail["latency_ms"] == 1.5


async def test_substrate_probe_failed_result_is_disturbed(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _bad(_client: object) -> SubstrateSmokeResult:
        return SubstrateSmokeResult(ok=False, latency_ms=0.0, detail="kein Round-Trip")

    monkeypatch.setattr("foreman.topology.service.run_substrate_smoke", _bad)
    assert _by_id(await _build_with_substrate(db_session))["substrate"].status == "gestört"


async def test_substrate_probe_exception_is_disturbed(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _boom(_client: object) -> SubstrateSmokeResult:
        raise RuntimeError("Substrat nicht erreichbar")

    monkeypatch.setattr("foreman.topology.service.run_substrate_smoke", _boom)
    node = _by_id(await _build_with_substrate(db_session))["substrate"]
    assert node.status == "gestört"
    assert node.detail is not None and node.detail["probe_error"] is True
