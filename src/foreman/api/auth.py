# ============================================================
#  FOREMAN — api/auth.py
#  Zweck: Login (JWT-Ausgabe), §4.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Offene Route (/auth/login) —
#         von der Auth-Middleware ausgenommen.
#  Betriebsmodell (§4/§19): keine Selbstregistrierung. FOREMAN ist eine
#         Werksanwendung, kein Consumer-Portal — Konten und Rollen vergibt der
#         Betreiber über `python -m foreman.db.provisioning`. Rollenvergabe ist
#         eine administrative Handlung und läuft daher nicht über HTTP.
#  Sicherheit (§8): Passwörter nur als bcrypt-Hash; Klartext-Identität in `users`.
# ============================================================
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from foreman.api.deps import SessionDep, SettingsDep
from foreman.core.security import create_access_token, verify_password
from foreman.db.models import User
from foreman.schemas.auth import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, session: SessionDep, settings: SettingsDep) -> TokenResponse:
    """Prüft Anmeldedaten und gibt ein JWT-Access-Token aus. 401 bei Fehlern."""
    user = await session.scalar(select(User).where(User.email == body.email))
    # Gleiche Fehlermeldung für „kein Nutzer" und „falsches Passwort" (kein User-Enumeration).
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Ungültige Anmeldedaten"
        )
    token = create_access_token(str(user.id), settings)
    return TokenResponse(access_token=token)
