# ============================================================
#  FOREMAN — tests/unit/test_archiv_guete_neu_fusionieren.py
#  Zweck: Prüft die Wächter des Werkzeugs, das aus Einzelquellen-Läufen ein
#         fusioniertes Ergebnis baut (tools/archiv_guete/neu_fusionieren.py).
#  Warum gerade die Wächter: Jeder von ihnen fängt einen Aufbaufehler ab, der
#         sich sonst als MESSERGEBNIS liest — ein Lauf gegen die alten Anfragen,
#         eine fehlende Quelle, eine andere Ausgabelänge. Ein Absturz ist
#         harmlos; eine plausible falsche Zahl wird geglaubt und landet im
#         Register. Dieselbe Klasse wie der leere Bewertungssatz in
#         `test_archiv_guete_auswertung.py`.
#  Warum hier und nicht im Werkzeug-Verzeichnis: Das Erheben braucht eine
#         laufende Instanz; das RECHNEN braucht nichts als die Rohdateien.
# ============================================================
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

_PFAD = Path(__file__).resolve().parents[2] / "tools" / "archiv_guete" / "neu_fusionieren.py"


def _lade() -> Any:
    spec = importlib.util.spec_from_file_location("archiv_guete_neu_fusionieren", _PFAD)
    assert spec is not None and spec.loader is not None
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture(scope="module")
def werkzeug() -> Any:
    return _lade()


def _lauf(
    quellen: list[str], *, anfragedatei: str = "goldset_v2_anfragen.yaml", k: int = 10
) -> dict:
    return {
        "lauf": "probe",
        "anfragedatei": anfragedatei,
        "basis": "http://probe",
        "quellen": quellen,
        "k": k,
        "laeufe": [],
    }


def _schreibe(pfad: Path, inhalt: dict) -> str:
    pfad.write_text(json.dumps(inhalt, ensure_ascii=False), encoding="utf-8")
    return str(pfad)


# ──────────────────────────────────────────────────────────────────────
#  Die Wächter — jeder fängt einen Fehler, der sich als Messung liest
# ──────────────────────────────────────────────────────────────────────


def test_ein_fusionierter_lauf_wird_abgewiesen(werkzeug: Any, tmp_path: Path) -> None:
    """Aus einem fusionierten Ergebnis ist der quelleninterne Rang nicht
    zurückzugewinnen.

    Die globale Reihenfolge lässt ihn nur solange erraten, wie die Fusion ein
    reines Interleaving ist — genau das ist seit dem 27.08.2026 nicht mehr der
    Fall. Ein solcher Lauf, still verarbeitet, ergäbe Ränge, die niemand
    gemessen hat, und eine Datei, die aussieht wie eine Messung.
    """
    pfad = _schreibe(tmp_path / "fusioniert.json", _lauf(["note", "maintenance", "alarm"]))

    with pytest.raises(SystemExit):
        werkzeug._lies(pfad)


def test_ein_einzelquellen_lauf_geht_durch(werkzeug: Any, tmp_path: Path) -> None:
    """AUFBAU-KONTROLLE zum Wächter: Er darf keinen gültigen Lauf abweisen."""
    pfad = _schreibe(tmp_path / "einzeln.json", _lauf(["note"]))

    assert werkzeug._lies(pfad)["quellen"] == ["note"]


def test_lauf_ohne_quellenangabe_wird_abgewiesen(werkzeug: Any, tmp_path: Path) -> None:
    """Ein Lauf ohne `quellen` ist nicht zuzuordnen — geraten wird nicht."""
    ohne = _lauf(["note"])
    del ohne["quellen"]
    pfad = _schreibe(tmp_path / "ohne.json", ohne)

    with pytest.raises(SystemExit):
        werkzeug._lies(pfad)


# ──────────────────────────────────────────────────────────────────────
#  Die Reihenfolge — sie entscheidet mit, wer einen Vorgang vertritt
# ──────────────────────────────────────────────────────────────────────


def _mit_treffer(quelle: str, treffer: list[dict]) -> dict:
    lauf = _lauf([quelle])
    lauf["laeufe"] = [
        {
            "anfrage_id": "B01",
            "anfrage": "Undichtigkeit an Achse",
            "machine_id": None,
            "dauer_s": 0.4,
            "fehler": None,
            "treffer": [{"rang": i + 1, **t} for i, t in enumerate(treffer)],
        }
    ]
    return lauf


def _notiz(kennung: int) -> dict:
    return {
        "source_type": "note",
        "id": kennung,
        "machine_id": 1,
        "timestamp": "2026-06-06T00:00:00+00:00",
        "excerpt": "Auszug",
        "detail": {},
    }


