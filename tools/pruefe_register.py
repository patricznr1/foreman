# ============================================================
#  FOREMAN — tools/pruefe_register.py
#  Zweck: Haelt das Aussagen-Register strukturell zusammen und stellt sicher,
#         dass die generierte Ansicht CLAIMS.md dasselbe sagt wie claims.yaml.
#  Anlass: CLAIMS.md liegt im oeffentlichen Repository und wird aus claims.yaml
#         ERZEUGT. Wer den Registereintrag aendert und `claims render` vergisst,
#         hinterlaesst draussen eine Aussage, die drinnen nicht mehr gilt — und
#         nichts im Repository merkt es. Das Erzeugerwerkzeug liegt auf Patrics
#         Maschine und kann in der Pruefpipeline nicht laufen; diese Pruefung
#         braucht nur PyYAML und laeuft deshalb ueberall.
#  Abgrenzung: KEIN Nachbau des Erzeugerwerkzeugs. Geprueft wird, was ohne
#         seinen Regelsatz belegbar ist — Struktur und Deckungsgleichheit.
#         Die Kennzahlen-Frische prueft `tools/pruefe_registerzahlen.py`, das
#         aus gutem Grund kein Gate ist; hier geht es um Zustaende, die sich
#         NUR aendern, wenn jemand das Register anfasst. Deshalb blockiert
#         diese Pruefung.
#  Architektur-Einordnung: Werkzeug, kein Anwendungscode.
#  TYPPRUEFUNG: Liegt ausserhalb des Standard-Scopes (pyproject: packages =
#         ["foreman"], mypy_path = "src") — wie das Schwesterwerkzeug einzeln
#         und streng geprueft:
#             uv run mypy --strict tools/pruefe_register.py
# ============================================================
"""Prüft das Aussagen-Register auf Struktur und die Ansicht auf Deckungsgleichheit.

Aufruf:
    uv run python -m tools.pruefe_register

Rückgabewert 0, wenn nichts zu beanstanden ist; sonst 1 mit einer Zeile je Verstoß.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

WURZEL = Path(__file__).resolve().parent.parent
REGISTER = WURZEL / "claims" / "claims.yaml"
ANSICHT = WURZEL / "CLAIMS.md"

# Aus dem Bestand abgeleitet, nicht erfunden (Stand 07.09.2026: 122 Einträge).
PFLICHTFELDER = (
    "id",
    "aussage",
    "status",
    "bedingung",
    "datum",
    "fundstelle",
    "geltung",
    "freigabe",
)
STATUS_WERTE = frozenset({"gemessen", "geschaetzt", "geplant", "konzipiert"})
GELTUNG_WERTE = frozenset({"gueltig", "ueberholt"})
FREIGABE_WERTE = frozenset({"intern", "fach", "kunde"})
ID_MUSTER = re.compile(r"^C-\d{3}$")
# Eine Aussage ist ein Satz, kein Absatz. Grenze aus dem Erzeugerwerkzeug (R14).
AUSSAGE_MAX = 200


@dataclass(frozen=True)
class Verstoss:
    """Eine Beanstandung mit ihrem Ort — der Ort steht vorn, damit die Ausgabe sortierbar ist."""

    wo: str
    was: str

    def __str__(self) -> str:
        return f"❌ {self.wo}: {self.was}"


def pruefe_kopf(register: dict[str, Any]) -> list[Verstoss]:
    """Der Kopf trägt Projekt und Stand — ohne sie ist kein Eintrag einzuordnen."""
    verstoesse: list[Verstoss] = []
    for feld in ("schema_version", "projekt", "produkt", "stand", "claims"):
        if not register.get(feld):
            verstoesse.append(Verstoss("Kopf", f"Feld „{feld}“ fehlt oder ist leer"))
    if not isinstance(register.get("claims"), list):
        verstoesse.append(Verstoss("Kopf", "„claims“ ist keine Liste"))
    return verstoesse


def _pflichtfelder(kennung: str, e: dict[str, Any]) -> list[Verstoss]:
    """Ohne diese Felder ist ein Eintrag keine Aussage, sondern eine Notiz."""
    return [
        Verstoss(kennung, f"Pflichtfeld „{feld}“ fehlt oder ist leer")
        for feld in PFLICHTFELDER
        if not e.get(feld)
    ]


def _wertebereiche(kennung: str, e: dict[str, Any], stand: str) -> list[Verstoss]:
    """Status, Geltung, Freigabe, Satzlänge und Datum gegen ihre erlaubten Werte."""
    verstoesse: list[Verstoss] = []

    if (status := e.get("status")) and status not in STATUS_WERTE:
        verstoesse.append(Verstoss(kennung, f"Status „{status}“ ist keiner der erlaubten"))
    if (geltung := e.get("geltung")) and geltung not in GELTUNG_WERTE:
        verstoesse.append(
            Verstoss(kennung, f"Geltung „{geltung}“ ist weder gueltig noch ueberholt")
        )

    verstoesse.extend(
        Verstoss(kennung, f"Freigabe „{f}“ ist keine der erlaubten")
        for f in e.get("freigabe") or []
        if f not in FREIGABE_WERTE
    )

    if len(str(e.get("aussage", ""))) > AUSSAGE_MAX:
        verstoesse.append(
            Verstoss(
                kennung, f"Aussage ist länger als {AUSSAGE_MAX} Zeichen — sie ist kein Satz mehr"
            )
        )

    # Ein Datum nach dem Stand hiesse: gemessen, bevor der Stand fortgeschrieben
    # wurde. Dann sagt der Kopf etwas anderes als der Eintrag.
    if (datum := str(e.get("datum", ""))) and stand and datum > stand:
        verstoesse.append(Verstoss(kennung, f"Datum {datum} liegt nach dem Stand {stand}"))

    return verstoesse


def _ueberholt(kennung: str, e: dict[str, Any]) -> list[Verstoss]:
    """Was nicht mehr gilt, braucht einen Grund und darf nicht mehr nach draussen."""
    if e.get("geltung") != "ueberholt":
        return []

    verstoesse: list[Verstoss] = []
    if not e.get("geltung_grund"):
        verstoesse.append(
            Verstoss(kennung, "ueberholt ohne geltung_grund — der Grund ist der ganze Wert")
        )
    # Eine ueberholte Aussage nach aussen freigegeben waere eine Behauptung, die
    # nicht mehr gilt — und niemand am Empfaenger sieht ihr das an.
    fremd = sorted(set(e.get("freigabe") or []) - {"intern"})
    if fremd:
        verstoesse.append(
            Verstoss(
                kennung, f"ueberholt, aber freigegeben für {', '.join(fremd)} statt nur intern"
            )
        )
    return verstoesse


def pruefe_eintraege(register: dict[str, Any]) -> list[Verstoss]:
    """Jeder Eintrag einzeln — und die Kennungen gegeneinander."""
    verstoesse: list[Verstoss] = []
    eintraege = register.get("claims") or []
    # FORM VOR INHALT: Ist `claims` keine Liste, hat der Kopf das bereits
    # gemeldet. Hier weiterzulaufen hiesse, ueber die Schluessel eines Mappings
    # zu iterieren und mit einem Traceback statt einem Verstoss zu enden — und
    # ein Verstoss, der wie ein Programmfehler aussieht, wird als Programmfehler
    # behandelt, nicht als Register-Mangel.
    if not isinstance(eintraege, list):
        return verstoesse
    stand = str(register.get("stand", ""))
    gesehen: set[str] = set()

    for i, e in enumerate(eintraege):
        if not isinstance(e, dict):
            verstoesse.append(Verstoss(f"Eintrag {i + 1}", "ist kein Mapping mit Feldern"))
            continue
        kennung = str(e.get("id") or f"Eintrag {i + 1} ohne Kennung")

        if not ID_MUSTER.match(str(e.get("id", ""))):
            verstoesse.append(Verstoss(kennung, "Kennung folgt nicht dem Muster C-<drei Ziffern>"))
        # Eine doppelte Kennung ist der schlimmste Fall: Zwei Aussagen unter
        # einem Namen, und jede Fundstelle zeigt auf beide.
        elif str(e["id"]) in gesehen:
            verstoesse.append(Verstoss(kennung, "Kennung ist doppelt vergeben"))
        else:
            gesehen.add(str(e["id"]))

        verstoesse += (
            _pflichtfelder(kennung, e) + _wertebereiche(kennung, e, stand) + _ueberholt(kennung, e)
        )

    return verstoesse


def pruefe_ansicht(register: dict[str, Any], roh_ansicht: str) -> list[Verstoss]:
    """Sagt die erzeugte Ansicht dasselbe wie das Register?

    Der Fall, gegen den das gebaut ist: Eintrag geändert, `claims render` vergessen.
    Die Ansicht liegt im öffentlichen Repository und wird gelesen wie eine Quelle.
    """
    # KEINE Vereinheitlichung der Zeilenenden: Jeder Vergleich hier ist
    # einzeilig (Stand-Zeile, Kennungen ueber einen Ausdruck, Aussage als
    # Teilzeichenkette), und eine Aussage kann keinen Umbruch tragen — sie steht
    # in einer Tabellenzeile. Eine Umwandlung waere hier eine Zusicherung ohne
    # Wirkung; die Mutationsprobe vom 07.09.2026 hat genau das gezeigt: Beim
    # Entfernen blieb kein Test rot.
    verstoesse: list[Verstoss] = []
    roh_eintraege = register.get("claims") or []
    if not isinstance(roh_eintraege, list):
        return verstoesse  # die Form meldet der Kopf; hier gaebe es nur einen Traceback
    eintraege = [e for e in roh_eintraege if isinstance(e, dict)]
    ansicht = roh_ansicht
    zeilen = ansicht.splitlines()

    # ZEILENGEBUNDEN: Gemeint ist die Kopfzeile `Stand: <datum>` — nicht ein
    # Vorkommen des Teilstrings in einer Prosa-Zelle. Und die Aussage gehoert
    # in die Tabellenzeile IHRER Kennung: Steht sie in einer fremden Zeile, ist
    # die eigene veraltet, und eine Suche ueber die ganze Ansicht meldete Drift
    # als synchron. Beide Stellen am 07.09.2026 im Review gefunden und am Code
    # bestaetigt.
    stand = str(register.get("stand", ""))
    if stand and not any(z.strip() == f"Stand: {stand}" for z in zeilen):
        verstoesse.append(Verstoss("CLAIMS.md", f"Stand-Zeile fehlt oder nennt nicht {stand}"))

    im_register = {str(e.get("id")) for e in eintraege if e.get("id")}
    in_ansicht = set(re.findall(r"\|\s*(C-\d{3})\s*\|", ansicht))

    for fehlend in sorted(im_register - in_ansicht):
        verstoesse.append(
            Verstoss("CLAIMS.md", f"{fehlend} steht im Register, aber nicht in der Ansicht")
        )
    for zuviel in sorted(in_ansicht - im_register):
        verstoesse.append(
            Verstoss("CLAIMS.md", f"{zuviel} steht in der Ansicht, aber nicht im Register")
        )

    for e in eintraege:
        kennung = str(e.get("id", ""))
        aussage = str(e.get("aussage", ""))
        if not aussage or kennung not in in_ansicht:
            continue  # ohne eigene Zeile ist der Fall oben schon gemeldet
        eigene_zeile = next(
            (z for z in zeilen if re.match(rf"\|\s*{re.escape(kennung)}\s*\|", z)), ""
        )
        if aussage not in eigene_zeile:
            verstoesse.append(
                Verstoss(
                    "CLAIMS.md",
                    f"Aussage von {kennung} steht nicht in ihrer Zeile der Ansicht — neu erzeugen",
                )
            )

    return verstoesse


def main() -> int:
    if not REGISTER.exists():
        print(f"❌ Register nicht gefunden: {REGISTER}")
        return 1
    if not ANSICHT.exists():
        print(f"❌ Ansicht nicht gefunden: {ANSICHT}")
        return 1

    roh = yaml.safe_load(REGISTER.read_text(encoding="utf-8"))
    if not isinstance(roh, dict):
        print("❌ claims.yaml enthält keine Abbildung")
        return 1

    verstoesse = (
        pruefe_kopf(roh)
        + pruefe_eintraege(roh)
        + pruefe_ansicht(roh, ANSICHT.read_text(encoding="utf-8"))
    )

    if verstoesse:
        print(f"\n{len(verstoesse)} Beanstandung(en) am Aussagen-Register:\n")
        for v in verstoesse:
            print(v)
        print(
            "\n📋 Struktur oder Ansicht stimmen nicht. `claims validate` und `claims render` fahren."
        )
        return 1

    anzahl = len(roh.get("claims") or [])
    print(
        f"✅ Register in Ordnung: {anzahl} Einträge, Ansicht deckungsgleich (Stand {roh.get('stand')})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
