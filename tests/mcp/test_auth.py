# ============================================================
#  FOREMAN — tests/mcp/test_auth.py
#  Zweck: Die read-only MCP-Auth festnageln — gültiger Token passiert, fehlendes/
#         ungültiges Credential wird sauber abgewiesen (401), offene Pfade
#         (/health, /metrics) brauchen keinen Token, Abruf-Last wird gebremst (429),
#         und ein schwacher/fehlender Token bricht den Produktionsstart ab.
#  Architektur-Einordnung: MCP-Schicht (F7). Reine Funktionen + ASGI-Middleware
#         ohne DB — schnelle, deterministische Tests.
# ============================================================
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest
from pydantic import SecretStr

from foreman.mcp.auth import (
    McpAuthMiddleware,
    McpSettings,
    extract_bearer,
    verify_mcp_token,
)

_TOKEN = "mcp-secret-token-0123456789abcdef"


def _settings(token: str | None = _TOKEN) -> McpSettings:
    return McpSettings(_env_file=None, token=SecretStr(token) if token is not None else None)


# ============================================================
#  Pure Funktionen
# ============================================================
def test_verify_mcp_token_accepts_exact_match() -> None:
    assert verify_mcp_token(_TOKEN, _settings()) is True


def test_verify_mcp_token_rejects_wrong_or_missing() -> None:
    settings = _settings()
    assert verify_mcp_token("falsch", settings) is False
    assert verify_mcp_token(None, settings) is False
    assert verify_mcp_token("", settings) is False


def test_verify_mcp_token_rejects_when_no_token_configured() -> None:
    # Ohne konfigurierten Token darf NICHTS passieren (Fail-Closed).
    assert verify_mcp_token(_TOKEN, _settings(token=None)) is False


def test_extract_bearer_parses_scheme_case_insensitively() -> None:
    assert extract_bearer("Bearer abc") == "abc"
    assert extract_bearer("bearer abc") == "abc"
    assert extract_bearer(None) is None
    assert extract_bearer("Basic abc") is None


def test_require_secure_token_blocks_weak_token_in_production() -> None:
    with pytest.raises(RuntimeError, match="MCP"):
        _settings(token=None).require_secure_token(is_production=True)
    with pytest.raises(RuntimeError, match="MCP"):
        _settings(token="kurz").require_secure_token(is_production=True)
    # Entwicklung toleriert schwache/fehlende Token; starker Token ist immer ok.
    _settings(token=None).require_secure_token(is_production=False)
    _settings().require_secure_token(is_production=True)


# ============================================================
#  ASGI-Middleware
# ============================================================
class _Downstream:
    """Nachgelagerte ASGI-App, die merkt, ob sie aufgerufen wurde."""

    def __init__(self) -> None:
        self.called = False

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        self.called = True
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})


async def _drive(
    middleware: Callable[[Any, Any, Any], Awaitable[None]],
    *,
    path: str = "/mcp",
    method: str = "POST",
    headers: dict[str, str] | None = None,
) -> int | None:
    scope: dict[str, Any] = {
        "type": "http",
        "path": path,
        "method": method,
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
    }
    statuses: list[int] = []

    async def receive() -> dict[str, Any]:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: dict[str, Any]) -> None:
        if message["type"] == "http.response.start":
            statuses.append(message["status"])

    await middleware(scope, receive, send)
    return statuses[0] if statuses else None


async def test_middleware_allows_valid_token() -> None:
    downstream = _Downstream()
    middleware = McpAuthMiddleware(downstream, _settings())
    status = await _drive(middleware, headers={"Authorization": f"Bearer {_TOKEN}"})
    assert status == 200
    assert downstream.called is True


async def test_middleware_rejects_missing_credential() -> None:
    downstream = _Downstream()
    middleware = McpAuthMiddleware(downstream, _settings())
    status = await _drive(middleware)  # kein Authorization-Header
    assert status == 401
    assert downstream.called is False


async def test_middleware_rejects_invalid_token() -> None:
    downstream = _Downstream()
    middleware = McpAuthMiddleware(downstream, _settings())
    status = await _drive(middleware, headers={"Authorization": "Bearer falsch"})
    assert status == 401
    assert downstream.called is False


async def test_middleware_open_paths_need_no_token() -> None:
    for path in ("/health", "/metrics"):
        downstream = _Downstream()
        middleware = McpAuthMiddleware(downstream, _settings())
        status = await _drive(middleware, path=path, method="GET")
        assert status == 200
        assert downstream.called is True


async def test_middleware_rate_limits_excess_requests() -> None:
    from foreman.mcp.auth import TokenBucket

    # Kapazität 2, kein Refill (eingefrorene Uhr) → der 3. Aufruf wird gebremst.
    limiter = TokenBucket(capacity=2, refill_per_s=0.0, clock=lambda: 0.0)
    downstream = _Downstream()
    middleware = McpAuthMiddleware(downstream, _settings(), limiter=limiter)
    headers = {"Authorization": f"Bearer {_TOKEN}"}
    assert await _drive(middleware, headers=headers) == 200
    assert await _drive(middleware, headers=headers) == 200
    assert await _drive(middleware, headers=headers) == 429
