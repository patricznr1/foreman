# ============================================================
#  FOREMAN — tests/integration/test_substrate_smoke.py
#  Zweck: GET /api/v1/substrate/smoke (§9) + Non-Blocking-Start.
#  Substrat wird gemockt (httpx.MockTransport) bzw. ist nicht konfiguriert.
# ============================================================
from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable

import httpx
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from foreman.api.deps import get_substrate_client
from foreman.config import Settings
from foreman.main import create_app
from foreman.substrate.client import SubstrateClient


def _smoke_handler(ok: bool) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if request.url.path == "/remember":
            return httpx.Response(200, json={"stored": True})
        if request.url.path == "/recall":
            query = body["query"]
            if ok:
                return httpx.Response(200, json={"results": [{"content": f"echo {query}"}]})
            return httpx.Response(200, json={"results": []})
        return httpx.Response(404)

    return handler


async def test_smoke_endpoint_not_configured_returns_false(
    auth_client: AsyncClient,
) -> None:
    # test_settings.substrate_base_url ist None → ok:false, kein Serverfehler.
    response = await auth_client.get("/api/v1/substrate/smoke")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "nicht konfiguriert" in body["detail"]


async def test_smoke_endpoint_ok_with_mocked_substrate(
    app: FastAPI, auth_client: AsyncClient
) -> None:
    mock_http = httpx.AsyncClient(
        transport=httpx.MockTransport(_smoke_handler(ok=True)),
        base_url="http://substrate.test",
    )
    sub = SubstrateClient(base_url="http://substrate.test", token="t", client=mock_http)

    async def _override() -> AsyncIterator[SubstrateClient]:
        yield sub

    app.dependency_overrides[get_substrate_client] = _override
    response = await auth_client.get("/api/v1/substrate/smoke")
    assert response.status_code == 200
    assert response.json()["ok"] is True
    await mock_http.aclose()


async def test_smoke_endpoint_requires_auth(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/substrate/smoke")).status_code == 401


async def test_startup_smoke_is_non_blocking(
    test_settings: Settings, _migrated_db: None
) -> None:
    """Ein Substrat-Fehlschlag beim Start darf die App NICHT abbrechen (§9)."""
    # Konfiguriert, aber unerreichbar → Smoke schlägt fehl, Start läuft weiter.
    settings = test_settings.model_copy(
        update={"substrate_base_url": "http://127.0.0.1:9", "substrate_timeout_s": 1.0}
    )
    application = create_app(settings)
    async with LifespanManager(application):
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://testserver") as http:
            # App ist trotz fehlgeschlagenem Substrat-Smoke gestartet und gesund.
            assert (await http.get("/health")).status_code == 200
