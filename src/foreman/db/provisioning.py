# ============================================================
#  FOREMAN — db/provisioning.py
#  Zweck: Nutzer-Anlage durch den Betreiber — der einzige Weg, ein Konto und
#         damit eine Rolle zu vergeben (§4/§19). FOREMAN ist eine Werksanwendung,
#         kein Consumer-Portal: Rollenvergabe ist eine administrative Handlung
#         und setzt Betreiber-Zugriff voraus, nicht bloß Netzwerkzugang.
#  Architektur-Einordnung: Persistenz-naher Schreibpfad (Schicht 1) + CLI-Einstieg
#         (Vordergrund-Prozess, Muster `embeddings/backfill.py`).
#         Aufruf: `python -m foreman.db.provisioning --email … --role manager`.
#  Sicherheit (§8/§19): Passwort nie über `argv` (Shell-Historie) — interaktiv per
#         getpass oder über FOREMAN_SEED_PASSWORD. Es landet ausschließlich als
#         bcrypt-Hash in der DB und niemals in einem Log.
#  Konvention (§6): Type Hints überall, deutsche Kommentare/Fehlermeldungen,
#         englische Bezeichner, Logs mit Emoji-Prefix.
# ============================================================
from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from foreman.config import get_settings
from foreman.core.roles import Role
from foreman.core.security import hash_password
from foreman.db.models import User
from foreman.logging_setup import OK, get_logger
from foreman.schemas.auth import PASSWORD_MAX, PASSWORD_MIN

logger = get_logger("foreman.db.provisioning")

# Umgebungsvariable für nicht-interaktive Läufe (CI, Container-Start).
PASSWORD_ENV_VAR = "FOREMAN_SEED_PASSWORD"

_EMAIL_ADAPTER: TypeAdapter[EmailStr] = TypeAdapter(EmailStr)


async def create_user(session: AsyncSession, *, email: str, password: str, role: Role) -> User:
    """Legt einen Nutzer mit fester Rolle an und gibt ihn zurück.

    Validiert E-Mail und Passwort-Länge gegen dieselben Grenzen wie der
    Login-Vertrag (`schemas/auth.py`). Die Rolle ist typisiert (`Role`), damit
    nur Werte aus der Rollenmatrix (§5) in die Spalte gelangen.

    Wirft `ValueError`, wenn die E-Mail ungültig ist, das Passwort außerhalb der
    Grenzen liegt oder die E-Mail bereits vergeben ist. Ein bestehender Nutzer
    wird NIE überschrieben — Rollen-Änderung ist bewusst kein Fall dieser
    Funktion (kein stiller Rechte-Wechsel).
    """
    try:
        normalized_email = str(_EMAIL_ADAPTER.validate_python(email))
    except ValidationError as exc:
        raise ValueError(f"Ungültige E-Mail-Adresse: {email}") from exc

    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        raise ValueError(
            f"Passwort muss zwischen {PASSWORD_MIN} und {PASSWORD_MAX} Zeichen lang sein."
        )

    existing = await session.scalar(select(User).where(User.email == normalized_email))
    if existing is not None:
        raise ValueError(f"E-Mail bereits vergeben: {normalized_email}")

    user = User(
        email=normalized_email,
        password_hash=hash_password(password),
        role=role.value,
    )
    session.add(user)
    await session.flush()
    await session.refresh(user)
    return user


def _read_password() -> str:
    """Holt das Passwort aus der Umgebung oder fragt es interaktiv ab.

    Bewusst NICHT aus `argv`: Kommandozeilen landen in der Shell-Historie und in
    der Prozessliste."""
    from_env = os.environ.get(PASSWORD_ENV_VAR)
    if from_env:
        return from_env
    return getpass.getpass("Passwort für den neuen Nutzer: ")


async def _run(*, email: str, role: Role, password: str, db_url: str | None) -> int:
    url = db_url if db_url is not None else get_settings().database_url
    engine = create_async_engine(url)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            user = await create_user(session, email=email, password=password, role=role)
            await session.commit()
            user_id: int = user.id
    finally:
        await engine.dispose()
    # Kein Passwort, kein Hash im Log — nur Identität und Rolle.
    logger.info("%s Nutzer angelegt: %s (id=%d, Rolle=%s)", OK, email, user_id, role.value)
    return user_id


def main() -> None:  # pragma: no cover - CLI-Einstieg
    parser = argparse.ArgumentParser(
        description=(
            "Legt einen FOREMAN-Nutzer an (der einzige Weg, eine Rolle zu vergeben). "
            f"Passwort über {PASSWORD_ENV_VAR} oder interaktiv — nie als Argument."
        )
    )
    parser.add_argument("--email", type=str, required=True, help="E-Mail des neuen Nutzers.")
    parser.add_argument(
        "--role",
        type=str,
        required=True,
        choices=[role.value for role in Role],
        help="Rolle des neuen Nutzers (Rollenmatrix 3.1).",
    )
    parser.add_argument(
        "--db-url", type=str, default=None, help="DB-URL (Default aus der Config/.env)."
    )
    args = parser.parse_args()

    try:
        asyncio.run(
            _run(
                email=args.email,
                role=Role(args.role),
                password=_read_password(),
                db_url=args.db_url,
            )
        )
    except ValueError as exc:
        print(f"❌ {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":  # pragma: no cover
    main()
