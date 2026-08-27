# ============================================================
#  FOREMAN — tests/unit/test_archiv_guete_auswertung.py
#  Zweck: Prüft die rechnende Hälfte des Güte-Messwerkzeugs
#         (tools/archiv_guete/werte_aus.py). Sie entscheidet über eine
#         FREIGABE — eine falsche Kennzahl dort belegt etwas, das nicht gilt.
#  Warum hier und nicht im Werkzeug-Verzeichnis: Das Erheben braucht eine
#         laufende Instanz und gehört deshalb ausdrücklich in keinen Prüflauf
#         (tools/archiv_guete/README.md). Das RECHNEN braucht nichts als die
#         Rohdateien und ist damit ganz normal prüfbar.
# ============================================================
from __future__ import annotations

import importlib.util
import math
import sys
from pathlib import Path
from typing import Any

import pytest

_PFAD = Path(__file__).resolve().parents[2] / "tools" / "archiv_guete" / "werte_aus.py"


def _lade() -> Any:
    spec = importlib.util.spec_from_file_location("archiv_guete_werte_aus", _PFAD)
    assert spec is not None and spec.loader is not None
    modul = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modul
    spec.loader.exec_module(modul)
    return modul


@pytest.fixture(scope="module")
def werte_aus() -> Any:
    return _lade()


def _erinnerung(art: str, kennung: int) -> dict:
    """Ein Gedächtnis-Treffer, wie ihn `miss.py` roh ablegt."""
    return {"schluessel": "memory:0", "detail": {"quelle": {"art": art, "id": kennung}}}


# ──────────────────────────────────────────────────────────────────────
#  Der Rückweg — ohne ihn ist die zweite Schwelle nicht messbar
# ──────────────────────────────────────────────────────────────────────


def test_rueckweg_wird_auf_den_goldset_schluessel_aufgeloest(werte_aus: Any) -> None:
    """Ohne Auflösung trägt JEDER Gedächtnis-Treffer denselben Schlüssel.

    Er wäre dann auf keinen Goldset-Eintrag abbildbar, und die Messung meldete
    null Zusatztreffer — nicht, weil nichts gefunden wurde, sondern weil sich
    nicht zuordnen liesse, was gefunden wurde.
    """
    assert werte_aus._schluessel(_erinnerung("maintenance", 7)) == "maintenance:7"


def test_ohne_rueckweg_wird_nichts_geraten(werte_aus: Any) -> None:
    """Altbestand trägt den Rückweg nicht — dann bleibt es bei `memory:0`.

    Eine geratene Zuordnung schriebe der Messung einen Treffer gut, den niemand
    geprüft hat. Ein nicht zuordenbarer Treffer ist ehrlicher als ein falsch
    zugeordneter.
    """
    assert werte_aus._schluessel({"schluessel": "memory:0", "detail": {}}) == "memory:0"
    assert werte_aus._schluessel({"schluessel": "note:4", "detail": {}}) == "note:4"


@pytest.mark.parametrize(
    "quelle",
    [
        {"art": "maintenance"},  # Kennung fehlt → zeigt auf eine ganze Tabelle
        {"id": 7},  # Art fehlt → zeigt auf eine Zahl ohne Bezug
        {"art": "maintenance", "id": 0},  # Kennung 0 ist keine Zeile
        "maintenance:7",  # gar kein Verzeichnis
    ],
)
def test_halber_rueckweg_gilt_nicht(werte_aus: Any, quelle: object) -> None:
    """Beide Felder werden verlangt — sonst entsteht ein Schlüssel ins Leere."""
    treffer = {"schluessel": "memory:0", "detail": {"quelle": quelle}}
    assert werte_aus._schluessel(treffer) == "memory:0"


# ──────────────────────────────────────────────────────────────────────
#  Doppelzählung — der Fehler, der eine Freigabe belegen würde
# ──────────────────────────────────────────────────────────────────────


