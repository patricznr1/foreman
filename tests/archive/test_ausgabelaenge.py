# ============================================================
#  FOREMAN — tests/archive/test_ausgabelaenge.py
#  Zweck: Hält die Ausgabelänge der Archiv-Suche an EINER Stelle.
#  Warum eine eigene Datei: Die Zahl stand an drei Orten verschieden — Backend 5,
#         Anzeige 12, Messwerkzeug 10 (C-083, erhoben am 27.08.2026). Gemessen
#         wurde damit eine Länge, die niemand zu sehen bekam, und die Aussage
#         über Verdrängung galt für ein System, das so nicht ausgeliefert wird.
#         Zwei Zahlen, die dasselbe bedeuten sollen, laufen auseinander; genau
#         das fangen die Fälle hier ab.
# ============================================================
from __future__ import annotations

import inspect
from pathlib import Path

from foreman.archive.router import search_archive_endpoint
from foreman.archive.search import ARCHIV_AUSGABELAENGE

_ANFRAGEN = (
    Path(__file__).resolve().parents[2] / "tools" / "archiv_guete" / "goldset_v2_anfragen.yaml"
)


def test_die_laenge_ist_die_gemessene() -> None:
    """15 ist erhoben, nicht gewählt (C-087, 27.08.2026).

    Bei zehn Plätzen sinkt die Trefferquote auf zwei von zehn Anfragen, sobald
    das Gedächtnis dazukommt; ab fünfzehn auf keiner. Der Kandidatenpool umfasst
    rund zwanzig Einträge je Anfrage — mehr als fünfzehn Plätze zeigen ihn
    faktisch ganz und geben die Rangfolge auf, statt sie zu verbessern.

    Dieser Test hält die Zahl nicht fest, weil sie schön ist, sondern damit ihre
    Änderung eine Entscheidung bleibt: Wer sie anfasst, muss hier vorbei und
    findet den Grund.
    """
    assert ARCHIV_AUSGABELAENGE == 15


def test_die_route_gibt_genau_diese_laenge_vor() -> None:
    """Der Vorgabewert der Route IST die Konstante, keine zweite Zahl daneben.

    Geprüft wird die Signatur des Endpunkts, nicht eine Antwort: Der Vorgabewert
    ist genau das, was greift, wenn ein Aufrufer `k` weglässt — und die Anzeige
    lässt es seit dem 27.08.2026 weg.
    """
    vorgabe = inspect.signature(search_archive_endpoint).parameters["k"].default

    assert vorgabe.default == ARCHIV_AUSGABELAENGE


def test_die_route_laesst_keine_unbegrenzte_ausgabe_zu() -> None:
    """AUFBAU-KONTROLLE zu den Grenzen der Route.

    Ohne obere Grenze könnte ein Aufrufer den gesamten Bestand in einer Antwort
    anfordern — und die Fusion müsste jede Quelle bis dorthin abfragen. Die
    Grenzen gehören mitgeprüft, sonst verschwinden sie bei einer Umstellung des
    Vorgabewerts unbemerkt mit.

    Die Grenzen liegen bei FastAPI als `annotated_types`-Marken in `metadata`,
    nicht als Attribute — gelesen wird, was wirklich dort steht.
    """
    vorgabe = inspect.signature(search_archive_endpoint).parameters["k"].default
    grenzen = {
        type(marke).__name__: getattr(marke, type(marke).__name__.lower())
        for marke in vorgabe.metadata
    }

    assert grenzen == {"Ge": 1, "Le": 50}


def test_das_messwerkzeug_misst_dieselbe_laenge() -> None:
    """Die dritte der drei Stellen — und die, an der es zuerst schiefging.

    Das Messwerkzeug nimmt seine Ausgabelänge aus der Anfragedatei. Steht dort
    eine andere Zahl als in der Route, misst der Lauf ein System, das so nicht
    ausgeliefert wird: Bei zehn Plätzen ist mehr zu verdrängen als bei fünfzehn,
    und die Freigabe-Entscheidung hinge an einer Länge, die niemand sieht.

    Gelesen wird die Datei zeilenweise (kein PyYAML im Prüflauf), wie es
    `miss.py` auch tut.
    """
    zeilen = _ANFRAGEN.read_text(encoding="utf-8").splitlines()
    werte = [z.split(":", 1)[1].strip() for z in zeilen if z.startswith("k:")]

    assert werte == [str(ARCHIV_AUSGABELAENGE)], (
        f"{_ANFRAGEN.name} misst mit k={werte}, die Route liefert {ARCHIV_AUSGABELAENGE}"
    )
