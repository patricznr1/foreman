# ============================================================
#  FOREMAN — tests/integration/test_ws_ticket.py
#  Zweck: GET /api/v1/ws-ticket (kurzlebiges, WS-scoped Ticket) + WS-Akzeptanz.
#         Auth-pflichtig (401 ohne Token); liefert {ticket, expires_in}; das
#         Ticket ist auf HTTP-Routen NICHT gültig (Scope), am WS aber akzeptiert;
#         ein abgelaufenes Ticket schließt den WS mit 4401.
#  Architektur-Einordnung: Integrationstest gegen echte Test-DB (§10.3).
# ============================================================
from __future__ import annotations

import pytest
from httpx import AsyncClient
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from foreman.config import Settings, get_settings
from foreman.core.security import WS_TICKET_AUDIENCE, create_ws_ticket, decode_ws_token
from foreman.main import create_app
from foreman.realtime.topics import machine_topic

pytestmark = pytest.mark.integration

_PW = "supersecret1"


async def _auth(client: AsyncClient, email: str, role: str = "manager") -> dict[str, str]:
    await client.post("/auth/register", json={"email": email, "password": _PW, "role": role})
    response = await client.post("/auth/login", json={"email": email, "password": _PW})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_ws_ticket_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/ws-ticket")
    assert response.status_code == 401


async def test_ws_ticket_issues_short_lived_scoped_ticket(
    client: AsyncClient, test_settings: Settings
) -> None:
    auth = await _auth(client, "wst-mgr@x.de")
    response = await client.get("/api/v1/ws-ticket", headers=auth)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["expires_in"] == 60
    payload = decode_ws_token(body["ticket"], test_settings)
    assert payload["aud"] == WS_TICKET_AUDIENCE


async def test_ws_ticket_is_rejected_on_http_route(client: AsyncClient) -> None:
    auth = await _auth(client, "wst-mgr2@x.de")
    ticket = (await client.get("/api/v1/ws-ticket", headers=auth)).json()["ticket"]
    # Das WS-Ticket als Bearer auf einer HTTP-Route → 401 (nur am WS gültig).
    response = await client.get("/api/v1/me", headers={"Authorization": f"Bearer {ticket}"})
    assert response.status_code == 401


# — WS-Akzeptanz (synchron über Starlette TestClient, wie test_realtime_ws) —


def _app(test_settings: Settings) -> object:
    app = create_app(test_settings)
    app.dependency_overrides[get_settings] = lambda: test_settings
    return app


def _register_login(client: TestClient, email: str, role: str = "manager") -> str:
    client.post("/auth/register", json={"email": email, "password": _PW, "role": role})
    response = client.post("/auth/login", json={"email": email, "password": _PW})
    assert response.status_code == 200, response.text
    return str(response.json()["access_token"])


def test_ws_accepts_ws_ticket(test_settings: Settings, _migrated_db: None) -> None:
    with TestClient(_app(test_settings)) as client:  # type: ignore[arg-type]
        token = _register_login(client, "wst-ws@x.de")
        auth = {"Authorization": f"Bearer {token}"}
        line = client.post("/api/v1/lines", json={"label": "L"}, headers=auth).json()
        machine = client.post(
            "/api/v1/machines", json={"label": "M", "line_id": line["id"]}, headers=auth
        ).json()
        ticket = client.get("/api/v1/ws-ticket", headers=auth).json()["ticket"]

        with client.websocket_connect(f"/api/v1/ws?token={ticket}") as ws:
            ws.send_json({"action": "subscribe", "topic": machine_topic(machine["id"])})
            message = ws.receive_json()

        assert message["type"] == "update"
        assert message["topic"] == machine_topic(machine["id"])


def test_ws_rejects_expired_ticket(test_settings: Settings, _migrated_db: None) -> None:
    expired = create_ws_ticket("1", test_settings, expires_seconds=-1)
    with TestClient(_app(test_settings)) as client:  # type: ignore[arg-type]
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/api/v1/ws?token={expired}"):
                pass
    assert exc_info.value.code == 4401
