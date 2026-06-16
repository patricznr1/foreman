# ============================================================
#  FOREMAN — tests/integration/test_realtime_ws.py
#  Zweck: Der gemultiplexte WS-Endpoint (F5, /api/v1/ws). Synchron über Starlette
#         TestClient (führt den Lifespan aus → globaler Engine + Listener gegen die
#         Test-DB). Deckt ab: Auth-Reject ohne Token, Snapshot beim subscribe,
#         Abo-AUTORISIERUNG (default-deny), und den ECHTEN End-to-End-Live-Push
#         (POST /readings → pg_notify → Listener → Hub → WS) — kein Mock.
# ============================================================
from __future__ import annotations

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from foreman.config import Settings, get_settings
from foreman.main import create_app
from foreman.realtime.topics import machine_topic, trend_topic

pytestmark = pytest.mark.integration

_PW = "supersecret1"


def _app(test_settings: Settings) -> object:
    app = create_app(test_settings)
    app.dependency_overrides[get_settings] = lambda: test_settings
    return app


def _register_login(client: TestClient, email: str, role: str) -> str:
    client.post("/auth/register", json={"email": email, "password": _PW, "role": role})
    response = client.post("/auth/login", json={"email": email, "password": _PW})
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def _seed_machine(client: TestClient, auth: dict[str, str]) -> int:
    line = client.post("/api/v1/lines", json={"label": "L"}, headers=auth).json()
    machine = client.post(
        "/api/v1/machines", json={"label": "M", "line_id": line["id"]}, headers=auth
    ).json()
    return int(machine["id"])


def test_ws_rejects_connection_without_token(test_settings: Settings, _migrated_db: None) -> None:
    with TestClient(_app(test_settings)) as client:  # type: ignore[arg-type]
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/api/v1/ws"):
                pass


def test_ws_manager_subscribe_machine_receives_snapshot(
    test_settings: Settings, _migrated_db: None
) -> None:
    with TestClient(_app(test_settings)) as client:  # type: ignore[arg-type]
        token = _register_login(client, "ws-mgr@x.de", "manager")
        auth = {"Authorization": f"Bearer {token}"}
        machine_id = _seed_machine(client, auth)

        with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
            ws.send_json({"action": "subscribe", "topic": machine_topic(machine_id)})
            message = ws.receive_json()

        assert message["type"] == "update"
        assert message["topic"] == machine_topic(machine_id)
        assert message["data"]["status"] == "healthy"


def test_ws_worker_subscribe_unassigned_machine_is_forbidden(
    test_settings: Settings, _migrated_db: None
) -> None:
    with TestClient(_app(test_settings)) as client:  # type: ignore[arg-type]
        manager = _register_login(client, "ws-mgr2@x.de", "manager")
        machine_id = _seed_machine(client, {"Authorization": f"Bearer {manager}"})
        worker = _register_login(client, "ws-wrk@x.de", "worker")

        with client.websocket_connect(f"/api/v1/ws?token={worker}") as ws:
            ws.send_json({"action": "subscribe", "topic": machine_topic(machine_id)})
            message = ws.receive_json()

        assert message["type"] == "error"
        assert message["reason"] == "forbidden"


def test_ws_live_push_on_new_reading(test_settings: Settings, _migrated_db: None) -> None:
    with TestClient(_app(test_settings)) as client:  # type: ignore[arg-type]
        token = _register_login(client, "ws-mgr3@x.de", "manager")
        auth = {"Authorization": f"Bearer {token}"}
        line = client.post("/api/v1/lines", json={"label": "L"}, headers=auth).json()
        machine = client.post(
            "/api/v1/machines", json={"label": "M", "line_id": line["id"]}, headers=auth
        ).json()
        data_point = client.post(
            "/api/v1/data_points",
            json={"machine_id": machine["id"], "name": "vib", "kind": "analog"},
            headers=auth,
        ).json()
        topic = trend_topic(data_point["id"])

        with client.websocket_connect(f"/api/v1/ws?token={token}") as ws:
            ws.send_json({"action": "subscribe", "topic": topic})
            snapshot = ws.receive_json()
            assert snapshot["type"] == "update"
            assert snapshot["topic"] == topic

            # Echtes E2E: POST → pg_notify → Listener → Hub → WS-Push.
            posted = client.post(
                "/api/v1/readings",
                json={
                    "readings": [
                        {
                            "data_point_id": data_point["id"],
                            "time": "2026-06-16T10:00:00+00:00",
                            "value": 2.5,
                        }
                    ]
                },
                headers=auth,
            )
            assert posted.status_code == 201, posted.text

            push = ws.receive_json()
            assert push["type"] == "update"
            assert push["topic"] == topic


def test_ws_rejects_token_with_non_integer_subject(
    test_settings: Settings, _migrated_db: None
) -> None:
    # Manipuliertes/fehlerhaftes Token (sub nicht numerisch) → sauberer 4401-Close,
    # keine unbehandelte ValueError (CodeRabbit-Finding PR #18).
    from foreman.core.security import create_access_token

    token = create_access_token("not-an-int", test_settings)
    with TestClient(_app(test_settings)) as client:  # type: ignore[arg-type]
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/api/v1/ws?token={token}"):
                pass
    assert exc_info.value.code == 4401
