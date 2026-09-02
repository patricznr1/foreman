# ============================================================
#  FOREMAN — tests/unit/test_archiv_guete_urteile_einlesen.py
#  Zweck: Der ausgefuellte Urteilsbogen laesst sich einlesen, WIE ER IST.
#  Anlass (02.09.2026): Der erzeugte Bogen traegt zu jedem Paar den Auszug als
#         '#'-Zeile und sagt dem Beurteiler ausdruecklich, sie bleibe stehen.
#         `lies_urteile` brach aber am ersten solchen Wort ab. Der Bogen versprach
#         also etwas, das der Code nicht hielt — und der ausgefuellte Bogen haette
#         von Hand gesaeubert werden muessen, was die Auszuege verloere. Genau sie
#         machen ein Urteil nachtraeglich pruefbar: Sie zeigen, WAS vorlag.
#  Die zweite Zusicherung wiegt schwerer als sie aussieht: Ein '#'-Auszug enthaelt
#         Fliesstext und darf NICHT als Urteil missdeutet werden — aber ein Wort
#         ausserhalb eines Kommentars muss weiterhin abbrechen. Faellt diese
#         Strenge weg, verschwindet ein vertipptes Urteil STILL, und die Zahl der
#         beurteilten Eintraege sinkt, ohne dass es jemandem auffiele — genau die
#         Zahl, die die Verzerrungskorrektur traegt.
# ============================================================
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

_PFAD = Path(__file__).resolve().parents[2] / "tools" / "archiv_guete" / "baue_goldset_v3.py"


@pytest.fixture(scope="module")
def werkzeug() -> Any:
    spec = importlib.util.spec_from_file_location("archiv_guete_baue_goldset", _PFAD)
    assert spec is not None and spec.loader is not None
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


def _bogen(tmp_path: Path, inhalt: str) -> Path:
    pfad = tmp_path / "relevanz_urteile_pruefung.txt"
    pfad.write_text(inhalt, encoding="utf-8")
    return pfad


def test_der_ausgefuellte_bogen_laesst_sich_einlesen_wie_er_ist(
    werkzeug: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DER TRAGENDE FALL — der Bogen im Originalzustand, mit Auszuegen."""
    bogen = _bogen(
        tmp_path,
        "# Urteilsbogen — unbeurteilte Paare\n"
        "#   2 = gleiche Ursache (dasselbe Stoerungsbild)\n"
        "\n"
        '## B07 — "Nullpunktverschiebung an AX"\n'
        "#   [memory] Wartung 37 (inspection) an AX-01. Umkehrspiel 0,08 bis 0,11 mm.\n"
        "B07-WA-021=2\n"
        "#   [memory] Wartung 96 an RB-02, Gelenklager. Spiel in Achse 1.\n"
        "B03-WA-080=1\n",
    )
    monkeypatch.setattr(werkzeug, "URTEILSDATEIEN", [bogen])
    assert werkzeug.lies_urteile() == {"B07": {"WA-021": 2}, "B03": {"WA-080": 1}}


def test_ein_urteil_ausserhalb_eines_kommentars_bricht_weiterhin_ab(
    werkzeug: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AUFBAU-KONTROLLE zur Strenge.

    Ohne diesen Fall waere nicht zu unterscheiden, ob '#'-Zeilen uebersprungen
    werden oder ob schlicht alles Unverstaendliche stillschweigend faellt. Der
    Unterschied ist der ganze Punkt: Ein vertipptes Urteil MUSS auffallen.
    """
    bogen = _bogen(tmp_path, "B07-WA-021=2\nB07-WA-022=3\n")
    monkeypatch.setattr(werkzeug, "URTEILSDATEIEN", [bogen])
    with pytest.raises(SystemExit, match="Unverstaendliches Urteil"):
        werkzeug.lies_urteile()


def test_mehrere_urteile_in_EINER_zeile_werden_alle_gelesen(
    werkzeug: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Fall, an dem der Umbau haette scheitern koennen.

    Beim Einziehen der Zeilen-Schleife rutschten Widerspruchspruefung und
    Zuweisung zuerst AUS der Wort-Schleife heraus. Bei einem Urteil je Zeile —
    also im ganzen erzeugten Bogen — waere das nie aufgefallen; erst ab zwei
    Urteilen in einer Zeile ueberschriebe das letzte alle vorigen. Die alte
    Fassung las wortweise ueber die ganze Datei und konnte das.
    """
    bogen = _bogen(tmp_path, "B01-WA-099=1 B01-WA-100=1 B01-WA-103=0\n")
    monkeypatch.setattr(werkzeug, "URTEILSDATEIEN", [bogen])
    assert werkzeug.lies_urteile() == {"B01": {"WA-099": 1, "WA-100": 1, "WA-103": 0}}


def test_widersprechende_urteile_brechen_ab(
    werkzeug: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Raten waere hier das Schlimmste — die Auswahl entschiede der Zufall."""
    a = tmp_path / "relevanz_urteile_a.txt"
    b = tmp_path / "relevanz_urteile_b.txt"
    a.write_text("B07-WA-021=2\n", encoding="utf-8")
    b.write_text("B07-WA-021=0\n", encoding="utf-8")
    monkeypatch.setattr(werkzeug, "URTEILSDATEIEN", [a, b])
    with pytest.raises(SystemExit, match="Widersprechende Urteile"):
        werkzeug.lies_urteile()
