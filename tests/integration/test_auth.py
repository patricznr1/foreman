# ============================================================
#  FOREMAN — tests/integration/test_auth.py
#  Zweck: Login (JWT) + Auth-Middleware (§4/§8) + der Nachweis, dass FOREMAN
#         keine Selbstregistrierung kennt (§4/§19).
#  Pflicht-Test-Block: Happy-Path, Fehlerfall, Auth-/Permission-Fall, Validierung.
# ============================================================
from __future__ import annotations

from collections.abc import Awaitable, Callable

from httpx import AsyncClient

from foreman.api.middleware import OPEN_PATHS

AuthHeaders = Callable[[str, str], Awaitable[dict[str, str]]]

_CREDS = {"email": "alice@foreman.de", "password": "supersecret1"}


# --- Keine Selbstregistrierung (§4/§19) ---
async def test_register_is_blocked_by_middleware_without_token(client: AsyncClient) -> None:
    """Ohne Token endet der Versuch an der Auth-Middleware (401) — der Pfad steht
    nicht auf der Open-Path-Whitelist. Das ist die äußere Schicht."""
    response = await client.post("/auth/register", json={**_CREDS, "role": "manager"})
    assert response.status_code == 401


async def test_register_route_does_not_exist_even_when_authenticated(
    client: AsyncClient, auth_headers_for: AuthHeaders
) -> None:
    """Die innere Schicht: auch mit gültigem Token existiert die Route nicht (404).
    Rollen werden ausschließlich administrativ vergeben, nicht über HTTP (§4)."""
    headers = await auth_headers_for("reg-probe@foreman.de", "manager")

    response = await client.post(
        "/auth/register", json={**_CREDS, "role": "manager"}, headers=headers
    )

    assert response.status_code == 404


def test_register_is_not_in_open_paths() -> None:
    """Die Auth-Whitelist führt als offene Schreib-Route nur den Login (§4)."""
    assert "/auth/register" not in OPEN_PATHS
    assert "/auth/login" in OPEN_PATHS


# --- Login ---
async def test_login_returns_bearer_token(
    client: AsyncClient, auth_headers_for: AuthHeaders
) -> None:
    await auth_headers_for(_CREDS["email"], "worker")
    response = await client.post("/auth/login", json=_CREDS)
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert isinstance(body["access_token"], str) and body["access_token"]


async def test_login_wrong_password_401(client: AsyncClient, auth_headers_for: AuthHeaders) -> None:
    await auth_headers_for(_CREDS["email"], "worker")
    response = await client.post(
        "/auth/login", json={"email": _CREDS["email"], "password": "falsch12345"}
    )
    assert response.status_code == 401


async def test_login_unknown_user_401(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login", json={"email": "niemand@foreman.de", "password": "irgendwas1"}
    )
    assert response.status_code == 401


async def test_login_invalid_email_422(client: AsyncClient) -> None:
    response = await client.post(
        "/auth/login", json={"email": "keine-email", "password": "supersecret1"}
    )
    assert response.status_code == 422


# --- Auth-Middleware ---
async def test_protected_route_without_token_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/lines")
    assert response.status_code == 401


async def test_protected_route_with_invalid_token_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/lines", headers={"Authorization": "Bearer kaputtes.token"})
    assert response.status_code == 401


async def test_protected_route_with_token_ok(auth_client: AsyncClient) -> None:
    response = await auth_client.get("/api/v1/lines")
    assert response.status_code == 200