def _erinnerung_auf(art: str, kennung: int) -> dict:
    return {
        "source_type": "memory",
        "id": 0,
        "machine_id": 1,
        "timestamp": "2026-06-06T00:00:00+00:00",
        "excerpt": "Auszug",
        "detail": {"herkunft": "gedaechtnis", "quelle": {"art": art, "id": kennung}},
    }


def test_die_quellen_reihenfolge_folgt_dem_produkt_nicht_der_kommandozeile(
    werkzeug: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Bei gleichem Punktestand entscheidet die Reihenfolge, WER vertritt.

    Wird das Gedächtnis zuerst eingelesen, würde es Vertreter eines Vorgangs, den
    auch eine Notiz gefunden hat — und der ausgelieferte Treffer trüge die
    gekürzte Fassung aus dem Abruf statt den Originaltext aus der Datenbank. Die
    Reihenfolge der Kommandozeile darf das nicht bestimmen; sonst hinge das
    Ergebnis daran, wie jemand den Aufruf getippt hat.
    """
    gedaechtnis = _schreibe(
        tmp_path / "mem.json", _mit_treffer("memory", [_erinnerung_auf("note", 7)])
    )
    notizen = _schreibe(tmp_path / "note.json", _mit_treffer("note", [_notiz(7)]))

    # Gedaechtnis ABSICHTLICH zuerst auf der Kommandozeile.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["neu_fusionieren.py", "probe", gedaechtnis, notizen])
    werkzeug.main()
    capsys.readouterr()

    ergebnis = json.loads((tmp_path / "messung_probe.json").read_text(encoding="utf-8"))
    (treffer,) = ergebnis["laeufe"][0]["treffer"]
    assert treffer["source_type"] == "note", "der eigene Treffer vertritt den Vorgang"
    assert treffer["gefunden_von"] == ["note", "memory"]
    assert ergebnis["quellen"] == ["note", "memory"]


def test_ein_fehler_in_einer_quelle_faerbt_die_ganze_anfrage(
    werkzeug: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Sonst entsteht eine Liste ohne diese Quelle, die sich von einem echten
    Ergebnis nicht unterscheiden lässt.

    Ein Netzfehler beim Erheben ist kein „keine Treffer". Ginge er still durch,
    zählte die Auswertung ihn als gefundene Null — und die Trefferquote fiele
    aus einem Grund, der mit der Suche nichts zu tun hat.
    """
    kaputt = _mit_treffer("memory", [])
    kaputt["laeufe"][0]["fehler"] = "URLError: timed out"
    a = _schreibe(tmp_path / "mem.json", kaputt)
    b = _schreibe(tmp_path / "note.json", _mit_treffer("note", [_notiz(7)]))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["neu_fusionieren.py", "probe", a, b])
    werkzeug.main()
    capsys.readouterr()

    ergebnis = json.loads((tmp_path / "messung_probe.json").read_text(encoding="utf-8"))
    fehler = ergebnis["laeufe"][0]["fehler"]
    assert fehler is not None
    assert "memory" in fehler and "timed out" in fehler


def test_verschiedene_anfragedateien_werden_abgewiesen(
    werkzeug: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DER Aufbaufehler, der schon einmal passiert ist (27.08.2026).

    Ein Lauf gegen den neuen Bestand rechnete stillschweigend gegen die alten
    Anfragen; alle Kennzahlen wurden null, und das las sich wie ein
    vernichtendes Urteil über die Suche statt wie ein Verdrahtungsfehler.
    """
    a = _schreibe(tmp_path / "a.json", _lauf(["note"], anfragedatei="goldset_anfragen.yaml"))
    b = _schreibe(tmp_path / "b.json", _lauf(["memory"], anfragedatei="goldset_v2_anfragen.yaml"))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["neu_fusionieren.py", "probe", a, b])
    with pytest.raises(SystemExit):
        werkzeug.main()


def test_verschiedene_ausgabelaengen_werden_abgewiesen(
    werkzeug: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """AUFBAU-KONTROLLE zum vorigen Fall in der zweiten Dimension.

    Zwei Läufe mit verschiedenem `k` beschreiben verschiedene Systeme. Ohne
    diesen Wächter liesse sich ein Zehner- mit einem Zwölfer-Lauf mischen —
    und genau diese Zahl ist im Projekt an drei Stellen verschieden belegt
    (C-083).
    """
    a = _schreibe(tmp_path / "a.json", _lauf(["note"], k=10))
    b = _schreibe(tmp_path / "b.json", _lauf(["memory"], k=12))

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["neu_fusionieren.py", "probe", a, b])
    with pytest.raises(SystemExit):
        werkzeug.main()
