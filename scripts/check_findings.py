#!/usr/bin/env python3
"""Hält security/findings.yaml ehrlich.

WARUM ES DIESES SKRIPT GIBT. Ein Register vorweggenommener Funde ist nur so viel
wert wie seine Pflege. Ohne Prüfung verrottet es auf drei Weisen, und alle drei
sehen von außen wie ein gepflegtes Register aus:

  1. Ein Eintrag zeigt auf eine Datei, die es nicht mehr gibt — die Begründung
     hängt dann in der Luft, und niemand merkt es.
  2. Eine Wiedervorlage verstreicht. Aus „bis November prüfen wir das erneut"
     wird stillschweigend „nie wieder".
  3. Ein akzeptiertes Risiko verliert die Bedingung, unter der es akzeptiert
     wurde. Damit wird aus einer Entscheidung eine Behauptung.

Deshalb ist der Lauf ein Tor in der Prüfkette: Das Register kann nicht verrotten,
ohne dass der Bau rot wird.

WAS ES NICHT KANN — und das gehört dazu, damit niemand mehr hineinliest: Es prüft
Form, nicht Inhalt. Ob eine Begründung trägt, ob eine Einstufung stimmt, ob eine
Zeilennummer noch auf die gemeinte Stelle zeigt — das sieht kein Syntaxbaum. Eine
verschobene Zeile innerhalb einer vorhandenen Datei fällt hier NICHT auf.

Seit dem 26.08.2026 prueft es zusaetzlich die ZAHLEN, mit denen die Dokumentation
auf dieses Register zeigt. Grund: dieselbe Zahl steht in vier Dateien, und beim
dritten Nachziehen von Hand war klar, dass die vierte Gelegenheit die ist, bei der
es jemand vergisst. Genau diese Klasse fuehrt das Register selbst als F-007, F-008
und F-015 — Doku, die etwas anderes behauptet als der Bestand hergibt.

Aufruf:  python scripts/check_findings.py [--strict]
Benötigt: PyYAML.
"""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as fehler:  # pragma: no cover - Umgebungsproblem
    sys.stderr.write("FEHLER: PyYAML fehlt. Installation:  pip install pyyaml\n")
    raise SystemExit(2) from fehler

REGISTER = Path("security/findings.yaml")

# Erlaubte Zustände. `status` folgt der SARIF-2.1.0-Unterdrückung, erweitert um
# `fixed` — SARIF kennt nur unterdrückt oder nicht, hier zählt auch der Vollzug.
ZUSTAENDE = {"accepted", "planned", "fixed", "disputed"}

# Was jeder Zustand zusätzlich mitbringen muss. Der Kern des Skripts:
#   accepted  -> depends_on: Ein akzeptiertes Risiko OHNE die Bedingung, unter
#                der es akzeptiert wurde, ist keine Entscheidung, sondern eine
#                Behauptung. Fällt die Bedingung, fällt die Annahme mit ihr.
#   planned   -> remedy: Ein Vorsatz ohne Abhilfe ist ein Vermerk.
#   fixed     -> fixed_at: Ein Vollzug ohne Datum ist nicht nachprüfbar.
#   disputed  -> justification: Ein Widerspruch ohne Begründung ist eine Meinung.
PFLICHTFELD_JE_ZUSTAND = {
    "accepted": "depends_on",
    "planned": "remedy",
    "fixed": "fixed_at",
    "disputed": "justification",
}

PFLICHTFELDER = (
    "id",
    "title",
    "where",
    "observation",
    "observation_is_correct",
    "status",
    "review_by",
)


class Bericht:
    """Sammelt Fehler und Warnungen und entscheidet den Rückgabewert."""

    def __init__(self, streng: bool) -> None:
        self._streng = streng
        self.fehler: list[str] = []
        self.warnungen: list[str] = []

    def fehlt(self, text: str, stelle: str = "") -> None:
        self.fehler.append(f"{text}{f'  [{stelle}]' if stelle else ''}")

    def warnt(self, text: str, stelle: str = "") -> None:
        self.warnungen.append(f"{text}{f'  [{stelle}]' if stelle else ''}")

    def ausgeben(self) -> int:
        for zeile in self.fehler:
            print(f"  FEHLER   {zeile}")
        for zeile in self.warnungen:
            print(f"  WARNUNG  {zeile}")
        offen = len(self.fehler) + (len(self.warnungen) if self._streng else 0)
        print("-" * 78)
        print(f"  ERGEBNIS: {len(self.fehler)} Fehler, {len(self.warnungen)} Warnungen")
        return 1 if offen else 0


