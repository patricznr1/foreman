# ============================================================
#  FOREMAN — tests/unit/test_archiv_guete_pool_verzerrung.py
#  Zweck: Prüft das Werkzeug, das die Pool-Verzerrung beziffert
#         (tools/archiv_guete/pool_verzerrung.py).
#  Warum es einen Test verdient: Seine Zahl entscheidet mit darüber, ob eine
#         verfehlte Freigabe-Bedingung als Mangel der vierten Quelle gilt oder
#         als Lücke im Maßstab (C-109, C-110). Jeder der drei Fehler, gegen die
#         hier geprüft wird, liefert eine PLAUSIBLE falsche Zahl — keiner wirft,
#         keiner fällt bei der Durchsicht auf. Genau diese Klasse trägt der Test.
#  Vorbild: tests/unit/test_archiv_guete_auswertung.py — dasselbe Ladeverfahren,
#         damit ein Werkzeug ausserhalb des Pakets prüfbar bleibt.
# ============================================================
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_PFAD = Path(__file__).resolve().parents[2] / "tools" / "archiv_guete" / "pool_verzerrung.py"


@pytest.fixture(scope="module")
def werkzeug() -> Any:
    spec = importlib.util.spec_from_file_location("archiv_guete_pool_verzerrung", _PFAD)
    assert spec is not None and spec.loader is not None
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


def _erinnerung(art: str, kennung: int, *, auch_eigen: bool = False) -> dict:
    """Ein Gedächtnis-Treffer mit Rückweg, wie ihn `miss.py` roh ablegt.

    `auch_eigen` bildet den Fall ab, dass eine eigene Quelle denselben Vorgang
    gefunden hat — dann ist der Platz gerade NICHT exklusiv.
    """
    return {
        "schluessel": "memory:0",
        "gefunden_von": [art, "memory"] if auch_eigen else ["memory"],
        "detail": {"quelle": {"art": art, "id": kennung}},
    }


def _eigener(art: str, kennung: int) -> dict:
    return {"schluessel": f"{art}:{kennung}", "gefunden_von": [art], "detail": {}}


@pytest.fixture
def lauf(tmp_path: Path) -> Path:
    """Vier Plätze, die zusammen jede Unterscheidung des Werkzeugs auslösen."""
    daten = {
        "lauf": "pruefung",
        "laeufe": [
            {
                "anfrage_id": "B01",
                "treffer": [
                    _erinnerung("maintenance", 37),  # exklusiv, NIE beurteilt
                    _erinnerung("note", 195),  # exklusiv, beurteilt mit 0
                    _erinnerung("note", 71, auch_eigen=True),  # NICHT exklusiv
                    _eigener("note", 108),  # eigene Quelle, zutreffend
                ],
            }
        ],
    }
    pfad = tmp_path / "lauf.json"
    pfad.write_text(json.dumps(daten), encoding="utf-8")
    return pfad


# Nur die ZUTREFFENDEN — so ist goldset_v3.json gebaut, es führt keine Nullen.
GOLDSET = {"B01": {"note:71": 2, "note:108": 1}}
# ALLE gesehenen, auch die verworfenen. Der Unterschied ist der ganze Punkt.
BEURTEILT = {"B01": {"note:195": 0, "note:71": 2, "note:108": 1}}


def test_die_zahlen_stimmen_im_ganzen(werkzeug: Any, lauf: Path) -> None:
    """AUFBAU-KONTROLLE für die drei Einzelfälle darunter.

    Ohne diesen Fall könnte eine der folgenden Zusicherungen zufällig halten,
    weil sich zwei Fehler gegenseitig aufheben.
    """
    e = werkzeug.werte_aus_lauf(lauf, GOLDSET, BEURTEILT)
    assert e["zahlen"]["exklusiv"] == [2, 1, 0], "gesamt/beurteilt/zutreffend der exklusiven"
    assert e["zahlen"]["eigen"] == [2, 2, 2], "gesamt/beurteilt/zutreffend der übrigen"


def test_ein_platz_den_auch_eine_eigene_quelle_fand_ist_nicht_exklusiv(
    werkzeug: Any, lauf: Path
) -> None:
    """DIE TRAGENDE UNTERSCHEIDUNG.

    Nur Plätze, die ALLEIN das Gedächtnis liefert, können die Verzerrung zeigen —
    ein Vorgang, den auch eine eigene Quelle findet, stand längst im Pool und ist
    deshalb beurteilt. Wer die Prüfung zu `"memory" in gefunden_von` lockert,
    zählt note:71 mit: Die exklusive Beurteilungsquote stiege von 1/2 auf 2/3 und
    sähe damit BESSER aus, als sie ist — die Verzerrung würde kleingerechnet.
    """
    e = werkzeug.werte_aus_lauf(lauf, GOLDSET, BEURTEILT)
    assert e["zahlen"]["exklusiv"][0] == 2, (
        "❌ Ein Platz mit zwei findenden Quellen wird als exklusiv gezählt."
    )


def test_ein_mit_null_beurteilter_platz_gilt_als_beurteilt(werkzeug: Any, lauf: Path) -> None:
    """DER FALL, AN DEM ALLES HÄNGT.

    `note:195` steht mit der Stufe 0 in den Urteilen und deshalb NICHT im
    Goldset. Wer den Beurteilungsstand am Goldset statt an den Urteilen prüft,
    hält diesen Platz für unbeurteilt — und misst eine Verzerrung, die es nicht
    gibt. Der Unterschied zwischen „gesehen und verworfen" und „nie angesehen"
    ist der einzige Grund, warum es zwei Dateien gibt.
    """
    e = werkzeug.werte_aus_lauf(lauf, GOLDSET, BEURTEILT)
    assert e["zahlen"]["exklusiv"][1] == 1, (
        "❌ Ein mit 0 beurteilter Treffer wird als unbeurteilt gezählt."
    )
    assert ("B01", "note:195") not in e["offen"]


def test_der_rueckweg_bestimmt_den_schluessel_nicht_die_rohkennung(
    werkzeug: Any, lauf: Path
) -> None:
    """Erinnerungen tragen alle `memory:0`.

    Würde danach nachgeschlagen, fiele KEINE Erinnerung je auf ein Urteil — die
    exklusive Quote wäre immer 0 %, und das sähe nach einem gewaltigen Befund
    aus statt nach einem Programmfehler. Der Schlüssel kommt deshalb aus
    `werte_aus._schluessel`, und der offene Posten muss ihn führen.
    """
    e = werkzeug.werte_aus_lauf(lauf, GOLDSET, BEURTEILT)
    assert e["offen"] == [("B01", "maintenance:37")], (
        f"❌ Offener Posten unter falschem Schlüssel: {e['offen']}"
    )


def test_ein_lauf_mit_fehler_wird_uebersprungen(werkzeug: Any, tmp_path: Path) -> None:
    """AUFBAU-KONTROLLE: Eine gescheiterte Anfrage hat keine Trefferliste.

    Sie mitzuzählen verschöbe die Quote um eine Anfrage, ohne dass etwas fehlte —
    dieselbe Regel, nach der `werte_aus.werte_lauf` verfährt.
    """
    pfad = tmp_path / "mit_fehler.json"
    pfad.write_text(
        json.dumps(
            {"laeufe": [{"anfrage_id": "B02", "fehler": "Zeitüberschreitung", "treffer": []}]}
        ),
        encoding="utf-8",
    )
    e = werkzeug.werte_aus_lauf(pfad, GOLDSET, BEURTEILT)
    assert e["zahlen"]["exklusiv"] == [0, 0, 0]
    assert e["zahlen"]["eigen"] == [0, 0, 0]
