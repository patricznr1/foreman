# ============================================================
#  FOREMAN — tests/integration/test_me.py
#  Zweck: GET /api/v1/me — Identität + Rolle + Per-User-Scope des eingeloggten
#         Nutzers (F5-Frontend: Rollen-Routing nach Matrix 3.1 spiegelt die
#         Backend-Autorisierung). Read-only, auth-pflichtig.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2), Integrationstest gegen die
#         echte Test-DB (§10.3).
# ============================================================
from __future__ import annotations

import asyncpg
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

_PW = "supersecret1"


async def _auth(client: AsyncClient, email: str, role: str) -> dict[str, str]:
    await client.post("/auth/register", json={"email": email, "password": _PW, "role": role})
    response = await client.post("/auth/login", json={"email": email, "password": _PW})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_me_requires_auth(client: AsyncClient) -> None:
    """Ohne Token → 401 (AuthMiddleware; /me ist nicht in der Open-Path-Whitelist)."""
    response = await client.get("/api/v1/me")
    assert response.status_code == 401


async def test_me_returns_identity_and_role(client: AsyncClient) -> None:
    """Der eingeloggte Nutzer bekommt Identität + Rolle + leeren Default-Scope."""
    auth = await _auth(client, "me-mgr@x.de", "manager")

    response = await client.get("/api/v1/me", headers=auth)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["email"] == "me-mgr@x.de"
    assert body["role"] == "manager"
    assert isinstance(body["id"], int)
    # Default-Scope ist leer (manager/technician ignorieren ihn ohnehin).
    assert body["assigned_line_ids"] == []
    assert body["assigned_machine_ids"] == []
    # Kein Klartext-Geheimnis in der Antwort (Passwort-Hash bleibt drin).
    assert "password_hash" not in body
    assert "password" not in body


async def test_me_returns_worker_machine_scope(
    client: AsyncClient, raw_conn: asyncpg.Connection
) -> None:
    """Worker-Scope (assigned_machine_ids) wird durchgereicht — das Frontend
    spiegelt damit die Server-Autorisierung (Matrix 3.1)."""
    auth = await _auth(client, "me-wrk@x.de", "worker")
    # Registrierung setzt keinen Scope — direkt in der DB setzen.
    await raw_conn.execute(
        "UPDATE users SET assigned_machine_ids = $1 WHERE email = $2",
        [101, 202],
        "me-wrk@x.de",
    )

    response = await client.get("/api/v1/me", headers=auth)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "worker"
    assert body["assigned_machine_ids"] == [101, 202]
    assert body["assigned_line_ids"] == []


async def test_me_returns_shift_lead_line_scope(
    client: AsyncClient, raw_conn: asyncpg.Connection
) -> None:
    """Schichtleiter-Scope (assigned_line_ids) wird durchgereicht."""
    auth = await _auth(client, "me-sl@x.de", "shift_lead")
    await raw_conn.execute(
        "UPDATE users SET assigned_line_ids = $1 WHERE email = $2",
        [7, 9],
        "me-sl@x.de",
    )

    response = await client.get("/api/v1/me", headers=auth)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["role"] == "shift_lead"
    assert body["assigned_line_ids"] == [7, 9]
    assert body["assigned_machine_ids"] == []