def _pfad_ohne_zeile(eintrag: str) -> str:
    """Trennt eine angehängte Zeilennummer ab: `src/x.py:42` → `src/x.py`.

    Nur die LETZTE Doppelpunkt-Gruppe und nur, wenn sie eine Zahl ist — ein
    Doppelpunkt kommt in Pfaden vor, eine abschließende Zahl praktisch nie.
    """
    kopf, trenner, schwanz = eintrag.rpartition(":")
    return kopf if trenner and schwanz.isdigit() else eintrag


def _als_datum(wert: Any) -> date | None:
    """YAML liefert je nach Schreibweise `date` oder `str`."""
    if isinstance(wert, date):
        return wert
    if isinstance(wert, str):
        try:
            return date.fromisoformat(wert.strip())
        except ValueError:
            return None
    return None


def _pruefe_pfade(eintrag: dict[str, Any], kennung: str, wurzel: Path, bericht: Bericht) -> None:
    """Jeder genannte Pfad muss existieren.

    Eine Begruendung, die auf eine verschwundene Datei zeigt, ist keine mehr. Ein
    Verweis nach aussen (http) ist kein Pfad und wird uebersprungen.
    """
    for stelle in eintrag.get("where") or []:
        if not (wurzel / _pfad_ohne_zeile(str(stelle))).exists():
            bericht.fehlt(f"Pfad existiert nicht: {stelle}", kennung)

    for beleg in eintrag.get("evidence") or []:
        text = str(beleg)
        if text.startswith(("http://", "https://")):
            continue
        if not (wurzel / _pfad_ohne_zeile(text)).exists():
            bericht.fehlt(f"Beleg existiert nicht: {beleg}", kennung)


def _pruefe_zustand(eintrag: dict[str, Any], kennung: str, bericht: Bericht) -> None:
    """Der Zustand muss bekannt sein und sein zustandsabhaengiges Pflichtfeld tragen."""
    zustand = eintrag.get("status")
    if zustand not in ZUSTAENDE:
        bericht.fehlt(f"status muss aus {sorted(ZUSTAENDE)} sein, ist: {zustand!r}", kennung)
        return
    noetig = PFLICHTFELD_JE_ZUSTAND[zustand]
    if not eintrag.get(noetig):
        bericht.fehlt(
            f"status '{zustand}' verlangt das Feld '{noetig}' — ohne es ist der "
            f"Eintrag nicht nachvollziehbar",
            kennung,
        )


def _pruefe_frist(eintrag: dict[str, Any], kennung: str, heute: date, bericht: Bericht) -> None:
    """Eine verstrichene Wiedervorlage ist bei offenen Eintraegen ein Fehler.

    Bei erledigten nur eine Warnung: dort ist die Frist eine Erinnerung, keine Pflicht.
    """
    frist = _als_datum(eintrag.get("review_by"))
    if frist is None:
        bericht.fehlt(
            f"review_by ist kein Datum (JJJJ-MM-TT): {eintrag.get('review_by')!r}", kennung
        )
    elif frist >= heute:
        return
    elif eintrag.get("status") != "fixed":
        bericht.fehlt(
            f"Wiedervorlage am {frist.isoformat()} verstrichen — der Eintrag ist "
            f"neu zu bewerten, nicht fortzuschreiben",
            kennung,
        )
    else:
        bericht.warnt(
            f"Wiedervorlage am {frist.isoformat()} verstrichen (Eintrag ist erledigt)",
            kennung,
        )