def test_derselbe_vorgang_zweimal_geliefert_zaehlt_einmal(werte_aus: Any) -> None:
    """Zwei Erinnerungen können auf DIESELBE Quellzeile zeigen.

    Die Zusammenführung in der Suche entfernt Erinnerungen nur gegen eigene
    Treffer, nicht untereinander — dieser Fall ist dort ausdrücklich offen
    gelassen. Zählte die Auswertung ihn doppelt, stiege die Trefferquote über
    1,0, ohne dass ein einziger Eintrag mehr gefunden wäre: eine Kennzahl, die
    eine Freigabe belegt, die nicht gilt.
    """
    doppelt = [_erinnerung("maintenance", 7), _erinnerung("maintenance", 7)]

    k = werte_aus.kennzahlen(doppelt, {"maintenance:7": 2}, 10)

    assert k["davon_relevant"] == 1
    assert k["recall"] == 1.0
    assert k["ndcg"] <= 1.0


def test_die_wiederholung_senkt_die_praezision(werte_aus: Any) -> None:
    """AUFBAU-KONTROLLE zur Entdoppelung: Sie darf die Dublette nicht verstecken.

    Ein zweites Mal derselbe Vorgang belegt einen ausgelieferten Platz und trägt
    nichts bei. Würde die Entdoppelung ihn auch aus dem Nenner nehmen, sähe eine
    Trefferliste mit Dubletten genauso gut aus wie eine ohne — und der Anreiz,
    sie zu beseitigen, wäre fort.
    """
    einfach = werte_aus.kennzahlen([_erinnerung("maintenance", 7)], {"maintenance:7": 2}, 10)
    doppelt = werte_aus.kennzahlen([_erinnerung("maintenance", 7)] * 2, {"maintenance:7": 2}, 10)

    assert einfach["praezision"] == 1.0
    assert doppelt["praezision"] == 0.5


def test_zwei_verschiedene_vorgaenge_zaehlen_beide(werte_aus: Any) -> None:
    """GEGENSTÜCK: Die Entdoppelung darf nicht zu viel wegnehmen.

    Ohne diesen Test liesse sich später auf „je Anfrage nur ein Gedächtnis-
    Treffer" verengen, und die Messung meldete weiter plausible Zahlen.
    """
    k = werte_aus.kennzahlen(
        [_erinnerung("maintenance", 7), _erinnerung("maintenance", 9)],
        {"maintenance:7": 2, "maintenance:9": 1},
        10,
    )

    assert k["davon_relevant"] == 2
    assert k["recall"] == 1.0


def test_eigener_treffer_und_erinnerung_auf_dieselbe_zeile_zaehlen_einmal(
    werte_aus: Any,
) -> None:
    """Der Fall, für den der Rückweg gebaut wurde — quellenübergreifend.

    Die Suche führt beide zusammen; träfe sie es einmal nicht, dürfte die
    Messung den Vorgang trotzdem nicht doppelt gutschreiben.
    """
    k = werte_aus.kennzahlen(
        [{"schluessel": "maintenance:7", "detail": {}}, _erinnerung("maintenance", 7)],
        {"maintenance:7": 2},
        10,
    )

    assert k["davon_relevant"] == 1


# ──────────────────────────────────────────────────────────────────────
#  Die Schwelle — was das Werkzeug AUSGIBT, muss sein, was es RECHNET
# ──────────────────────────────────────────────────────────────────────


def test_die_ausgabe_nennt_die_geltende_schwellenfassung() -> None:
    """Der Messbericht lädt dazu ein, das Werkzeug selbst laufen zu lassen.

    Stünde dort noch der frühere Wortlaut („schlechter als die Baseline"), läse
    ein Dritter ein Urteil über eine Bedingung, die so nicht mehr gilt — und
    zwar ausgerechnet in der Zeile, die ERFUELLT meldet.

    Geprüft wird auf dem QUELLTEXT der Ausgabezeilen, nicht auf der ganzen
    Datei: Der frühere Wortlaut steht als Erklärung weiterhin im Kommentar, und
    genau daran bliebe eine Suche über die ganze Datei hängen.
    """
    quelltext = _PFAD.read_text(encoding="utf-8")
    zeilen = [z.strip() for z in quelltext.splitlines() if z.strip().startswith("print(")]
    ausgabe = "\n".join(zeilen)

    assert "ein zutreffender Treffer VERLOREN" in ausgabe
    assert "kein verlorener Treffer" in ausgabe
    assert "schlechter als die Baseline" not in ausgabe
    assert "keine Verschlechterung" not in ausgabe


