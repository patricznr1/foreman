# ============================================================
#  FOREMAN — tests/integration/test_auth.py
#  Zweck: Register/Login (JWT) + Auth-Middleware (§4/§8).
#  Pflicht-Test-Block: Happy-Path, Fehlerfall, Auth-/Permission-Fall, Validierung.
# ============================================================
from __future__ import annotations

from httpx import AsyncClient

_CREDS = {"email": "alice@foreman.de", "password": "supersecret1"}


async def test_register_happy_path(client: AsyncClient) -> None:
    response = await client.post("/auth/register", json=_CREDS)
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == _CREDS["email"]
    assert body["role"] == "worker"
    assert "id" in body
    # Niemals den Passwort-Hash ausliefern.
    assert "password_hash" not in body
    assert "password" not in body


async def test_register_duplicate_email_conflicts(client: AsyncClient) -> None:
    await client.post("/auth/register", json=_CREDS)
    again = await client.post("/auth/register", json=_CREDS)
    assert again.status_code == 409


async def test_register_invalid_email_422(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register", json={"email": "keine-email", "password": "supersecret1"}
    )
    assert response.status_code == 422


async def test_register_short_password_422(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/register", json={"email": "bob@foreman.de", "password": "kurz"}
    )
    assert response.status_code == 422


async def test_login_returns_bearer_token(client: AsyncClient) -> None:
    await client.post("/auth/register", json=_CREDS)
    response = await client.post("/auth/login", json=_CREDS)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]


async def test_login_wrong_password_401(client: AsyncClient) -> None:
    await client.post("/auth/register", json=_CREDS)
    response = await client.post(
        "/auth/login", json={"email": _CREDS["email"], "password": "falsch12345"}
    )
    assert response.status_code == 401


async def test_login_unknown_user_401(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login", json={"email": "niemand@foreman.de", "password": "irgendwas1"}
    )
    assert response.status_code == 401


async def test_protected_route_without_token_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/lines")
    assert response.status_code == 401


async def test_protected_route_with_invalid_token_401(client: AsyncClient) -> None:
    response = await client.get(
        "/api/v1/lines", headers={"Authorization": "Bearer kaputtes.token"}
    )
    assert response.status_code == 401


async def test_protected_route_with_token_ok(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/api/v1/lines")
    assert response.status_code == 200