def pruefe(register: dict[str, Any], wurzel: Path, bericht: Bericht) -> None:
    eintraege = register.get("findings") or []
    if not eintraege:
        bericht.fehlt("Register enthält keinen einzigen Eintrag — dann prüft dieser Lauf nichts")
        return

    heute = date.today()
    gesehen: set[str] = set()

    for eintrag in eintraege:
        kennung = str(eintrag.get("id", "<ohne id>"))

        for feld in PFLICHTFELDER:
            if eintrag.get(feld) in (None, "", []):
                bericht.fehlt(f"Pflichtfeld fehlt: {feld}", kennung)

        if kennung in gesehen:
            bericht.fehlt("Kennung doppelt vergeben", kennung)
        gesehen.add(kennung)

        _pruefe_zustand(eintrag, kennung, bericht)
        _pruefe_pfade(eintrag, kennung, wurzel, bericht)
        _pruefe_frist(eintrag, kennung, heute, bericht)

    kopf_frist = _als_datum(register.get("next_review"))
    if kopf_frist is None:
        bericht.fehlt("next_review im Kopf fehlt oder ist kein Datum")
    elif kopf_frist < heute:
        bericht.fehlt(
            f"Die Wiedervorlage des Registers selbst ist am {kopf_frist.isoformat()} verstrichen"
        )


# --- Zahlen in der Prosa ---------------------------------------------------
# Vier Dateien nennen die Groesse und die Verteilung dieses Registers im Fliesstext.
# Ohne Pruefung driften sie auseinander, sobald ein Eintrag hinzukommt: die Zahl
# steht an sechs Stellen in vier Dateien, und es genuegt, eine davon zu uebersehen.

ZAHLWORT = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}

# Je Datei die Stellen, die dort stehen MUESSEN — als Zuordnung, nicht als eine
# gemeinsame Liste. Grund: eine gemeinsame Liste haette nur zaehlen koennen, wie viele
# Stellen irgendwo trafen, und waere gruen geblieben, solange in einer Datei mit zwei
# Stellen noch eine steht. Die Gegenprobe hat genau das gezeigt. Jede Stelle wird
# deshalb einzeln belegt.
#
# Schluessel ist `gesamt` oder ein Zustand aus ZUSTAENDE. Die Muster treffen den
# Satzbau, in dem die Zahl heute steht — bewusst eng, damit sie nicht jede beliebige
# Zahl im Dokument einfangen. Wer einen dieser Saetze umformuliert, muss das Muster
# mitziehen; die Pruefung meldet sich, statt still auszufallen.
PROSA_STELLEN: dict[str, tuple[tuple[str, str], ...]] = {
    "README.md": (
        (r"([\w-]+) findings a review", "gesamt"),
        (r"([\w-]+) are accepted risks", "accepted"),
        (r"([\w-]+) are open work", "planned"),
        (r"([\w-]+) are already closed", "fixed"),
        (r"([\w-]+) is a documented false positive", "disputed"),
    ),
    "SECURITY.md": (
        (r"Of its ([\w-]+) entries", "gesamt"),
        (r"([\w-]+) are accepted risks", "accepted"),
        (r"([\w-]+) are open work", "planned"),
        (r"([\w-]+) are already closed", "fixed"),
        (r"([\w-]+) is a documented false positive", "disputed"),
    ),
    "REVIEW.md": (
        (r"([\w-]+) of them: the observation", "gesamt"),
        (r"([\w-]+) are open work", "planned"),
        (r"([\w-]+) entries are already closed", "fixed"),
        (r"([\w-]+) is a documented false positive", "disputed"),
    ),
    "SECURITY-INSIGHTS.yml": (
        (r"records ([\w-]+) that are already triaged", "gesamt"),
        (r"covering ([\w-]+) findings", "gesamt"),
        (r"([\w-]+) are accepted risks", "accepted"),
        (r"([\w-]+) are open work", "planned"),
        (r"([\w-]+) are already closed", "fixed"),
        (r"([\w-]+) is a documented false positive", "disputed"),
    ),
}


