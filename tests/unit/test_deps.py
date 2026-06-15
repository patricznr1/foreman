# ============================================================
#  FOREMAN — tests/unit/test_deps.py
#  Zweck: Auth-Dependency get_current_user (Bearer-JWT -> User), §8.
#  Direkt getestet mit Stub-Session — kein DB nötig.
# ============================================================
from __future__ import annotations

from typing import Any

import jwt
import pytest
from fastapi import HTTPException

from foreman.api.deps import get_current_user
from foreman.config import Settings
from foreman.core.security import create_access_token
from foreman.db.models import User

_S = Settings(_env_file=None, jwt_secret="deps-secret-0123456789abcdef0123456789")


class _StubSession:
    def __init__(self, user: User | None) -> None:
        self._user = user

    async def get(self, _model: Any, _pk: Any) -> User | None:
        return self._user


async def test_get_current_user_ok() -> None:
    user = User(id=5, email="a@foreman.de", password_hash="h", role="worker")
    token = create_access_token("5", _S)
    result = await get_current_user(
        session=_StubSession(user),
        settings=_S,
        authorization=f"Bearer {token}",  # type: ignore[arg-type]
    )
    assert result is user


async def test_missing_header_raises_401() -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user(session=_StubSession(None), settings=_S, authorization=None)  # type: ignore[arg-type]
    assert exc.value.status_code == 401


async def test_non_bearer_header_raises_401() -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user(
            session=_StubSession(None),
            settings=_S,
            authorization="Basic abc",  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 401


async def test_invalid_token_raises_401() -> None:
    with pytest.raises(HTTPException) as exc:
        await get_current_user(
            session=_StubSession(None),
            settings=_S,
            authorization="Bearer kaputt",  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 401


async def test_token_without_subject_raises_401() -> None:
    # exp/iat vorhanden (sonst greift bereits die require-Prüfung), aber kein sub.
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    token = jwt.encode(
        {"iat": now, "exp": now + timedelta(minutes=5)},
        _S.jwt_secret,
        algorithm=_S.jwt_algorithm,
    )
    with pytest.raises(HTTPException) as exc:
        await get_current_user(
            session=_StubSession(None),
            settings=_S,
            authorization=f"Bearer {token}",  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 401


async def test_unknown_user_raises_401() -> None:
    token = create_access_token("999", _S)
    with pytest.raises(HTTPException) as exc:
        await get_current_user(
            session=_StubSession(None),
            settings=_S,
            authorization=f"Bearer {token}",  # type: ignore[arg-type]
        )
    assert exc.value.status_code == 401