# ──────────────────────────────────────────────────────────────────────
#  Ein falsch verdrahteter Lauf darf sich nicht wie ein Messergebnis lesen
# ──────────────────────────────────────────────────────────────────────


def test_leerer_bewertungssatz_wird_abgewiesen(werte_aus: Any) -> None:
    """Der gefährlichste Aufbaufehler: null Kennzahlen, die geglaubt werden.

    Als der Goldset-Pfad noch fest verdrahtet war, rechnete ein Lauf gegen den
    NEUEN Bestand stillschweigend gegen die ALTEN Urteile. Kein Schlüssel passte,
    alle Kennzahlen wurden null — und das las sich wie ein vernichtendes Urteil
    über die Suche statt wie ein Verdrahtungsfehler. Ein Aufbaufehler, der sich
    als Messergebnis liest, ist schlimmer als ein Absturz: Er wird geglaubt.
    """
    with pytest.raises(SystemExit):
        werte_aus.pruefe_goldset({"B01": {}, "B02": {}}, "goldset_falsch.json")


def test_bewertungssatz_mit_eintraegen_laeuft_durch(werte_aus: Any) -> None:
    """AUFBAU-KONTROLLE: Der Wächter darf keinen gültigen Satz abweisen.

    Ohne diesen Fall liesse sich die Bedingung später verschärfen — etwa auf
    „jede Anfrage braucht Einträge" —, und ein Bewertungssatz mit einer bewusst
    leeren Anfrage (im Bestand gibt es keinen zutreffenden Eintrag) wäre plötzlich
    nicht mehr auswertbar.
    """
    werte_aus.pruefe_goldset({"B01": {"note:7": 2}, "B02": {}}, "goldset_v2.json")


# ──────────────────────────────────────────────────────────────────────
#  Trägt der Unterschied? — der Permutationstest
# ──────────────────────────────────────────────────────────────────────


def test_lauter_gleichgerichtete_differenzen_ergeben_den_kleinstmoeglichen_wert(
    werte_aus: Any,
) -> None:
    """Bei drei gleichgerichteten Differenzen sind nur zwei von acht Vorzeichen-
    Belegungen so extrem wie die beobachtete — die alles-plus und die alles-minus.

    Das ist die Rechnung von Hand nachvollzogen, nicht die Ausgabe des Codes
    abgeschrieben: 2/8 = 0,25. Ein Test, der nur „irgendein kleiner Wert" prüft,
    bliebe auch bei einer falschen Normierung grün.
    """
    p_wert, exakt = werte_aus.permutationstest([0.1, 0.2, 0.3])

    assert exakt is True
    assert p_wert == pytest.approx(0.25)


def test_lauter_nullen_ergeben_gewissheit_ueber_nichts(werte_aus: Any) -> None:
    """AUFBAU-KONTROLLE: Ohne Unterschied muss p = 1,0 herauskommen.

    Ohne diesen Fall liesse sich der Vergleich versehentlich auf `>` statt `>=`
    stellen; dann meldete ein Lauf ohne jeden Unterschied p = 0 — also größte
    Signifikanz für nichts.
    """
    p_wert, exakt = werte_aus.permutationstest([0.0, 0.0, 0.0, 0.0])

    assert exakt is True
    assert p_wert == pytest.approx(1.0)


def test_die_richtung_der_differenz_aendert_den_wert_nicht(werte_aus: Any) -> None:
    """Zweiseitig heisst: das Vorzeichen der Gesamtdifferenz ist gleichgültig."""
    hin, _ = werte_aus.permutationstest([0.1, 0.2, 0.3])
    zurueck, _ = werte_aus.permutationstest([-0.1, -0.2, -0.3])

    assert hin == pytest.approx(zurueck)


