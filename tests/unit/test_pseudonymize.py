# ============================================================
#  FOREMAN — tests/unit/test_pseudonymize.py
#  Zweck: HMAC-Pseudonymisierung (Determinismus, Versionierung, Re-ID, Mandanten-Salt).
#  Bezug: GROUND_TRUTH §8, Research §5.3 (a).
# ============================================================
from __future__ import annotations

import pytest

from foreman.config import Settings
from foreman.core.pseudonymize import (
    PseudonymizationError,
    Pseudonymizer,
    build_pseudonymizer,
)

_KEYS = {"v1": bytes.fromhex("11" * 32), "v2": bytes.fromhex("22" * 32)}


def test_token_is_deterministic() -> None:
    p = Pseudonymizer(active_version="v1", keys=_KEYS)
    assert p.tokenize_worker("42") == p.tokenize_worker("42")


def test_token_has_version_prefix_and_hex_digest() -> None:
    p = Pseudonymizer(active_version="v2", keys=_KEYS)
    token = p.tokenize_worker("42")
    version, digest = token.split(":", 1)
    assert version == "v2"
    assert len(digest) == 64
    int(digest, 16)  # ist gültiges Hex


def test_different_users_get_different_tokens() -> None:
    p = Pseudonymizer(active_version="v1", keys=_KEYS)
    assert p.tokenize_worker("1") != p.tokenize_worker("2")


def test_tenant_acts_as_salt() -> None:
    a = Pseudonymizer(active_version="v1", keys=_KEYS, tenant="werk-a")
    b = Pseudonymizer(active_version="v1", keys=_KEYS, tenant="werk-b")
    assert a.tokenize_worker("42") != b.tokenize_worker("42")
    # Per-Call-Override deckt sich mit dem anderen Mandanten.
    assert a.tokenize_worker("42", tenant="werk-b") == b.tokenize_worker("42")


def test_verify_token_true_and_false() -> None:
    p = Pseudonymizer(active_version="v1", keys=_KEYS)
    token = p.tokenize_worker("42")
    assert p.verify_token("42", token) is True
    assert p.verify_token("43", token) is False


def test_verify_token_malformed_or_unknown_version() -> None:
    p = Pseudonymizer(active_version="v1", keys=_KEYS)
    assert p.verify_token("42", "kein-token") is False
    assert p.verify_token("42", "v9:deadbeef") is False


def test_verify_works_across_key_rotation() -> None:
    # Token mit v1 erzeugt; aktive Version v2 — bleibt verifizierbar (Version aus Token).
    old = Pseudonymizer(active_version="v1", keys=_KEYS)
    token_v1 = old.tokenize_worker("42")
    rotated = Pseudonymizer(active_version="v2", keys=_KEYS)
    assert rotated.tokenize_worker("42").startswith("v2:")
    assert rotated.verify_token("42", token_v1) is True


def test_missing_active_key_raises() -> None:
    with pytest.raises(PseudonymizationError):
        Pseudonymizer(active_version="v9", keys=_KEYS)


def test_build_from_settings() -> None:
    # FOREMAN_PSEUDO_KEY_v1 wird in conftest gesetzt.
    settings = Settings(
        _env_file=None, pseudo_key_version="v1", pseudo_key_versions="v1"
    )
    p = build_pseudonymizer(settings)
    token = p.tokenize_worker("7")
    assert token.startswith("v1:")
    assert p.verify_token("7", token)
