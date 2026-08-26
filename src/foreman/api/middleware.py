# ============================================================
#  FOREMAN — api/middleware.py
#  Zweck: Auth-Middleware — schützt alle Routen außer den offenen (§4).
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Offen: /health, /metrics,
#         /auth/login, OpenAPI-Doku. Alles andere braucht ein gültiges
#         Bearer-JWT, sonst 401.
#  Offene Schreib-Route ist ausschließlich /auth/login: FOREMAN kennt keine
#         Selbstregistrierung, Konten legt der Betreiber per CLI an (§4).
#  Umsetzung als REINE ASGI-Middleware (kein BaseHTTPMiddleware): wickelt die
#  nachgelagerte App inline ab — performanter und ohne Child-Task-Eigenheiten.
# ============================================================
from __future__ import annotations

import jwt
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from foreman.config import Settings
from foreman.core.security import decode_access_token

# Offene Pfade (kein Token nötig). OpenAPI-Doku als Präfixe (siehe _is_open).
OPEN_PATHS: frozenset[str] = frozenset(
    {
        "/health",
        # Bereitschaftssonde: offen aus demselben Grund wie /health — der
        # Orchestrierer, der sie abfragt, hat kein Token und soll keines haben.
        # Sie gibt keine Ressourcendaten heraus, nur „bereit" oder „nicht".
        "/readyz",
        "/metrics",  # Prometheus-Scraper (kein JWT) — §11.2, ab F4
        "/auth/login",
        "/",
        "/docs",
        "/redoc",
        "/openapi.json",
    }
)
# Pfade, unter denen die Doku eigene Unterseiten führt (z. B.
# /docs/oauth2-redirect). Der Vergleich unten nimmt sie als NAMEN, nicht als
# Anfangsbuchstaben: `/docs-admin` fängt zwar mit „/docs" an, ist aber keine Doku.
_OPEN_PREFIXES: tuple[str, ...] = ("/docs", "/redoc", "/openapi.json")


class AuthMiddleware:
    """Erzwingt ein gültiges Bearer-JWT auf geschützten Pfaden (ASGI-Middleware)."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self._settings = settings

    def _is_open(self, path: str) -> bool:
        """Ob dieser Pfad ohne Token erreichbar ist.

        Der Präfix-Zweig verlangt einen Trennstrich: `/docs/oauth2-redirect` gehört
        zur Doku, `/docs-admin` nicht. Ohne den Strich hinge die Grenze daran, dass
        zufällig kein geschützter Pfad mit einem Doku-Namen beginnt — eine Regel,
        die aus Zufall hält und beim nächsten Endpunkt kippt.
        """
        if path in OPEN_PATHS:
            return True
        return any(path.startswith(prefix + "/") for prefix in _OPEN_PREFIXES)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # KEINE Ausnahme für OPTIONS: FOREMAN richtet keine CORS-Middleware ein,
        # das Frontend spricht über einen Proxy (frontend/next.config.ts). Eine
        # tokenfreie Methode deckt hier nichts ab, was gebraucht würde, gäbe aber
        # jedem die Möglichkeit, Pfade auf ihre Existenz abzuklopfen. Kommt CORS
        # später, gehört die Ausnahme in die CORSMiddleware, nicht in die Auth.
        path: str = scope.get("path", "")
        if self._is_open(path):
            await self.app(scope, receive, send)
            return

        authorization = self._authorization_header(scope)
        if not authorization or not authorization.lower().startswith("bearer "):
            await self._unauthorized(scope, receive, send, "Nicht authentifiziert")
            return
        token = authorization.split(" ", 1)[1].strip()
        try:
            decode_access_token(token, self._settings)
        except jwt.InvalidTokenError:
            await self._unauthorized(scope, receive, send, "Ungültiges oder abgelaufenes Token")
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
    async def _unauthorized(scope: Scope, receive: Receive, send: Send, detail: str) -> None:
        response = JSONResponse(
            {"detail": detail},
            status_code=401,
            headers={"WWW-Authenticate": "Bearer"},
        )
        await response(scope, receive, send)