def test_ohne_paare_wird_kein_wert_erfunden(werte_aus: Any) -> None:
    """Keine vergleichbare Anfrage heisst KEIN p-Wert — nicht p = 1,0.

    Ein Wert, der aus null Beobachtungen entsteht, sähe im Bericht aus wie ein
    Ergebnis. Genau diese Klasse Fehler hat der leere Bewertungssatz schon
    einmal erzeugt.
    """
    assert werte_aus.permutationstest([]) is None


# ──────────────────────────────────────────────────────────────────────
#  Die verdichtete Ranggüte — gegen die Pool-Verzerrung
# ──────────────────────────────────────────────────────────────────────


def _treffer(schluessel: str) -> dict:
    return {"schluessel": schluessel, "detail": {}}


def test_unbeurteilte_eintraege_werden_entfernt_nicht_abgewertet(werte_aus: Any) -> None:
    """Sakai 2007: Wer nicht beurteilt wurde, zählt nicht als „nicht zutreffend".

    Der unbeurteilte Eintrag steht hier VOR dem zutreffenden und drückt ihn in
    der gewöhnlichen Rechnung auf Platz 2. Herausgenommen rückt der zutreffende
    auf Platz 1 — und genau um diesen Betrag benachteiligt die gewöhnliche
    Rechnung jede Variante, die neue Einträge mitbringt.
    """
    liste = [_treffer("note:99"), _treffer("note:7")]
    relevant = {"note:7": 2}
    beurteilt = {"note:7": 2}  # note:99 hat NIEMAND angesehen

    z = werte_aus.kennzahlen(liste, relevant, 10, beurteilt)

    assert z["unbeurteilt"] == 1
    assert z["ndcg"] == pytest.approx(1 / math.log2(3))
    assert z["ndcg_verdichtet"] == pytest.approx(1.0)


def test_beurteilt_und_nicht_zutreffend_bleibt_in_der_liste(werte_aus: Any) -> None:
    """AUFBAU-KONTROLLE — der ganze Zweck der zweiten Datei.

    Ein Eintrag, den ein Beurteiler ANGESEHEN und mit 0 bewertet hat, ist ein
    echter Fehltreffer und muss den zutreffenden weiterhin nach hinten drücken.
    Würde die Verdichtung auch ihn entfernen, wäre sie kein Korrektiv mehr,
    sondern eine Schönrechnung: Jede Liste stünde am Ende perfekt da.
    """
    liste = [_treffer("note:99"), _treffer("note:7")]
    relevant = {"note:7": 2}
    beurteilt = {"note:7": 2, "note:99": 0}  # angesehen, nicht zutreffend

    z = werte_aus.kennzahlen(liste, relevant, 10, beurteilt)

    assert z["unbeurteilt"] == 0
    assert z["ndcg_verdichtet"] == pytest.approx(z["ndcg"])


def test_ohne_beurteilte_menge_wird_nichts_geschaetzt(werte_aus: Any) -> None:
    """Fehlt die beurteilte Menge, bleibt die Kennzahl leer statt geraten.

    Eine Zahl, die so tut, als wäre die Verzerrung behandelt, ist schlimmer als
    keine — sie steht im Bericht neben den echten und ist von ihnen nicht zu
    unterscheiden.
    """
    z = werte_aus.kennzahlen([_treffer("note:7")], {"note:7": 2}, 10)

    assert z["ndcg_verdichtet"] is None
    assert z["unbeurteilt"] is None


def test_die_beurteilte_menge_wird_neben_dem_bewertungssatz_gesucht(
    werte_aus: Any, tmp_path: Any
) -> None:
    """Der Pfad wird abgeleitet, nicht zusätzlich verlangt.

    Ein zweiter Pfad auf der Kommandozeile wäre eine zweite Stelle, an der sich
    ein Lauf falsch verdrahten liesse — und genau dieser Fehler ist bei Goldset
    und Anfragedatei schon zweimal passiert.
    """
    (tmp_path / "beurteilt_v3.json").write_text('{"B01": {"note:7": 2}}', encoding="utf-8")

    gefunden = werte_aus.lade_beurteilte(str(tmp_path / "goldset_v3.json"))
    fehlend = werte_aus.lade_beurteilte(str(tmp_path / "goldset_v9.json"))

    assert gefunden == {"B01": {"note:7": 2}}
    assert fehlend is None
