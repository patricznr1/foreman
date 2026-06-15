# ============================================================
#  FOREMAN — tests/unit/test_security.py
#  Zweck: Passwort-Hashing (bcrypt) + JWT-Erzeugung/-Prüfung.
#  Bezug: GROUND_TRUTH §8/§10.4.
# ============================================================
from __future__ import annotations

import jwt
import pytest

from foreman.config import Settings
from foreman.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

_SETTINGS = Settings(
    _env_file=None,
    jwt_secret="unit-secret-0123456789abcdef0123456789",  # >=32 Byte (HS256)
    jwt_algorithm="HS256",
)


def test_hash_is_not_plaintext_and_verifies() -> None:
    hashed = hash_password("supersecret1")
    assert hashed != "supersecret1"
    assert verify_password("supersecret1", hashed) is True


def test_wrong_password_does_not_verify() -> None:
    hashed = hash_password("supersecret1")
    assert verify_password("falsch", hashed) is False


def test_verify_with_broken_hash_returns_false() -> None:
    assert verify_password("x", "kein-gueltiger-bcrypt-hash") is False


def test_long_password_is_truncated_consistently() -> None:
    pw = "a" * 100
    hashed = hash_password(pw)
    assert verify_password(pw, hashed) is True
    # bcrypt-Kürzung auf 72 Byte: die ersten 72 Zeichen ergeben denselben Treffer.
    assert verify_password("a" * 72, hashed) is True


def test_jwt_roundtrip_contains_subject() -> None:
    token = create_access_token("7", _SETTINGS)
    payload = decode_access_token(token, _SETTINGS)
    assert payload["sub"] == "7"
    assert "exp" in payload and "iat" in payload


def test_jwt_extra_claims() -> None:
    token = create_access_token("7", _SETTINGS, extra_claims={"role": "admin"})
    payload = decode_access_token(token, _SETTINGS)
    assert payload["role"] == "admin"


def test_expired_token_raises() -> None:
    token = create_access_token("7", _SETTINGS, expires_minutes=-1)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token, _SETTINGS)


def test_tampered_token_raises() -> None:
    token = create_access_token("7", _SETTINGS)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token + "tamper", _SETTINGS)


def test_wrong_secret_raises() -> None:
    token = create_access_token("7", _SETTINGS)
    other = Settings(_env_file=None, jwt_secret="anderes-secret-0123456789abcdef0123")
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token, other)
