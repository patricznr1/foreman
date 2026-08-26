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

Aufruf:  python scripts/check_findings.py [--strict]
Benötigt: PyYAML.
"""

from __future__ import annotations

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

        zustand = eintrag.get("status")
        if zustand not in ZUSTAENDE:
            bericht.fehlt(f"status muss aus {sorted(ZUSTAENDE)} sein, ist: {zustand!r}", kennung)
        else:
            noetig = PFLICHTFELD_JE_ZUSTAND[zustand]
            if not eintrag.get(noetig):
                bericht.fehlt(
                    f"status '{zustand}' verlangt das Feld '{noetig}' — ohne es ist der "
                    f"Eintrag nicht nachvollziehbar",
                    kennung,
                )

        # Jeder genannte Pfad muss existieren. Eine Begründung, die auf eine
        # verschwundene Datei zeigt, ist keine mehr.
        for stelle in eintrag.get("where") or []:
            pfad = wurzel / _pfad_ohne_zeile(str(stelle))
            if not pfad.exists():
                bericht.fehlt(f"Pfad existiert nicht: {stelle}", kennung)

        # Belege werden ebenso geprüft, aber ein Verweis nach außen (http) ist
        # kein Pfad und wird übersprungen.
        for beleg in eintrag.get("evidence") or []:
            text = str(beleg)
            if text.startswith(("http://", "https://")):
                continue
            if not (wurzel / _pfad_ohne_zeile(text)).exists():
                bericht.fehlt(f"Beleg existiert nicht: {beleg}", kennung)

        frist = _als_datum(eintrag.get("review_by"))
        if frist is None:
            bericht.fehlt(
                f"review_by ist kein Datum (JJJJ-MM-TT): {eintrag.get('review_by')!r}", kennung
            )
        elif frist < heute and eintrag.get("status") != "fixed":
            bericht.fehlt(
                f"Wiedervorlage am {frist.isoformat()} verstrichen — der Eintrag ist "
                f"neu zu bewerten, nicht fortzuschreiben",
                kennung,
            )
        elif frist < heute:
            bericht.warnt(
                f"Wiedervorlage am {frist.isoformat()} verstrichen (Eintrag ist erledigt)",
                kennung,
            )

    kopf_frist = _als_datum(register.get("next_review"))
    if kopf_frist is None:
        bericht.fehlt("next_review im Kopf fehlt oder ist kein Datum")
    elif kopf_frist < heute:
        bericht.fehlt(
            f"Die Wiedervorlage des Registers selbst ist am {kopf_frist.isoformat()} verstrichen"
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
    return bericht.ausgeben()


if __name__ == "__main__":
    raise SystemExit(main())
