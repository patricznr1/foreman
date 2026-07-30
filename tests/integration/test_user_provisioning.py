# ============================================================
#  FOREMAN — tests/integration/test_user_provisioning.py
#  Zweck: Nutzer-Anlage über den Betreiber-Pfad (`db/provisioning.create_user`) —
#         der EINZIGE Weg, eine Rolle zu vergeben (§4/§19, OWASP A01).
#  Architektur-Einordnung: Integrationstest gegen die echte Test-DB (§10.3).
#  Pflicht-Test-Block: Happy-Path, Fehlerfall, Validierung, Contract.
# ============================================================
from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.core.roles import Role
from foreman.core.security import verify_password
from foreman.db.models import User
from foreman.db.provisioning import create_user

pytestmark = pytest.mark.integration

AuthHeaders = Callable[[str, str], Awaitable[dict[str, str]]]

_PW = "supersecret1"


async def test_create_user_stores_role_and_bcrypt_hash(db_session: AsyncSession) -> None:
    """Happy-Path: die Rolle landet wie angefordert, das Passwort nur als Hash."""
    user = await create_user(
        db_session, email="prov-mgr@foreman.de", password=_PW, role=Role.MANAGER
    )

    assert user.role == "manager"
    assert user.email == "prov-mgr@foreman.de"
    # Klartext taucht nirgends auf; der Hash verifiziert das Passwort.
    assert user.password_hash != _PW
    assert verify_password(_PW, user.password_hash)


async def test_create_user_rejects_duplicate_without_overwriting(
    db_session: AsyncSession,
) -> None:
    """Ein zweiter Aufruf legt NICHT an und ändert die bestehende Rolle nicht.

    Das ist die Kern-Eigenschaft: Nutzer-Anlage darf niemals ein stiller
    Rechte-Wechsel sein."""
    await create_user(db_session, email="prov-dup@foreman.de", password=_PW, role=Role.WORKER)

    with pytest.raises(ValueError, match="bereits vergeben"):
        await create_user(db_session, email="prov-dup@foreman.de", password=_PW, role=Role.MANAGER)

    rows = (await db_session.scalars(select(User).where(User.email == "prov-dup@foreman.de"))).all()
    assert len(rows) == 1
    assert rows[0].role == "worker", "❌ Die bestehende Rolle wurde überschrieben"


async def test_create_user_rejects_invalid_email(db_session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="E-Mail"):
        await create_user(db_session, email="keine-email", password=_PW, role=Role.WORKER)


async def test_create_user_rejects_too_short_password(db_session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="Passwort"):
        await create_user(
            db_session, email="prov-short@foreman.de", password="kurz", role=Role.WORKER
        )


@pytest.mark.parametrize("role", [role.value for role in Role])
async def test_every_role_can_be_provisioned_and_login(
    client: AsyncClient, auth_headers_for: AuthHeaders, role: str
) -> None:
    """Contract: jede Rolle der Matrix 3.1 ist anlegbar und einloggbar — und die
    Rolle, die `/me` zurückgibt, ist genau die angelegte."""
    headers = await auth_headers_for(f"prov-{role}@foreman.de", role)

    response = await client.get("/api/v1/me", headers=headers)

    assert response.status_code == 200, response.text
    assert response.json()["role"] == role
