# ============================================================
#  FOREMAN — tests/unit/test_config.py
#  Zweck: Produktions-Guard für das JWT-Secret (§8/§10.4).
# ============================================================
from __future__ import annotations

import pytest
from pydantic import ValidationError

from foreman.config import INSECURE_JWT_SECRET, Settings
from foreman.core.security import JWT_ALGORITHM


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


# ------------------------------------------------------------
#  Die Startkonfiguration raet nicht
# ------------------------------------------------------------


def test_ohne_umgebung_verweigert_die_konfiguration_den_start(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ohne `ENVIRONMENT` kommt die Anwendung nicht hoch — bewusst.

    Von dieser Angabe haengt ab, ob die Schema-Routen offen sind und ob ein
    schwaches Geheimnis abgelehnt wird. Ein Vorgabewert muesste sie raten, und ein
    geratenes „development" liefe im Ernstfall lautlos mit offenen Routen und ohne
    Guard. Der Test haelt fest, dass hier abgebrochen wird und nicht geraten.

    `delenv` ist noetig, weil tests/conftest.py die Umgebung fuer die Suite auf
    „test" setzt — ohne das Entfernen pruefte dieser Test seine eigene Vorbedingung
    weg und bliebe gruen, ohne etwas zu belegen.
    """
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    with pytest.raises(ValidationError) as fehler:
        Settings(_env_file=None)

    text = str(fehler.value)
    assert "ENVIRONMENT" in text, (
        "❌ Die Meldung nennt die Variable nicht — sie liest jemand, dessen Anwendung "
        f"gerade nicht startet. Bekommen: {text[:200]}"
    )


def test_mit_benannter_umgebung_startet_die_konfiguration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kontroll-Zwilling: Genannt reicht, und die Einstufung stimmt.

    Ohne ihn bliebe der Test darueber auch dann gruen, wenn `Settings` aus einem
    ganz anderen Grund immer wuerfe.
    """
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    entwicklung = Settings(_env_file=None, environment="development")
    betrieb = Settings(_env_file=None, environment="production", jwt_secret="x" * 40)

    assert entwicklung.is_production is False
    assert betrieb.is_production is True


def test_leere_umgebung_zaehlt_nicht_als_benannt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Eine gesetzte, aber leere Variable ist keine Angabe.

    `ENVIRONMENT=` in einer .env ist der wahrscheinlichere Fehler als eine ganz
    fehlende Zeile — und ohne diese Pruefung liefe er auf `"".lower() not in
    _DEV_ENVIRONMENTS` hinaus, also auf stillen Produktionsbetrieb mit einem Wert,
    den niemand gemeint hat.
    """
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, environment="   ")


def test_der_signaturalgorithmus_ist_keine_betriebseinstellung() -> None:
    """`jwt_algorithm` darf nicht ueber die Umgebung setzbar sein.

    Der Algorithmus ist eine Sicherheitsentscheidung. Waere er ein Settings-Feld,
    koennte eine Fehlkonfiguration ihn still veraendern — an einer Stelle, an der
    niemand nachsieht, solange Tokens funktionieren. Er liegt deshalb als Konstante
    in core/security.py, und dieser Test haelt fest, dass er dort BLEIBT: Ein
    zurueckgebautes Feld faellt hier auf, nicht erst im Betrieb.
    """
    assert "jwt_algorithm" not in Settings.model_fields, (
        "❌ Der Signaturalgorithmus ist wieder eine Betriebseinstellung geworden. "
        "Begruendung gegen diesen Zustand steht in core/security.py bei JWT_ALGORITHM."
    )
    assert JWT_ALGORITHM == "HS256"
