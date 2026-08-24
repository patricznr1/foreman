# ============================================================
#  FOREMAN — tools/pruefe_registerzahlen.py
#  Zweck: Haelt die Kennzahlen des Aussagen-Registers (§23) gegen den
#         Ist-Stand. Meldet Abweichungen, blockiert nichts.
#  Anlass: Zwischen dem 10.08. und dem 24.08.2026 liefen drei Aenderungen
#         durch, ohne dass eine einzige Registerzahl nachgezogen wurde —
#         der zweite Fall derselben Klasse. Eine Regel, die zweimal
#         gerissen ist, braucht einen Traeger, kein weiteres Merkblatt.
#  Architektur-Einordnung: Werkzeug, kein Anwendungscode. Keine Abhaengigkeit
#         auf das maschinenlokale claims-Werkzeug — nur PyYAML.
#  TYPPRUEFUNG: Liegt ausserhalb des Standard-Scopes (pyproject: packages =
#         ["foreman"], mypy_path = "src"). Die Konfiguration dafuer umzubauen
#         waere fuer ein Hilfsmittel unverhaeltnismaessig — geprueft wird
#         einzeln und streng:
#             uv run mypy --strict tools/pruefe_registerzahlen.py
#         Stand 24.08.2026: sauber. Wer hier etwas aendert, faehrt den Befehl.
# ============================================================
"""Prüft, ob die im Register geführten Kennzahlen noch zum Bestand passen.

BEWUSST KEIN CI-GATE. Die Testzahl ändert sich mit jedem hinzugefügten Test;
ein blockierender Schritt würde jeden Beitrag aufhalten, um einen Stichtagswert
nachzuziehen. Das wäre Bürokratie, nicht Sorgfalt.

Der Ort, an dem die Frische zählt, ist ein anderer: bevor eine Zahl das Haus
verlässt. Deshalb läuft dieses Werkzeug zusammen mit `claims check` vor jeder
externen Unterlage — und sagt dann, welche Zahl seit ihrer Messung gewandert
ist.

Aufruf:
    uv run python -m tools.pruefe_registerzahlen
    uv run python -m tools.pruefe_registerzahlen --schnell   # ohne Typprüfung
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

WURZEL = Path(__file__).resolve().parent.parent
REGISTER = WURZEL / "claims" / "claims.yaml"


@dataclass(frozen=True)
class Kennzahl:
    """Eine Registerzahl und der Weg, sie erneut zu erheben."""

    claim_id: str
    was: str
    # Muster, das den Wert AUS DEM REGISTEREINTRAG zieht.
    muster_register: str
    befehl: tuple[str, ...]
    # Muster, das den Wert aus der Ausgabe des Befehls zieht.
    muster_ist: str
    langsam: bool = False
    # Optionales zweites Registermuster, dessen Wert ADDIERT wird.
    #
    # WARUM: Der erste Entwurf verglich "1068 bestanden" mit "1070 gesammelt"
    # und meldete eine Abweichung, die keine war — zwei verschiedene Groessen,
    # gleich aussehend. Genau die Fehlerklasse, gegen die das Register gebaut
    # ist, im Werkzeug fuer das Register. Gesammelt = bestanden + uebersprungen;
    # die Abgewaehlten zaehlt `--collect-only` bereits heraus.
    muster_register_plus: str | None = None


# --no-cov ist bei --collect-only PFLICHT: Ohne ausgefuehrte Tests reisst das
# Abdeckungs-Gate und der Lauf meldet einen Fehlschlag, der nichts bedeutet —
# ein roter Haken ohne Wirkung.
KENNZAHLEN: tuple[Kennzahl, ...] = (
    Kennzahl(
        claim_id="C-018",
        was="Anzahl gesammelter Prüfungen im Backend",
        muster_register=r"(\d+) bestanden",
        muster_register_plus=r"(\d+) übersprungen",
        befehl=(
            "uv",
            "run",
            "--frozen",
            "--extra",
            "dev",
            "pytest",
            "--collect-only",
            "-q",
            "--no-cov",
        ),
        muster_ist=r"(\d+)/\d+ tests collected",
    ),
    Kennzahl(
        claim_id="C-022",
        was="Dateizahl der Formatprüfung",
        muster_register=r"Formatprüfung über (\d+) Dateien",
        befehl=("uv", "run", "--frozen", "--extra", "dev", "ruff", "format", "--check"),
        muster_ist=r"(\d+) files already formatted",
    ),
    Kennzahl(
        claim_id="C-022",
        was="Dateizahl der Typprüfung",
        muster_register=r"über (\d+) Dateien im Backend",
        befehl=("uv", "run", "--frozen", "--extra", "dev", "mypy"),
        muster_ist=r"no issues found in (\d+) source files",
        langsam=True,
    ),
)


def lade_register() -> dict[str, Any]:
    """Liest das Register. Ohne das maschinenlokale Werkzeug — nur PyYAML."""
    with REGISTER.open(encoding="utf-8") as datei:
        rohdaten = yaml.safe_load(datei)
    if not isinstance(rohdaten, dict):
        raise SystemExit(f"❌ Register nicht lesbar: {REGISTER}")
    return rohdaten


def registerwert(register: dict[str, Any], kennzahl: Kennzahl) -> tuple[int, str] | None:
    """Zieht die Zahl aus dem `wert`-Feld eines Eintrags, plus dessen Datum.

    Ist ein zweites Muster gesetzt, wird dessen Wert addiert — siehe die
    Begruendung an `muster_register_plus`.
    """
    for eintrag in register.get("claims") or []:
        if eintrag.get("id") != kennzahl.claim_id:
            continue
        wert = str(eintrag.get("wert") or "")
        treffer = re.search(kennzahl.muster_register, wert)
        if treffer is None:
            return None
        summe = int(treffer.group(1))
        if kennzahl.muster_register_plus is not None:
            zweiter = re.search(kennzahl.muster_register_plus, wert)
            if zweiter is None:
                return None
            summe += int(zweiter.group(1))
        return summe, str(eintrag.get("datum") or "?")
    return None


def istwert(kennzahl: Kennzahl) -> int | None:
    """Erhebt den Ist-Wert. Gibt None zurück, wenn der Befehl nicht lief."""
    try:
        # Feste Befehlsliste aus KENNZAHLEN, keine Nutzereingabe — kein Shell-Aufruf.
        lauf = subprocess.run(
            kennzahl.befehl, cwd=WURZEL, capture_output=True, text=True, timeout=900
        )
    except (OSError, subprocess.TimeoutExpired) as fehler:
        print(f"⚠️  {kennzahl.claim_id} {kennzahl.was}: Befehl lief nicht ({fehler})")
        return None
    ausgabe = f"{lauf.stdout}\n{lauf.stderr}"
    treffer = re.search(kennzahl.muster_ist, ausgabe)
    if treffer is None:
        # Ein leeres Ergebnis ist erst dann ein Befund, wenn belegt ist, dass
        # das Werkzeug lief. Hier ist es das nicht — also melden statt werten.
        print(
            f"⚠️  {kennzahl.claim_id} {kennzahl.was}: Ausgabe passt nicht zum Muster "
            f"(Rückgabecode {lauf.returncode}) — nicht gewertet"
        )
        return None
    return int(treffer.group(1))


def main() -> int:
    zerleger = argparse.ArgumentParser(description="Registerzahlen gegen den Bestand halten")
    zerleger.add_argument("--schnell", action="store_true", help="langsame Prüfungen überspringen")
    argumente = zerleger.parse_args()

    register = lade_register()
    print(f"📋 Register {REGISTER.relative_to(WURZEL)} — Stand {register.get('stand', '?')}\n")

    abweichungen = 0
    ungeprueft = 0
    for kennzahl in KENNZAHLEN:
        if argumente.schnell and kennzahl.langsam:
            print(f"⏭️  {kennzahl.claim_id} {kennzahl.was}: übersprungen (--schnell)")
            ungeprueft += 1
            continue
        soll = registerwert(register, kennzahl)
        if soll is None:
            print(f"⚠️  {kennzahl.claim_id} {kennzahl.was}: im Register nicht gefunden")
            ungeprueft += 1
            continue
        sollwert, datum = soll
        ist = istwert(kennzahl)
        if ist is None:
            ungeprueft += 1
            continue
        if ist == sollwert:
            print(f"✅ {kennzahl.claim_id} {kennzahl.was}: {ist} (Register {datum})")
        else:
            abweichungen += 1
            print(
                f"❌ {kennzahl.claim_id} {kennzahl.was}: Register führt {sollwert} "
                f"(gemessen {datum}), Bestand hat {ist}"
            )

    print()
    if abweichungen:
        print(
            f"📋 {abweichungen} Kennzahl(en) gewandert. Das ist kein Fehler im Code — "
            "aber diese Zahlen dürfen so nicht nach draußen. Vor einer externen "
            "Unterlage neu messen und den Eintrag nachziehen (GROUND_TRUTH §23.1)."
        )
    else:
        print("📋 Alle geprüften Kennzahlen decken sich mit dem Bestand.")
    if ungeprueft:
        print(f"📋 {ungeprueft} nicht geprüft — siehe Meldungen oben.")
    # Rueckgabecode 0 auch bei Abweichung: Dieses Werkzeug meldet, es blockiert
    # nicht. Wer es als Gate will, wertet die Ausgabe selbst aus.
    return 0


if __name__ == "__main__":
    sys.exit(main())