def _als_zahl(wort: str) -> int | None:
    """Loest ein Zahlwort auf, auch zusammengesetzt: `twenty-two` wird 22.

    Notwendig, seit das Register zwanzig Eintraege ueberschritten hat. Ohne die
    Zerlegung faende der Ausdruck nur den Teil hinter dem Bindestrich und meldete
    `two` gegen 22 — ein Fehlalarm, der die Pruefung unglaubwuerdig machte. Die
    Bedingung `>= 20` haelt Unsinn wie `five-three` heraus.
    """
    if wort in ZAHLWORT:
        return ZAHLWORT[wort]
    zehner, trenner, einer = wort.partition("-")
    if trenner and zehner in ZAHLWORT and einer in ZAHLWORT and ZAHLWORT[zehner] >= 20:
        return ZAHLWORT[zehner] + ZAHLWORT[einer]
    return None


def pruefe_prosa_zahlen(register: dict[str, Any], wurzel: Path, bericht: Bericht) -> None:
    """Haelt die Zahlwoerter in der Dokumentation gegen den Bestand des Registers.

    Zwei Dinge werden geprueft, und das zweite ist das wichtigere:

      1. Stimmt die genannte Zahl? Jede Fundstelle einzeln, nicht als Summe.
      2. Ist die Stelle ueberhaupt noch da? Verschwindet der Satzbau, verschwindet
         die Pruefung mit ihm — lautlos. Deshalb ist eine Stelle ohne Treffer ein
         Fehler und keine Erleichterung.
    """
    eintraege = register.get("findings") or []
    ist: dict[str, int] = {"gesamt": len(eintraege)}
    for zustand in ZUSTAENDE:
        ist[zustand] = sum(1 for e in eintraege if e.get("status") == zustand)

    for name, stellen in PROSA_STELLEN.items():
        pfad = wurzel / name
        if not pfad.exists():
            bericht.fehlt(f"Prosa-Datei fehlt, die auf das Register zeigt: {name}")
            continue

        # Zwei Normalisierungen, beide durch die Gegenprobe erzwungen:
        # Fettung raus, damit `**four are open work**` wie ohne trifft — und jede
        # Folge von Leerraum auf ein Leerzeichen, weil Markdown mitten im Satz
        # umbricht, und ein Muster sonst an der Zeilengrenze zerbricht, ohne dass
        # jemand es merkt.
        roh = pfad.read_text(encoding="utf-8").replace("**", "")
        text = re.sub(r"\s+", " ", roh)

        for muster, schluessel in stellen:
            treffer = list(re.finditer(muster, text))
            if not treffer:
                bericht.fehlt(
                    f"{name}: die Angabe zu '{schluessel}' ist in bekannter Form nicht "
                    f"mehr auffindbar — entweder ist sie entfallen oder der Satzbau hat "
                    f"diese Pruefung stillgelegt",
                )
                continue
            for fund in treffer:
                wort = fund.group(1).lower()
                gelesen = _als_zahl(wort)
                if gelesen is None:
                    bericht.fehlt(f"{name}: '{wort}' vor '{schluessel}' ist kein Zahlwort")
                elif gelesen != ist[schluessel]:
                    bericht.fehlt(
                        f"{name}: Text sagt {wort} ({gelesen}) fuer '{schluessel}', "
                        f"das Register enthaelt {ist[schluessel]}",
                    )


def main() -> int:
    streng = "--strict" in sys.argv
    wurzel = Path(__file__).resolve().parents[1]
    register_pfad = wurzel / REGISTER

    print("=" * 78)
    print(f"  Fund-Register: {register_pfad}")
    print(f"  Modus: {'streng (Warnungen sind Fehler)' if streng else 'Normalbetrieb'}")
    print("=" * 78)

    if not register_pfad.exists():
        print(f"  FEHLER   Register nicht gefunden: {register_pfad}")
        return 1

    bericht = Bericht(streng)
    try:
        register = yaml.safe_load(register_pfad.read_text(encoding="utf-8"))
    except yaml.YAMLError as fehler:
        print(f"  FEHLER   YAML nicht lesbar: {fehler}")
        return 1

    pruefe(register or {}, wurzel, bericht)
    pruefe_prosa_zahlen(register or {}, wurzel, bericht)
    return bericht.ausgeben()


if __name__ == "__main__":
    raise SystemExit(main())
