# ============================================================
#  FOREMAN — tests/unit/test_deploy_geheimnisse.py
#  Zweck: Prüft deploy/server/geheimnisse.py — Disjunktheit zu deploy/konfig,
#         Einordnung jedes Railway-Namens, geteilter Pseudo-Schlüssel, und dass
#         keine Ausgabe einen Wert trägt.
#  Architektur-Einordnung: Betrieb (Server-Skript außerhalb von src/foreman).
# ============================================================

from __future__ import annotations

import importlib.util
import io
import json
import os
import stat
import sys
from pathlib import Path
from types import ModuleType

import pytest

WURZEL = Path(__file__).resolve().parents[2]
SKRIPT = WURZEL / "deploy" / "server" / "geheimnisse.py"
KONFIG = WURZEL / "deploy" / "konfig"


def _laden() -> ModuleType:
    spec = importlib.util.spec_from_file_location("deploy_geheimnisse", SKRIPT)
    assert spec is not None and spec.loader is not None
    modul = importlib.util.module_from_spec(spec)
    # dataclass braucht das Modul in sys.modules, um die Annotationen aufzulösen
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


g = _laden()


def _railway(dienst: str, **extra: str | None) -> dict[str, str | None]:
    """Eine Variablenliste, wie Railway sie für den Dienst liefert, mit Merkwerten."""
    werte: dict[str, str | None] = {name: f"wert-{name}" for name in g.DIENSTE[dienst].uebernehmen}
    werte["FOREMAN_PSEUDO_KEY_v1"] = "wert-schluessel-v1"
    werte["DATABASE_URL"] = "wert-railway-datenbank"
    werte["RAILWAY_SERVICE_NAME"] = dienst
    werte.update(extra)
    return werte


def _uebernehmen(dienst: str, railway: dict[str, str | None], ziel: Path) -> int:
    roh = json.dumps(railway).encode("utf-8")
    return int(g.main(["--ziel", str(ziel), "uebernehmen", dienst], stdin=io.BytesIO(roh)))


@pytest.fixture
def ziel(tmp_path: Path) -> Path:
    verzeichnis = tmp_path / "env"
    verzeichnis.mkdir(mode=0o700)
    return verzeichnis


@pytest.mark.parametrize("dienst", sorted(g.DIENSTE))
def test_liste_ist_disjunkt_zur_konfiguration(dienst: str) -> None:
    # Compose liest die Geheimnisdatei nach der Konfiguration; ein gemeinsamer
    # Name ließe Railway eine Server-Einstellung überschreiben
    namen = g.konfig_namen(KONFIG / g.DIENSTE[dienst].konfig)
    assert not namen & g.DIENSTE[dienst].uebernehmen
    assert not {n for n in namen if g.PSEUDO_MUSTER.match(n)}


def test_frontend_konfiguration_traegt_keinen_geheimnisnamen() -> None:
    namen = g.konfig_namen(KONFIG / "frontend.conf.env")
    alle = set().union(*(d.uebernehmen for d in g.DIENSTE.values()))
    assert namen == {"FOREMAN_API_URL"}
    assert not namen & alle


def test_backend_schreibt_beide_dateien_woertlich(
    ziel: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    railway = _railway("backend")
    assert _uebernehmen("backend", railway, ziel) == 0

    backend = g.env_lesen(ziel / "backend.env")
    assert backend == {n: railway[n] for n in g.DIENSTE["backend"].uebernehmen}
    assert g.env_lesen(ziel / "pseudo.env") == {"FOREMAN_PSEUDO_KEY_v1": "wert-schluessel-v1"}
    # Der Railway-Zugang zur alten Datenbank landet nirgends
    assert "DATABASE_URL" not in backend
    if os.name == "posix":
        for datei in ("backend.env", "pseudo.env"):
            assert stat.S_IMODE((ziel / datei).stat().st_mode) == 0o600
    ausgabe = capsys.readouterr()
    assert "wert-" not in ausgabe.out + ausgabe.err


def test_worker_vergleicht_den_geteilten_schluessel(ziel: Path) -> None:
    assert _uebernehmen("backend", _railway("backend"), ziel) == 0
    assert _uebernehmen("worker", _railway("worker"), ziel) == 0
    assert set(g.env_lesen(ziel / "worker.env")) == g.DIENSTE["worker"].uebernehmen


def test_abweichender_schluessel_beim_worker_bricht_ab(
    ziel: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _uebernehmen("backend", _railway("backend"), ziel) == 0
    vorher = (ziel / "pseudo.env").read_bytes()

    anders = _railway("worker", FOREMAN_PSEUDO_KEY_v1="wert-anderer-schluessel")
    assert _uebernehmen("worker", anders, ziel) == 1

    assert (ziel / "pseudo.env").read_bytes() == vorher
    assert not (ziel / "worker.env").exists()
    ausgabe = capsys.readouterr()
    assert "FOREMAN_PSEUDO_KEY_v1" in ausgabe.err
    assert "wert-" not in ausgabe.out + ausgabe.err


def test_zweiter_lauf_vergleicht_und_ueberschreibt_nie(ziel: Path) -> None:
    assert _uebernehmen("backend", _railway("backend"), ziel) == 0
    vorher = (ziel / "backend.env").read_bytes()

    assert _uebernehmen("backend", _railway("backend"), ziel) == 0
    assert _uebernehmen("backend", _railway("backend", JWT_SECRET="wert-gedreht"), ziel) == 1
    assert (ziel / "backend.env").read_bytes() == vorher


def test_unbekannter_name_bricht_ab_ohne_zu_schreiben(
    ziel: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert _uebernehmen("backend", _railway("backend", NEUE_VARIABLE="wert-neu"), ziel) == 1
    assert list(ziel.iterdir()) == []
    assert "NEUE_VARIABLE: nicht eingeordnet" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("wert", "befund"),
    [
        (None, "versiegelt"),
        ("", "ist leer"),
        ("wert-mit-'-zeichen", "Anführungszeichen"),
        ("wert-mit\numbruch", "Zeilenumbruch"),
    ],
)
def test_unbrauchbarer_wert_wird_benannt_nicht_gezeigt(
    ziel: Path, capsys: pytest.CaptureFixture[str], wert: str | None, befund: str
) -> None:
    assert _uebernehmen("backend", _railway("backend", JWT_SECRET=wert), ziel) == 1
    assert list(ziel.iterdir()) == []
    ausgabe = capsys.readouterr().err
    assert "JWT_SECRET" in ausgabe and befund in ausgabe
    assert "wert-mit" not in ausgabe


def test_fehlender_schluessel_bricht_ab(ziel: Path, capsys: pytest.CaptureFixture[str]) -> None:
    railway = _railway("worker")
    del railway["FOREMAN_PSEUDO_KEY_v1"]
    assert _uebernehmen("worker", railway, ziel) == 1
    assert "kein Schlüssel auf Railway" in capsys.readouterr().err


def test_anlegen_nur_einmal(ziel: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert g.main(["--ziel", str(ziel), "anlegen"]) == 0
    passwort = g.env_lesen(ziel / "timescaledb.env")["POSTGRES_PASSWORD"]
    adresse = g.env_lesen(ziel / "zugang.env")["DATABASE_URL"]
    assert adresse == f"postgresql+asyncpg://foreman:{passwort}@timescaledb:5432/foreman"
    assert g.wert_problem(passwort) is None

    assert g.main(["--ziel", str(ziel), "anlegen"]) == 1
    assert g.env_lesen(ziel / "timescaledb.env")["POSTGRES_PASSWORD"] == passwort
    assert passwort not in capsys.readouterr().out
