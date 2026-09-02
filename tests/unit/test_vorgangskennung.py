# ============================================================
#  FOREMAN — tests/unit/test_vorgangskennung.py
#  Zweck: Die Vorgangskennung, die jeder Gedaechtnis-Abruf mitschickt.
#  Warum sie eigene Faelle verdient: Sie verlaesst das Haus und landet im
#         Protokoll eines fremden Dienstes. Zwei Eigenschaften tragen alles
#         Weitere — sie darf NIE Text tragen koennen, und sie muss je Aufruf
#         verschieden sein. Beide fallen nicht auf, wenn sie brechen: Eine
#         Kennung mit Freitext sieht aus wie eine Kennung, und zwei gleiche
#         Kennungen sehen aus wie eine Zuordnung, die es nicht gibt.
# ============================================================
from __future__ import annotations

import re

from foreman.substrate.vorgang import MAX_LAENGE, vorgangskennung

# Die Form, auf die es ankommt: Vorgang, Bezug, Unterscheider — sonst NICHTS.
# Kein Leerzeichen, kein Nicht-ASCII, keine Stelle, an der Text stehen koennte.
FORM = re.compile(r"^(kette|archiv)-(alle|\d+)-[0-9a-f]{12}$")


def test_die_kennung_hat_eine_maschinenform_ohne_platz_fuer_text() -> None:
    """DIE TRAGENDE ZUSICHERUNG.

    Die Typen verhindern schon, dass ein Aufrufer Text hineinreicht (`Vorgang` ist
    eine geschlossene Menge, `bezug` eine Zahl). Dieser Fall haelt die andere
    Haelfte fest: dass auch das ERGEBNIS nichts anderes sein kann. Wuerde jemand
    spaeter einen freien Namensteil ergaenzen, faellt es hier auf — und nicht erst
    dann, wenn ein Werker-Freitext im Protokoll eines fremden Dienstes steht.
    """
    for kennung in (
        vorgangskennung("kette", bezug=93),
        vorgangskennung("archiv", bezug=7),
        vorgangskennung("archiv"),
    ):
        assert FORM.match(kennung), f"❌ Kennung ausserhalb der erlaubten Form: {kennung!r}"


def test_zwei_aufrufe_tragen_verschiedene_kennungen() -> None:
    """Ohne das ist sie zum Zuordnen wertlos.

    Zwei Abrufe zum selben Anker faenden im fremden Protokoll sonst dieselbe
    Zeile, und die Frage, welcher der beiden langsam war, waere nicht mehr zu
    beantworten. Geprueft wird ueber ZWANZIG Aufrufe statt zwei: Ein Fehler, der
    nur gelegentlich dieselbe Kennung liefert, waere bei zweien leicht zu
    uebersehen.
    """
    kennungen = {vorgangskennung("kette", bezug=93) for _ in range(20)}
    assert len(kennungen) == 20, "❌ Zwei Aufrufe lieferten dieselbe Kennung."


def test_der_vorgang_und_der_bezug_bleiben_lesbar() -> None:
    """Die Kennung soll auf der Gegenseite ohne Rueckfrage einzuordnen sein.

    Ein reiner Zufallswert waere eindeutig und nutzlos: Man saehe, DASS zwei
    Zeilen verschieden sind, aber nicht, worum es ging.
    """
    assert vorgangskennung("kette", bezug=93).startswith("kette-93-")
    assert vorgangskennung("archiv", bezug=7).startswith("archiv-7-")


def test_kein_bezug_ist_von_der_null_zu_unterscheiden() -> None:
    """AUFBAU-KONTROLLE: 0 ist eine gueltige Kennung.

    Ein leerer Teil statt `alle` liesse `archiv--…` entstehen, und das waere von
    einem Bezug 0 nicht mehr zu trennen — dieselbe Klasse wie "nicht erhoben"
    gegen "leer", die an der Spiegelung schon einmal Arbeit gekostet hat.
    """
    assert vorgangskennung("archiv").startswith("archiv-alle-")
    assert vorgangskennung("archiv", bezug=0).startswith("archiv-0-")


def test_die_kennung_bleibt_innerhalb_der_vertragslaenge() -> None:
    """Die Gegenstelle nimmt hoechstens 128 Zeichen.

    Der Klient kuerzt zwar, aber eine Kennung, die erst DORT gekuerzt wird, ist
    nicht mehr die, die wir gebaut haben — und die gekuerzte Fassung landet im
    fremden Protokoll, waehrend wir die ungekuerzte fuer die Zuordnung erwarten.
    Die Nummer ist so gewaehlt, dass die Kuerzung WIRKLICH greift: 121 Stellen
    plus Vorgang und Unterscheider ergeben 140 Zeichen. Mit einer kleineren
    Zahl waere der Fall gruen geblieben, auch wenn jemand die Kuerzung
    entfernt — ein Test, der seine eigene Zusicherung nicht erreichen kann.
    """
    riesig = 10**120
    assert len(f"kette-{riesig}-000000000000") > MAX_LAENGE, (
        "❌ Aufbau-Kontrolle: Die Testzahl loest die Kuerzung gar nicht aus."
    )
    assert len(vorgangskennung("kette", bezug=riesig)) <= MAX_LAENGE
