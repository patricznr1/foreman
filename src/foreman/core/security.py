# ============================================================
#  FOREMAN — core/security.py
#  Zweck: Passwort-Hashing (bcrypt) + JWT-Erzeugung/-Prüfung.
#  Architektur-Einordnung: Auth-Querschnitt (Schicht 2). Genutzt von /auth
#         und der Auth-Dependency.
#  Sicherheit (§8/§10.4): JWT-Secret + Algorithmus aus der Config (.env),
#         niemals hartkodiert. Keine Klartext-Passwörter, keine PII in Logs.
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from foreman.config import Settings

# bcrypt verarbeitet höchstens 72 Byte — wir kürzen deterministisch (wie passlib),
# damit Hash und Prüfung konsistent bleiben.
_BCRYPT_MAX_BYTES = 72


def _prepare(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


def hash_password(password: str) -> str:
    """Erzeugt einen bcrypt-Hash für ein Passwort."""
    return bcrypt.hashpw(_prepare(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Prüft ein Passwort gegen seinen bcrypt-Hash (zeitkonstant durch bcrypt)."""
    try:
        return bcrypt.checkpw(_prepare(password), password_hash.encode("utf-8"))
    except ValueError:
        # Ungültiges/defektes Hash-Format → kein Treffer.
        return False


def create_access_token(
    subject: str,
    settings: Settings,
    *,
    expires_minutes: int | None = None,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """Erzeugt ein signiertes JWT-Access-Token mit `sub`, `iat`, `exp`."""
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=expires_minutes or settings.jwt_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "iat": now, "exp": expire}
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    """Dekodiert und validiert ein JWT. Wirft `jwt.InvalidTokenError` bei Ungültigkeit.

    Erzwingt `exp` und `iat`: ein Token ohne Ablaufdatum wird aktiv abgelehnt
    (jedes gültige Token ist endlich gültig). Audience-tragende Tokens (z. B. das
    WS-Ticket, `aud="ws"`) werden hier — ohne `audience`-Vorgabe — von PyJWT
    abgelehnt: ein WS-Ticket ist NICHT für HTTP-Routen gültig (Scope-Begrenzung).
    """
    decoded: dict[str, Any] = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "iat"], "verify_exp": True},
    )
    return decoded


# WebSocket-Ticket: kurzlebiges, WS-scoped JWT (statt das volle Session-JWT im
# ?token=-Query auszuliefern). Audience grenzt es vom HTTP-Pfad ab (§20.3/§21.8).
WS_TICKET_AUDIENCE = "ws"
DEFAULT_WS_TICKET_SECONDS = 60


def create_ws_ticket(
    subject: str,
    settings: Settings,
    *,
    expires_seconds: int = DEFAULT_WS_TICKET_SECONDS,
) -> str:
    """Erzeugt ein kurzlebiges WS-Ticket (`sub`, `iat`, `exp`, `aud="ws"`)."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": now + timedelta(seconds=expires_seconds),
        "aud": WS_TICKET_AUDIENCE,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_ws_token(token: str, settings: Settings) -> dict[str, Any]:
    """Validiert ein Token für den WebSocket: akzeptiert ein Session-JWT (ohne
    `aud`) ODER ein WS-Ticket (`aud="ws"`); ein fremdes `aud` wird abgelehnt.

    Wirft `jwt.InvalidTokenError` (inkl. `InvalidAudienceError`) bei Ungültigkeit —
    der WS-Endpoint fängt das und schließt mit 4401.
    """
    decoded: dict[str, Any] = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "iat"], "verify_exp": True, "verify_aud": False},
    )
    audience = decoded.get("aud")
    if audience is not None and audience != WS_TICKET_AUDIENCE:
        raise jwt.InvalidAudienceError("Token-Audience ist für den WebSocket nicht gültig")
    return decoded
