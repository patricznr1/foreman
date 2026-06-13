# ============================================================
#  FOREMAN — api/auth.py
#  Zweck: Registrierung + Login (JWT-Ausgabe), §4.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Offene Routen
#         (/auth/register, /auth/login) — von der Auth-Middleware ausgenommen.
#  Sicherheit (§8): Passwörter nur als bcrypt-Hash; Klartext-Identität in `users`.
# ============================================================
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from foreman.api.deps import SessionDep, SettingsDep
from foreman.core.security import create_access_token, hash_password, verify_password
from foreman.db.models import User
from foreman.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=UserRead)
async def register(body: RegisterRequest, session: SessionDep) -> User:
    """Legt einen neuen Nutzer an. 409, wenn die E-Mail bereits existiert."""
    existing = await session.scalar(select(User).where(User.email == body.email))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="E-Mail bereits registriert"
        )
    user = User(
        email=str(body.email),
        password_hash=hash_password(body.password),
        role=body.role,
    )
    session.add(user)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="E-Mail bereits registriert"
        ) from exc
    await session.refresh(user)
    return user


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
