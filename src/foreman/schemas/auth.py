# ============================================================
#  FOREMAN — schemas/auth.py
#  Zweck: Register-/Login-/Token-Schemas.
#  Architektur-Einordnung: API-Vertrag der Auth-Routen (Schicht 2).
# ============================================================
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# bcrypt verarbeitet max. 72 Byte — Passwort-Länge entsprechend begrenzen.
PASSWORD_MIN = 8
PASSWORD_MAX = 72


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=PASSWORD_MIN, max_length=PASSWORD_MAX)
    role: str = Field(default="worker", max_length=32)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=PASSWORD_MAX)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: str
    created_at: datetime


class CurrentUserRead(BaseModel):
    """`/api/v1/me` — Identität, Rolle und Per-User-Scope des eingeloggten Nutzers.

    Read-only-Spiegel der Server-Autorisierung (Rollenmatrix 3.1) fürs Frontend:
    Das Frontend leitet daraus sichtbare Navigation/Sichten ab, ersetzt die
    serverseitige Autorisierung (`can_subscribe`, §20.4) aber nicht. Enthält keine
    PII über die eigene Identität hinaus (kein `password_hash`).
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: str
    assigned_line_ids: list[int]
    assigned_machine_ids: list[int]
