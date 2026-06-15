# ============================================================
#  FOREMAN — tests/unit/test_config.py
#  Zweck: Produktions-Guard für das JWT-Secret (§8/§10.4).
# ============================================================
from __future__ import annotations

import pytest

from foreman.config import INSECURE_JWT_SECRET, Settings


def test_dev_allows_default_secret() -> None:
    settings = Settings(_env_file=None, environment="development", jwt_secret=INSECURE_JWT_SECRET)
    assert settings.is_production is False
    settings.require_secure_secrets()  # darf nicht werfen


def test_production_with_default_secret_raises() -> None:
    settings = Settings(_env_file=None, environment="production", jwt_secret=INSECURE_JWT_SECRET)
    assert settings.is_production is True
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        settings.require_secure_secrets()


def test_production_with_short_secret_raises() -> None:
    settings = Settings(_env_file=None, environment="production", jwt_secret="zu-kurz")
    with pytest.raises(RuntimeError):
        settings.require_secure_secrets()


def test_production_with_strong_secret_ok() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        jwt_secret="x" * 40,  # >= 32 Byte
    )
    settings.require_secure_secrets()  # darf nicht werfen
