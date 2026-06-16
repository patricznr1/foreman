# ============================================================
#  FOREMAN — mcp/auth.py
#  Zweck: Read-only-Auth des MCP-Servers (F7) — ein dedizierter Token/Key, getrennt
#         vom Plattform-JWT (Blast-Radius-Isolation für Drittsysteme). Plus eine
#         reine ASGI-Auth-Middleware (Muster der Plattform), die alles außer den
#         offenen Pfaden (/health, /metrics) hinter dem Token verriegelt, und ein
#         schlankes Token-Bucket-Limit gegen Abruf-Last (LLM10-Geist, ohne LLM).
#  Architektur-Einordnung: MCP-Schicht (F7). McpSettings als eigene Sub-Config
#         (env_prefix FOREMAN_MCP_), SecretStr für den Token (§8: nie im Klartext).
#  Sicherheit (§8): zeitkonstanter Vergleich (hmac.compare_digest), Fail-Closed
#         (ohne konfigurierten Token passiert nichts), Produktions-Fail-Fast gegen
#         schwache/fehlende Token (Repo ist öffentlich).
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

import hmac
from collections.abc import Callable
from functools import lru_cache
from time import perf_counter

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

# Mindest-Entropie des MCP-Tokens im Produktionsbetrieb.
_MIN_TOKEN_BYTES = 32
# Umgebungen, in denen ein schwaches/fehlendes Token toleriert wird (Dev/Test).
# Offene Pfade des MCP-Servers: Liveness + Prometheus-Scrape brauchen keinen Token.
OPEN_PATHS: frozenset[str] = frozenset({"/health", "/metrics"})


class McpSettings(BaseSettings):
    """Konfiguration des MCP-Servers. Einmalig aus der Umgebung geladen.

    Alle Variablen tragen den Präfix `FOREMAN_MCP_` (z. B. `FOREMAN_MCP_TOKEN=...`,
    `FOREMAN_MCP_PORT=8081`). Der Token ist SecretStr — nie im Klartext geloggt.
    """

    model_config = SettingsConfigDict(
        env_prefix="FOREMAN_MCP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Read-only-Zugangstoken für Drittsysteme. None → Fail-Closed (Server weist ab).
    token: SecretStr | None = None
    # Remote-Transport (Streamable HTTP) — Bind-Adresse/Port.
    host: str = "0.0.0.0"
    port: int = 8081
    # Abruf-Last-Bremse (Token-Bucket): Kapazität + Nachfüllrate pro Sekunde.
    rate_limit_capacity: int = Field(default=120, ge=1)
    rate_limit_refill_per_s: float = Field(default=4.0, gt=0.0)

    def require_secure_token(self, *, is_production: bool) -> None:
        """Bricht im Produktionsbetrieb ab, wenn der MCP-Token schwach/fehlend ist.

        Schützt davor, dass der MCP-Server ohne (oder mit einem zu kurzen) Token
        remote erreichbar wird — der Lese-Zugriff auf die Erkenntnisse muss
        authentifiziert sein. In Entwicklung/Tests bleibt ein leerer Token erlaubt.
        """
        if not is_production:
            return
        raw = self.token.get_secret_value() if self.token is not None else ""
        if len(raw.encode("utf-8")) < _MIN_TOKEN_BYTES:
            raise RuntimeError(
                "❌ FOREMAN_MCP_TOKEN ist im Produktionsbetrieb nicht sicher gesetzt "
                f"(mindestens {_MIN_TOKEN_BYTES} Byte erforderlich, kein leerer Token). "
                "Bitte FOREMAN_MCP_TOKEN in der .env/im Secret-Store setzen."
            )


@lru_cache(maxsize=1)
def get_mcp_settings() -> McpSettings:
    """Liefert die (einmalig geladene) MCP-Konfiguration."""
    return McpSettings()


def extract_bearer(authorization: str | None) -> str | None:
    """Liest den rohen Token aus einem `Bearer`-Header (case-insensitiv) oder None."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return authorization.split(" ", 1)[1].strip()


def verify_mcp_token(presented: str | None, settings: McpSettings) -> bool:
    """Prüft einen vorgelegten Token zeitkonstant gegen den konfigurierten (Fail-Closed)."""
    if settings.token is None or not presented:
        return False
    expected = settings.token.get_secret_value()
    if not expected:
        return False
    return hmac.compare_digest(presented, expected)


class TokenBucket:
    """Schlankes Token-Bucket gegen Abruf-Last (seedbare Uhr für deterministische Tests)."""

    def __init__(
        self,
        capacity: int | float,
        refill_per_s: float,
        *,
        clock: Callable[[], float] = perf_counter,
    ) -> None:
        self._capacity = float(capacity)
        self._refill_per_s = refill_per_s
        self._clock = clock
        self._tokens = float(capacity)
        self._last = clock()

    def allow(self) -> bool:
        """Verbraucht ein Token, wenn verfügbar; füllt anteilig der verstrichenen Zeit nach."""
        now = self._clock()
        self._tokens = min(self._capacity, self._tokens + (now - self._last) * self._refill_per_s)
        self._last = now
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return True
        return False


class McpAuthMiddleware:
    """Reine ASGI-Middleware: verriegelt alles außer den offenen Pfaden hinter dem Token.

    Fehlendes/ungültiges Credential → 401; überschrittene Abruf-Last → 429. Spiegelt
    das Plattform-Muster (api/middleware.py), nutzt aber den eigenen MCP-Token statt
    des JWT — ein Drittsystem bekommt nie ein Plattform-JWT.
    """

    def __init__(
        self, app: ASGIApp, settings: McpSettings, *, limiter: TokenBucket | None = None
    ) -> None:
        self.app = app
        self._settings = settings
        self._limiter = limiter or TokenBucket(
            settings.rate_limit_capacity, settings.rate_limit_refill_per_s
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path: str = scope.get("path", "")
        method: str = scope.get("method", "GET")
        if method == "OPTIONS" or path in OPEN_PATHS:
            await self.app(scope, receive, send)
            return

        token = extract_bearer(self._authorization_header(scope))
        if not verify_mcp_token(token, self._settings):
            await self._reject(scope, receive, send, 401, "Nicht authentifiziert")
            return
        if not self._limiter.allow():
            await self._reject(scope, receive, send, 429, "Zu viele Anfragen — bitte drosseln")
            return

        await self.app(scope, receive, send)

    @staticmethod
    def _authorization_header(scope: Scope) -> str | None:
        for key, value in scope.get("headers", []):
            if key == b"authorization":
                header_value: str = value.decode("latin-1")
                return header_value
        return None

    @staticmethod
    async def _reject(
        scope: Scope, receive: Receive, send: Send, status_code: int, detail: str
    ) -> None:
        headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else {}
        response = JSONResponse({"detail": detail}, status_code=status_code, headers=headers)
        await response(scope, receive, send)
