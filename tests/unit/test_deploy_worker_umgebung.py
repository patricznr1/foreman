# ============================================================
#  FOREMAN — tests/unit/test_deploy_worker_umgebung.py
#  Zweck: Der live-worker startet auf dem Server nur mit dem, was Compose ihm
#         gibt: deploy/konfig/worker.conf.env plus die Namen, die
#         deploy/server/geheimnisse.py von Railway übernimmt. Settings muss
#         daraus entstehen — ohne ENVIRONMENT verweigert config.py den Start.
#  Architektur-Einordnung: Betrieb (Server-Konfiguration gegen src/foreman).
# ============================================================

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest
from pydantic import ValidationError

from foreman.config import Settings

WURZEL = Path(__file__).resolve().parents[2]
SKRIPT = WURZEL / "deploy" / "server" / "geheimnisse.py"
KONFIG = WURZEL / "deploy" / "konfig"


def _laden() -> ModuleType:
    spec = importlib.util.spec_from_file_location("deploy_geheimnisse_worker", SKRIPT)
    assert spec is not None and spec.loader is not None
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


g = _laden()


def _konfig_werte(datei: str) -> dict[str, str]:
    werte: dict[str, str] = {}
    for zeile in (KONFIG / datei).read_text(encoding="utf-8").splitlines():
        if zeile.strip() and not zeile.lstrip().startswith("#"):
            name, _, wert = zeile.partition("=")
            werte[name] = wert
    return werte


def _umgebung_wie_compose(monkeypatch: pytest.MonkeyPatch, werte: dict[str, str]) -> None:
    # Nur was Compose dem Container gibt — eine ENVIRONMENT aus der Testumgebung
    # verdeckte sonst genau den Fehler, um den es geht
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    for name in g.DIENSTE["worker"].uebernehmen:
        monkeypatch.delenv(name, raising=False)
    for name, wert in werte.items():
        monkeypatch.setenv(name, wert)


def test_worker_startet_mit_konfiguration_und_uebernommenen_namen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    werte = _konfig_werte(g.DIENSTE["worker"].konfig)
    # Merkwerte für die übernommenen Namen, wie sie in worker.env stünden
    werte.update({name: "1" for name in g.DIENSTE["worker"].uebernehmen if name not in werte})
    _umgebung_wie_compose(monkeypatch, werte)

    einstellungen = Settings(_env_file=None)

    assert einstellungen.environment == "production"
    assert einstellungen.is_production
    assert einstellungen.substrate_base_url


def test_worker_ohne_environment_in_der_konfiguration_startet_nicht(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Kontrollpunkt: dieselbe Umgebung ohne die Zeile aus worker.conf.env
    werte = _konfig_werte(g.DIENSTE["worker"].konfig)
    werte.pop("ENVIRONMENT")
    _umgebung_wie_compose(monkeypatch, werte)

    with pytest.raises(ValidationError, match="ENVIRONMENT ist nicht gesetzt"):
        Settings(_env_file=None)


def test_environment_des_workers_ist_eingeordnet() -> None:
    # Brächte Railway den Namen doch mit, bricht `uebernehmen` nicht ab
    assert "ENVIRONMENT" in g.DIENSTE["worker"].nicht_uebernommen
    assert "ENVIRONMENT" not in g.DIENSTE["worker"].uebernehmen
