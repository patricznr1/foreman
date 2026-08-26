#!/usr/bin/env python3
"""
check_compliance.py — Prueft die fuenf Traceability-Gates, die SoA-Konsistenz, den
Geltungsbereich, die Rechtsgrundlagen, die Verweisintegritaet des VVT und die
Aktualitaet der Quellenpruefung.

    python3 scripts/check_compliance.py
    python3 scripts/check_compliance.py --strict
    python3 scripts/check_compliance.py --junit evidence/junit.xml --json-out evidence/check.json

DIE FUENF GATES
    Gate 1  jede requirements[].id hat mindestens einen tests[]-Eintrag
    Gate 2  jeder artifacts[].path existiert im Repo
    Gate 3  jeder automatisierte tests[].path erscheint im JUnit-Report als bestanden
    Gate 4  jede covers[].ref existiert im Katalog des jeweiligen Regimes
    Gate 5  jedes SoA-Control mit anwendbar: true hat mindestens eine Anforderung

Gate 5 ist der eigentliche Waechter. Die Gates 1-4 pruefen, ob das Vorhandene in
sich stimmig ist. Nur Gate 5 prueft, ob etwas FEHLT - und zwar in der Richtung,
in die der Auditor fragt: vom Control zur Anforderung. Gate 5 ist deshalb immer
ein Fehler und wird nie zur Warnung degradiert.

GELESENE ARTEFAKTE
    compliance/traceability.yaml     Pflicht  Gates 1-5
    compliance/soa.yaml              Pflicht  SoA-Konsistenz, Gate 5
    compliance/scope.yaml            offen    Gate G1 der Gate-Checkliste
    compliance/retention-policy.yaml offen    Gate G2, Rechtsgrundlagen
    compliance/ropa.yaml             offen    Gate G2, Verweisintegritaet
    compliance/quellenpruefung.yaml  offen    Gate G5, Aktualitaet
    Fehlt eines der als "offen" gefuehrten Artefakte, ist das eine Warnung und
    mit --strict ein Fehler - nicht stillschweigend nichts.
    Nicht gelesen werden access-model.yaml, supplier-register.yaml und
    risk-register.yaml; ihre Pruefungen sind in references/07-artefakte.md
    beschrieben und hier bewusst noch nicht implementiert.

PLATZHALTER
    Werte in spitzen Klammern (<...>) gelten als noch nicht ausgefuellt:
    im Normalbetrieb WARNUNG, mit --strict FEHLER. Das trennt "Vorlage noch nicht
    befuellt" von "Verweis kaputt" - zwei Zustaende, die man nicht verwechseln darf.
    Erkannt wird nur ein vollstaendiges Klammerpaar mit Inhalt; Vergleichsoperatoren
    wie ">= P10Y" in regeln[].regel sind keine Platzhalter (siehe ist_platzhalter).

EXIT-CODES
    0   keine Fehler (im Normalbetrieb koennen Warnungen offen sein)
    1   mindestens ein Compliance-Fehler
    2   Aufruf- oder Dateifehler (fehlende Pflichtdatei, kaputtes YAML)

ABHAENGIGKEITEN
    Nur PyYAML.  pip install pyyaml

GxP-HINWEIS
    Dieses Skript ist eigene Gate-Logik und damit GAMP-5-Kategorie 5. Auch ein
    kurzes Gate braucht einen vollstaendigen SDLC. Die zugehoerigen Tests liegen
    in tests/test_check_compliance.py und laufen in der Pipeline mit.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as fehler:  # pragma: no cover - Umgebungsproblem, kein Compliance-Fehler
    sys.stderr.write("FEHLER: PyYAML fehlt. Installation:  pip install pyyaml\n")
    raise SystemExit(2) from fehler

VERSION = "1.0.0"

# =============================================================================
# Kataloge
# =============================================================================

REGIME = ("AIACT", "GDPR", "ISO27001", "21CFR11")


def iso27001_katalog() -> frozenset[str]:
    """Die 93 Controls aus ISO/IEC 27001:2022 Anhang A.

    A.5.1-A.5.37 (37 organisatorische), A.6.1-A.6.8 (8 personenbezogene),
    A.7.1-A.7.14 (14 physische), A.8.1-A.8.34 (34 technologische) = 93.
    Die Titel stehen in references/04-iso-27001.md; hier sind nur die Kennungen
    noetig, weil das SoA die Titel fuehrt.
    """
    kennungen: list[str] = []
    for praefix, anzahl in (("A.5", 37), ("A.6", 8), ("A.7", 14), ("A.8", 34)):
        kennungen.extend(f"{praefix}.{n}" for n in range(1, anzahl + 1))
    return frozenset(kennungen)


ISO27001_CONTROLS = iso27001_katalog()

# DSGVO: Art. 1 bis Art. 99, optional mit Absatz-/Buchstabenzusatz.
_RE_GDPR = re.compile(r"^Art\.(\d{1,2})(\(.+\))?$")
_GDPR_MAX_ARTIKEL = 99

# AI Act: Art. 1 bis Art. 113, dazu die Anhaenge I bis XIII.
_RE_AIACT_ARTIKEL = re.compile(r"^Art\.(\d{1,3})(\(.+\))?$")
_RE_AIACT_ANHANG = re.compile(r"^Annex\.(I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII)$")
_AIACT_MAX_ARTIKEL = 113

# 21 CFR Part 11: nur die tatsaechlich existierenden Abschnitte.
_RE_CFR = re.compile(r"^(11\.\d{1,3})((?:\([a-z0-9]+\))*)$")
_CFR_ABSCHNITTE = frozenset(
    {"11.1", "11.2", "11.3", "11.10", "11.30", "11.50", "11.70", "11.100", "11.200", "11.300"}
)

# Rechtsgrundlagen: Drittstaatsrecht traegt Art. 17(3)(b) und Art. 6(1)(c) DSGVO nicht.
_RE_DRITTSTAATSRECHT = re.compile(
    r"\b(21\s*CFR|21CFR|CFR\s*Part|Part\s*11|FDA|HIPAA|CCPA|U\.?S\.?\s*Code)\b",
    re.IGNORECASE,
)

# ISO-Datum JJJJ-MM-TT. Die Kalenderpruefung macht date.fromisoformat().
_RE_ISO_DATUM = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# Platzhalter: ein vollstaendiges Paar spitzer Klammern mit Inhalt, der nicht mit
# einem Leerzeichen beginnt - also <Systemname>, aber nicht "frist < P30D".
_RE_PLATZHALTER = re.compile(r"<[^<>\s][^<>]*>")
# Vergleichsausdruck am Anfang oder Ende des Wertes: ">= P10Y", "> 0", "< 5".
_RE_VERGLEICH = re.compile(r"^\s*(>=|<=|>|<)\s")

# Pflichtfelder eines Eintrags in quellenpruefung.yaml (references/11-quellen.md).
QUELLEN_FELDER = (
    "datum",
    "geprueft_von",
    "gegenstand",
    "quelle",
    "ergebnis",
    "aenderung_gegenueber_vorstand",
    "folge",
)
# Jaehrlich die vollstaendige Neupruefung - aelter darf der juengste Eintrag nicht sein.
QUELLEN_MAX_ALTER_TAGE = 365

UMSETZUNGSSTAENDE = ("nicht_umgesetzt", "teilweise", "umgesetzt")
# Diese Umsetzungsstaende sind eine NACHWEISAUSSAGE: Sie behaupten, dass etwas
# geprueft wurde. Sie brauchen deshalb ein Pruefdatum und eine Geltungsbereichsnotiz.
NACHWEISAUSSAGE = ("umgesetzt", "teilweise")
TEST_TYPEN = ("automated", "manual", "vendor")
VERIFIKATIONEN = ("IQ", "OQ", "PQ", "review", "inspection")
STATUS_WERTE = ("geplant", "in_arbeit", "implemented", "verifiziert")
OUT_OF_SCOPE = "OUT_OF_SCOPE_REPO"


# =============================================================================
# Befunde
# =============================================================================

FEHLER = "FEHLER"
WARNUNG = "WARNUNG"
INFO = "INFO"


@dataclass
class Befund:
    stufe: str
    pruefung: str
    meldung: str
    ort: str = ""

    def als_text(self) -> str:
        ort = f" [{self.ort}]" if self.ort else ""
        return f"{self.stufe:<8} {self.pruefung:<22} {self.meldung}{ort}"


@dataclass
class Ergebnis:
    befunde: list[Befund] = field(default_factory=list)
    strict: bool = False
    abbruch: bool = False  # Datei-/Aufruffehler -> Exit 2

    # -- Erfassung ---------------------------------------------------------
    def fehler(self, pruefung: str, meldung: str, ort: str = "") -> None:
        self.befunde.append(Befund(FEHLER, pruefung, meldung, ort))

    def warnung(self, pruefung: str, meldung: str, ort: str = "") -> None:
        self.befunde.append(Befund(WARNUNG, pruefung, meldung, ort))

    def info(self, pruefung: str, meldung: str, ort: str = "") -> None:
        self.befunde.append(Befund(INFO, pruefung, meldung, ort))

    def offen(self, pruefung: str, meldung: str, ort: str = "") -> None:
        """Offener Punkt: Warnung, mit --strict Fehler.

        Fuer alles, was noch nicht erledigt, aber auch nicht kaputt ist:
        fehlendes Pruefdatum, fehlender Verweis, noch nicht angelegte Datei.
        """
        stufe = FEHLER if self.strict else WARNUNG
        self.befunde.append(Befund(stufe, pruefung, meldung, ort))

    def platzhalter(self, pruefung: str, meldung: str, ort: str = "") -> None:
        """Nicht ausgefuellte Vorlage: Warnung, mit --strict Fehler."""
        self.offen(pruefung, meldung, ort)

    # -- Auswertung --------------------------------------------------------
    @property
    def fehlerliste(self) -> list[Befund]:
        return [b for b in self.befunde if b.stufe == FEHLER]

    @property
    def warnungsliste(self) -> list[Befund]:
        return [b for b in self.befunde if b.stufe == WARNUNG]

    def hat_fehler_in(self, pruefung: str) -> bool:
        return any(b.stufe == FEHLER and b.pruefung == pruefung for b in self.befunde)

    def meldungen_von(self, pruefung: str) -> list[str]:
        return [b.meldung for b in self.befunde if b.pruefung == pruefung]

    @property
    def exit_code(self) -> int:
        if self.abbruch:
            return 2
        return 1 if self.fehlerliste else 0


# =============================================================================
# Hilfsfunktionen
# =============================================================================


def ist_platzhalter(wert: Any) -> bool:
    """True, wenn der Wert eine noch nicht ausgefuellte Vorlage ist (<...>).

    Erkannt wird ein VOLLSTAENDIGES Klammerpaar mit Inhalt: <Systemname>,
    <JJJJ-MM-TT>, "Repository <org/repo> als Teil des ISMS".

    NICHT erkannt werden Vergleichsoperatoren. In regeln[].regel stehen legitime
    Ausdruecke wie ">= P10Y" oder "llm.retention_tage > 0"; ein einzelnes < oder >
    als Vorkommen zu werten, wuerde diese Regeln als unbefuellte Vorlage melden und
    den Befund damit wertlos machen. Ausgeschlossen sind deshalb:
      - Werte ohne vollstaendiges Paar (">= P10Y", "> 0", "< 5"),
      - ein "<" oder "<=" mit folgendem Leerzeichen ("frist < P30D"),
    denn ein Platzhalter beginnt unmittelbar nach der oeffnenden Klammer.
    """
    if not isinstance(wert, str):
        return False
    text = wert.strip()
    if not text:
        return False
    if _RE_VERGLEICH.match(text) and not _RE_PLATZHALTER.search(text):
        return False
    return bool(_RE_PLATZHALTER.search(text))


def ist_leer(wert: Any) -> bool:
    return wert is None or (isinstance(wert, str) and not wert.strip())


def als_datum(wert: Any) -> date | None:
    """Liefert das Datum, wenn der Wert ein gueltiges JJJJ-MM-TT ist, sonst None.

    PyYAML liefert ein unquotiertes 2026-08-13 bereits als date-Objekt, ein
    quotiertes "2026-08-13" als Zeichenkette. Beide Schreibweisen sind zulaessig.
    """
    if isinstance(wert, datetime):
        return wert.date()
    if isinstance(wert, date):
        return wert
    if not isinstance(wert, str) or not _RE_ISO_DATUM.match(wert.strip()):
        return None
    try:
        return date.fromisoformat(wert.strip())
    except ValueError:  # z. B. 2026-02-30
        return None


def lade_yaml(
    pfad: Path, ergebnis: Ergebnis, pruefung: str = "Dateien", pflicht: bool = True
) -> Any | None:
    """Laedt eine YAML-Datei.

    pflicht=True   fehlt sie, ist der Lauf nicht durchfuehrbar -> Exit 2.
    pflicht=False  fehlt sie, ist das ein offener Punkt: Warnung, mit --strict
                   Fehler. Ein noch nicht angelegtes Artefakt ist kein kaputtes
                   Artefakt - aber es darf auch nicht stillschweigend fehlen.
    Kaputtes YAML ist in beiden Faellen ein Fehler.
    """
    if not pfad.exists():
        if pflicht:
            ergebnis.fehler("Dateien", f"Pflichtdatei fehlt: {pfad}")
            ergebnis.abbruch = True
        else:
            ergebnis.offen(
                pruefung,
                f"Datei noch nicht angelegt: {pfad.name} - Pruefung uebersprungen",
                pfad.name,
            )
        return None
    try:
        with pfad.open("r", encoding="utf-8") as fh:
            daten = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        ergebnis.fehler(pruefung, f"YAML nicht lesbar: {pfad} ({exc.__class__.__name__})")
        if pflicht:
            ergebnis.abbruch = True
        return None

    # Eine leere Datei ist kein leerer Befund: Sie sieht aus wie ein gepflegtes
    # Artefakt und sagt nichts. Das ist schlechter als eine fehlende Datei.
    if daten is None:
        ergebnis.fehler(pruefung, f"Datei ist leer: {pfad.name}", pfad.name)
        if pflicht:
            ergebnis.abbruch = True
        return None
    return daten


def als_liste(wert: Any) -> list[Any]:
    if wert is None:
        return []
    return wert if isinstance(wert, list) else [wert]


# =============================================================================
# Katalogpruefung (Gate 4)
# =============================================================================


def ref_bekannt(regime: str, ref: str) -> bool:
    """Existiert die Referenz im Katalog des Regimes?"""
    if regime == "ISO27001":
        return ref in ISO27001_CONTROLS

    if regime == "GDPR":
        treffer = _RE_GDPR.match(ref)
        return bool(treffer) and 1 <= int(treffer.group(1)) <= _GDPR_MAX_ARTIKEL

    if regime == "AIACT":
        if _RE_AIACT_ANHANG.match(ref):
            return True
        treffer = _RE_AIACT_ARTIKEL.match(ref)
        return bool(treffer) and 1 <= int(treffer.group(1)) <= _AIACT_MAX_ARTIKEL

    if regime == "21CFR11":
        treffer = _RE_CFR.match(ref)
        return bool(treffer) and treffer.group(1) in _CFR_ABSCHNITTE

    return False


# =============================================================================
# JUnit (Gate 3)
# =============================================================================


def junit_index(pfad: Path) -> tuple[set[str], set[str]]:
    """Liefert (bestandene Kennungen, nicht bestandene Kennungen) aus einem JUnit-XML."""
    bestanden: set[str] = set()
    nicht_bestanden: set[str] = set()
    wurzel = ET.parse(str(pfad)).getroot()
    for fall in wurzel.iter("testcase"):
        name = fall.get("name") or ""
        klasse = fall.get("classname") or ""
        datei = fall.get("file") or ""
        kennungen = {name}
        if datei:
            kennungen.add(f"{datei}::{name}")
        if klasse:
            kennungen.add(f"{klasse}::{name}")
            kennungen.add(f"{klasse}.{name}")
            kennungen.add(f"{klasse.replace('.', '/')}.py::{name}")
        gescheitert = (
            fall.find("failure") is not None
            or fall.find("error") is not None
            or fall.find("skipped") is not None
        )
        (nicht_bestanden if gescheitert else bestanden).update(kennungen)
    return bestanden, nicht_bestanden


# =============================================================================
# Pruefungen
# =============================================================================


def pruefe_traceability_struktur(daten: Any, ergebnis: Ergebnis) -> list[dict]:
    if not isinstance(daten, dict):
        ergebnis.fehler("Struktur", "traceability.yaml ist keine Abbildung")
        ergebnis.abbruch = True
        return []

    schema = daten.get("schema")
    if schema != "trace/v1":
        ergebnis.fehler(
            "Struktur", f"schema muss 'trace/v1' sein, ist: {schema!r}", "traceability.yaml"
        )

    anforderungen = [a for a in als_liste(daten.get("requirements")) if isinstance(a, dict)]
    if not anforderungen:
        ergebnis.fehler("Struktur", "keine requirements[] vorhanden", "traceability.yaml")
        return []

    gesehen: set[str] = set()
    for anf in anforderungen:
        kennung = anf.get("id")
        ort = f"traceability.yaml:{kennung}"
        if ist_leer(kennung):
            ergebnis.fehler("Struktur", "requirement ohne id", "traceability.yaml")
            continue
        if kennung in gesehen:
            ergebnis.fehler("Struktur", f"doppelte requirement-id: {kennung}", ort)
        gesehen.add(kennung)

        if ist_leer(anf.get("title")):
            ergebnis.fehler("Struktur", "title fehlt", ort)

        verifikation = anf.get("verification")
        if verifikation not in VERIFIKATIONEN:
            ergebnis.fehler(
                "Struktur",
                f"verification muss aus {list(VERIFIKATIONEN)} sein, ist: {verifikation!r}",
                ort,
            )

        status = anf.get("status")
        if status not in STATUS_WERTE:
            ergebnis.fehler(
                "Struktur", f"status muss aus {list(STATUS_WERTE)} sein, ist: {status!r}", ort
            )

        for test in als_liste(anf.get("tests")):
            if not isinstance(test, dict):
                ergebnis.fehler("Struktur", "tests[]-Eintrag ist keine Abbildung", ort)
                continue
            typ = test.get("type")
            if typ not in TEST_TYPEN:
                ergebnis.fehler(
                    "Struktur", f"tests[].type muss aus {list(TEST_TYPEN)} sein, ist: {typ!r}", ort
                )
    return anforderungen


def gate1_tests_vorhanden(anforderungen: list[dict], ergebnis: Ergebnis) -> None:
    for anf in anforderungen:
        kennung = anf.get("id", "<ohne id>")
        tests = [t for t in als_liste(anf.get("tests")) if isinstance(t, dict)]
        if not tests:
            ergebnis.fehler(
                "Gate 1",
                f"Anforderung {kennung} hat keinen einzigen Test - eine Anforderung, "
                f"die niemand prueft, ist keine Anforderung",
                f"traceability.yaml:{kennung}",
            )


def gate2_artefakte_existieren(anforderungen: list[dict], wurzel: Path, ergebnis: Ergebnis) -> None:
    for anf in anforderungen:
        kennung = anf.get("id", "<ohne id>")
        ort = f"traceability.yaml:{kennung}"
        artefakte = [a for a in als_liste(anf.get("artifacts")) if isinstance(a, dict)]
        if not artefakte:
            ergebnis.fehler("Gate 2", f"Anforderung {kennung} hat keine artifacts[]", ort)
            continue
        for artefakt in artefakte:
            pfad = artefakt.get("path")
            if ist_leer(pfad):
                ergebnis.fehler("Gate 2", f"{kennung}: artifacts[]-Eintrag ohne path", ort)
                continue
            if ist_platzhalter(pfad):
                ergebnis.platzhalter(
                    "Gate 2", f"{kennung}: Artefaktpfad noch Platzhalter: {pfad}", ort
                )
                continue
            if not (wurzel / pfad).exists():
                ergebnis.fehler(
                    "Gate 2",
                    f"{kennung}: Artefakt existiert nicht: {pfad}",
                    ort,
                )


def gate3_tests_bestanden(
    anforderungen: list[dict], junit_pfad: Path | None, ergebnis: Ergebnis
) -> None:
    if junit_pfad is None:
        ergebnis.platzhalter(
            "Gate 3",
            "uebersprungen: kein JUnit-Report angegeben (--junit). Ohne Testevidenz ist "
            "die Traceability unvollstaendig",
        )
        return
    if not junit_pfad.exists():
        ergebnis.fehler("Gate 3", f"JUnit-Report nicht gefunden: {junit_pfad}")
        return
    try:
        bestanden, nicht_bestanden = junit_index(junit_pfad)
    except ET.ParseError as exc:
        ergebnis.fehler("Gate 3", f"JUnit-Report nicht lesbar: {junit_pfad} ({exc})")
        return

    for anf in anforderungen:
        kennung = anf.get("id", "<ohne id>")
        ort = f"traceability.yaml:{kennung}"
        for test in als_liste(anf.get("tests")):
            if not isinstance(test, dict) or test.get("type") != "automated":
                continue
            pfad = test.get("path")
            if ist_leer(pfad):
                ergebnis.fehler("Gate 3", f"{kennung}: tests[]-Eintrag ohne path", ort)
                continue
            if ist_platzhalter(pfad):
                ergebnis.platzhalter("Gate 3", f"{kennung}: Testpfad noch Platzhalter: {pfad}", ort)
                continue
            if pfad in bestanden:
                continue
            if pfad in nicht_bestanden:
                ergebnis.fehler(
                    "Gate 3", f"{kennung}: Test im JUnit-Report NICHT bestanden: {pfad}", ort
                )
            else:
                ergebnis.fehler(
                    "Gate 3",
                    f"{kennung}: Test kommt im JUnit-Report nicht vor: {pfad} "
                    f"(nicht gelaufen ist nicht bestanden)",
                    ort,
                )


def gate4_referenzen_bekannt(anforderungen: list[dict], ergebnis: Ergebnis) -> set[str]:
    """Prueft covers[] und liefert nebenbei die abgedeckten ISO-Controls fuer Gate 5."""
    iso_abgedeckt: set[str] = set()
    for anf in anforderungen:
        kennung = anf.get("id", "<ohne id>")
        ort = f"traceability.yaml:{kennung}"
        deckungen = [c for c in als_liste(anf.get("covers")) if isinstance(c, dict)]
        if not deckungen:
            ergebnis.fehler(
                "Gate 4", f"{kennung}: covers[] fehlt - Anforderung ohne Regime-Bezug", ort
            )
            continue
        for deckung in deckungen:
            regime = deckung.get("regime")
            ref = deckung.get("ref")
            if regime not in REGIME:
                ergebnis.fehler(
                    "Gate 4",
                    f"{kennung}: unbekanntes Regime {regime!r}, erlaubt sind {list(REGIME)}",
                    ort,
                )
                continue
            if ist_leer(ref):
                ergebnis.fehler("Gate 4", f"{kennung}: covers[]-Eintrag ohne ref", ort)
                continue
            if ist_platzhalter(ref):
                ergebnis.platzhalter("Gate 4", f"{kennung}: Referenz noch Platzhalter: {ref}", ort)
                continue
            if not ref_bekannt(regime, ref):
                ergebnis.fehler(
                    "Gate 4",
                    f"{kennung}: {regime}-Referenz existiert im Katalog nicht: {ref}",
                    ort,
                )
                continue
            if regime == "ISO27001":
                iso_abgedeckt.add(ref)
    return iso_abgedeckt


def pruefe_soa(daten: Any, wurzel: Path, ergebnis: Ergebnis) -> list[tuple[str, str]]:
    """SoA-Konsistenz. Liefert die Liste (control_id, titel) der anwendbaren Controls."""
    anwendbare: list[tuple[str, str]] = []
    if not isinstance(daten, dict):
        ergebnis.fehler("SoA", "soa.yaml ist keine Abbildung")
        ergebnis.abbruch = True
        return anwendbare

    if daten.get("schema") != "soa/v1":
        ergebnis.fehler(
            "SoA", f"schema muss 'soa/v1' sein, ist: {daten.get('schema')!r}", "soa.yaml"
        )

    controls = [c for c in als_liste(daten.get("controls")) if isinstance(c, dict)]
    if not controls:
        ergebnis.fehler("SoA", "keine controls[] vorhanden", "soa.yaml")
        return anwendbare

    gesehen: set[str] = set()
    bewertet: set[str] = set()

    for control in controls:
        kennung = control.get("control_id")
        ort = f"soa.yaml:{kennung}"

        if ist_leer(kennung):
            ergebnis.fehler("SoA", "Control ohne control_id", "soa.yaml")
            continue

        # Keine Duplikate (references/07-artefakte.md, Artefakt 6). Zwei Zeilen zu
        # demselben Control sind zwei Entscheidungen zu derselben Frage - welche
        # gilt, entscheidet dann die Lesereihenfolge, und das ist keine Entscheidung.
        # Ausnahme: noch nicht befuellte Vorlagenzeilen (control_id als Platzhalter)
        # duerfen mehrfach vorkommen - sie behaupten noch nichts.
        if kennung in gesehen:
            if ist_platzhalter(kennung):
                ergebnis.platzhalter(
                    "SoA", f"mehrere unbefuellte Vorlagenzeilen mit control_id {kennung}", ort
                )
            else:
                ergebnis.fehler(
                    "SoA",
                    f"doppelte control_id: {kennung} - zwei Zeilen zu einem Control sind "
                    f"zwei Entscheidungen zu derselben Frage",
                    ort,
                )
            continue
        gesehen.add(kennung)

        if ist_platzhalter(kennung):
            ergebnis.platzhalter("SoA", f"control_id ist Platzhalter: {kennung}", ort)
            continue
        if kennung not in ISO27001_CONTROLS:
            ergebnis.fehler(
                "SoA",
                f"control_id existiert in Anhang A (2022) nicht: {kennung}",
                ort,
            )
            continue

        if ist_leer(control.get("titel")):
            ergebnis.fehler("SoA", f"{kennung}: titel fehlt", ort)

        anwendbar = control.get("anwendbar")
        if ist_platzhalter(anwendbar):
            ergebnis.platzhalter(
                "SoA",
                f"{kennung}: noch nicht bewertet (anwendbar ist Platzhalter). Die vollstaendige "
                f"Controlliste steht in references/04-iso-27001.md",
                ort,
            )
            continue
        if not isinstance(anwendbar, bool):
            ergebnis.fehler(
                "SoA", f"{kennung}: anwendbar muss true oder false sein, ist: {anwendbar!r}", ort
            )
            continue

        bewertet.add(kennung)
        scope_note = control.get("scope_note")

        # OUT_OF_SCOPE_REPO und anwendbar: true schliessen einander aus.
        if isinstance(scope_note, str) and scope_note.strip() == OUT_OF_SCOPE and anwendbar:
            ergebnis.fehler(
                "SoA",
                f"{kennung}: scope_note {OUT_OF_SCOPE} bei anwendbar: true - "
                f"was ausserhalb des Repo-Scopes liegt, kann hier nicht nachgewiesen werden",
                ort,
            )

        # Klausel 6.1.3 d): JEDE Entscheidung braucht eine Begruendung, der
        # AUSSCHLUSS (anwendbar: false) ganz besonders - er ist die Entscheidung,
        # die im Audit erklaert werden muss. Ein Ausschluss ohne Begruendung ist
        # nicht dokumentiert, sondern weggelassen.
        begruendung = control.get("begruendung")
        if ist_leer(begruendung):
            zusatz = (
                " - ein Ausschluss ohne Begruendung ist im Audit nicht verteidigbar"
                if anwendbar is False
                else ""
            )
            ergebnis.fehler(
                "SoA",
                f"{kennung}: begruendung fehlt (Klausel 6.1.3 d verlangt sie fuer JEDE "
                f"Entscheidung){zusatz}",
                ort,
            )
        elif ist_platzhalter(begruendung):
            ergebnis.platzhalter("SoA", f"{kennung}: begruendung ist Platzhalter", ort)

        stand = control.get("umsetzungsstand")
        if ist_platzhalter(stand):
            ergebnis.platzhalter("SoA", f"{kennung}: umsetzungsstand ist Platzhalter", ort)
        elif stand not in UMSETZUNGSSTAENDE:
            ergebnis.fehler(
                "SoA",
                f"{kennung}: umsetzungsstand muss aus {list(UMSETZUNGSSTAENDE)} sein, ist: {stand!r}",
                ort,
            )

        nachweis = control.get("evidence_ref")
        if ist_platzhalter(nachweis):
            ergebnis.platzhalter("SoA", f"{kennung}: evidence_ref ist Platzhalter: {nachweis}", ort)
        elif not ist_leer(nachweis) and not (wurzel / str(nachweis)).exists():
            ergebnis.fehler("SoA", f"{kennung}: evidence_ref existiert nicht: {nachweis}", ort)

        if stand == "umgesetzt" and ist_leer(nachweis):
            ergebnis.fehler(
                "SoA",
                f"{kennung}: umsetzungsstand 'umgesetzt' ohne evidence_ref ist eine Behauptung",
                ort,
            )

        automatisch = control.get("automated_check")
        if automatisch not in (True, False, None) and not ist_platzhalter(automatisch):
            ergebnis.fehler(
                "SoA",
                f"{kennung}: automated_check muss true oder false sein, ist: {automatisch!r}",
                ort,
            )

        # --- Nachweisaussage: checked_at und scope_note ------------------------
        # Wer "umgesetzt" oder "teilweise" schreibt, behauptet einen geprueften
        # Zustand. Diese Behauptung braucht ZWEI Angaben, unabhaengig davon, ob
        # die Pruefung automatisiert laeuft:
        #   checked_at  - WANN wurde das geprueft (ein Nachweis ohne Datum ist
        #                 eine Aussage ueber einen unbekannten Zeitpunkt),
        #   scope_note  - WOFUER gilt der Nachweis (ohne Geltungsbereich laesst
        #                 sich aus einem Teilnachweis ein Gesamtnachweis lesen).
        # Fehlt eines, ist das ein offener Punkt: Warnung, mit --strict Fehler.
        # Bei automated_check: true bleibt das fehlende Datum ein harter Fehler -
        # dort haette die CI es setzen muessen, es fehlt also der Laufnachweis.
        geprueft_am = control.get("checked_at")
        nachweisaussage = anwendbar is True and stand in NACHWEISAUSSAGE

        if automatisch is True:
            if ist_leer(geprueft_am):
                ergebnis.fehler("SoA", f"{kennung}: automated_check: true ohne checked_at", ort)
            elif ist_platzhalter(geprueft_am):
                ergebnis.platzhalter(
                    "SoA", f"{kennung}: automated_check: true, checked_at ist Platzhalter", ort
                )
            elif als_datum(geprueft_am) is None:
                ergebnis.fehler(
                    "SoA",
                    f"{kennung}: checked_at ist kein gueltiges Datum (JJJJ-MM-TT): {geprueft_am!r}",
                    ort,
                )
        elif nachweisaussage:
            if ist_leer(geprueft_am):
                ergebnis.offen(
                    "SoA",
                    f"{kennung}: umsetzungsstand '{stand}' ohne checked_at - eine "
                    f"Nachweisaussage ohne Pruefdatum ist eine Behauptung ueber einen "
                    f"unbekannten Zeitpunkt",
                    ort,
                )
            elif ist_platzhalter(geprueft_am):
                ergebnis.platzhalter(
                    "SoA",
                    f"{kennung}: umsetzungsstand '{stand}', checked_at ist noch "
                    f"Platzhalter: {geprueft_am}",
                    ort,
                )
            elif als_datum(geprueft_am) is None:
                ergebnis.fehler(
                    "SoA",
                    f"{kennung}: checked_at ist kein gueltiges Datum (JJJJ-MM-TT): {geprueft_am!r}",
                    ort,
                )

        if nachweisaussage:
            if ist_leer(scope_note):
                ergebnis.offen(
                    "SoA",
                    f"{kennung}: umsetzungsstand '{stand}' ohne scope_note - ohne "
                    f"Geltungsbereich ist unklar, wofuer der Nachweis gilt",
                    ort,
                )
            elif ist_platzhalter(scope_note):
                ergebnis.platzhalter(
                    "SoA",
                    f"{kennung}: umsetzungsstand '{stand}', scope_note ist noch Platzhalter",
                    ort,
                )

        if anwendbar:
            anwendbare.append((kennung, str(control.get("titel", ""))))

    fehlend = len(ISO27001_CONTROLS) - len(bewertet)
    if fehlend > 0:
        ergebnis.platzhalter(
            "SoA",
            f"{fehlend} von {len(ISO27001_CONTROLS)} Anhang-A-Controls sind noch nicht bewertet. "
            f"Vollstaendige Liste: references/04-iso-27001.md",
            "soa.yaml",
        )

    return anwendbare


def gate5_jedes_control_hat_anforderung(
    anwendbare: Iterable[tuple[str, str]], iso_abgedeckt: set[str], ergebnis: Ergebnis
) -> None:
    """Der eigentliche Waechter: prueft, was FEHLT. Nie eine Warnung."""
    for kennung, titel in anwendbare:
        if kennung not in iso_abgedeckt:
            zusatz = f" ({titel})" if titel else ""
            ergebnis.fehler(
                "Gate 5",
                f"Control {kennung}{zusatz} ist anwendbar, aber keine einzige Anforderung "
                f"in traceability.yaml deckt es ab",
                f"soa.yaml:{kennung}",
            )


def pruefe_scope(daten: Any, ergebnis: Ergebnis) -> None:
    """Gate G1 (Geltungsbereich) - liest compliance/scope.yaml.

    Geprueft wird, ob fuer JEDES der vier Regime eine Einstufung vorliegt und ob
    diese Einstufung traegt:
      - alle vier Regime aus REGIME sind vorhanden, keines fehlt (ein fehlendes
        Regime ist keine Nicht-Anwendbarkeit, sondern eine offene Frage),
      - je Regime ist "greift" (bzw. das im Skelett gefuehrte Synonym
        "anwendbar") gesetzt und liegt im Wertebereich true | false | teilweise,
      - bei true oder teilweise sind "begruendung" und "tragende_bedingung"
        ausgefuellt - ohne tragende Bedingung gibt es keinen Kipppunkt und damit
        keinen Fruehwarnindikator (references/01-scoping.md),
      - "eingestuft_am" und "naechste_pruefung" sind gueltige Daten und die
        Wiedervorlage liegt NACH der Einstufung.

    Feldnamen: references/01-scoping.md fuehrt "greift", das Skelett fuehrt
    historisch "anwendbar". Beide werden akzeptiert, damit keine der beiden
    Schreibweisen stillschweigend ungeprueft bleibt.
    """
    if not isinstance(daten, dict):
        ergebnis.fehler("Scope", "scope.yaml ist keine Abbildung", "scope.yaml")
        return

    if daten.get("schema") != "scope/v1":
        ergebnis.fehler(
            "Scope", f"schema muss 'scope/v1' sein, ist: {daten.get('schema')!r}", "scope.yaml"
        )

    eintraege = [r for r in als_liste(daten.get("regime")) if isinstance(r, dict)]
    if not eintraege:
        ergebnis.fehler("Scope", "keine regime[] vorhanden", "scope.yaml")
        return

    gesehen: set[str] = set()
    for eintrag in eintraege:
        kennung = str(eintrag.get("id") or "").strip()
        ort = f"scope.yaml:{kennung or '<ohne id>'}"

        if not kennung:
            ergebnis.fehler("Scope", "regime[]-Eintrag ohne id", "scope.yaml")
            continue
        if kennung not in REGIME:
            ergebnis.fehler(
                "Scope", f"unbekanntes Regime {kennung!r}, erlaubt sind {list(REGIME)}", ort
            )
            continue
        if kennung in gesehen:
            ergebnis.fehler("Scope", f"doppelte Regime-Einstufung: {kennung}", ort)
            continue
        gesehen.add(kennung)

        # -- greift / anwendbar ------------------------------------------------
        if "greift" in eintrag:
            wert = eintrag["greift"]
        elif "anwendbar" in eintrag:
            wert = eintrag["anwendbar"]
        else:
            ergebnis.fehler(
                "Scope",
                f"{kennung}: greift fehlt - ein Regime ohne Einstufung ist eine offene "
                f"Frage, keine Nicht-Anwendbarkeit",
                ort,
            )
            wert = None

        trifft_zu: bool | None = None
        if ist_platzhalter(wert):
            ergebnis.platzhalter("Scope", f"{kennung}: greift ist noch Platzhalter: {wert}", ort)
        elif wert is True or wert == "teilweise":
            trifft_zu = True
        elif wert is False:
            trifft_zu = False
        elif wert is not None:
            ergebnis.fehler(
                "Scope",
                f"{kennung}: greift muss true, false oder 'teilweise' sein, ist: {wert!r}",
                ort,
            )

        # -- Begruendung und tragende Bedingung --------------------------------
        # Ein "greift: false" wird genauso begruendet wie ein "true"; die tragende
        # Bedingung verlangen wir nur dort, wo das Regime tatsaechlich greift.
        pflichtfelder = ["begruendung"]
        if trifft_zu:
            pflichtfelder.append("tragende_bedingung")
        for feld in pflichtfelder:
            inhalt = eintrag.get(feld)
            if ist_leer(inhalt):
                ergebnis.fehler("Scope", f"{kennung}: {feld} fehlt", ort)
            elif ist_platzhalter(inhalt):
                ergebnis.platzhalter("Scope", f"{kennung}: {feld} ist noch Platzhalter", ort)

        # -- Daten -------------------------------------------------------------
        daten_werte: dict[str, date | None] = {}
        for feld in ("eingestuft_am", "naechste_pruefung"):
            inhalt = eintrag.get(feld)
            daten_werte[feld] = None
            if ist_leer(inhalt):
                ergebnis.fehler(
                    "Scope",
                    f"{kennung}: {feld} fehlt - eine Einstufung ohne Datum ist eine "
                    f"Meinung, kein Dokument",
                    ort,
                )
            elif ist_platzhalter(inhalt):
                ergebnis.platzhalter("Scope", f"{kennung}: {feld} ist noch Platzhalter", ort)
            else:
                datum = als_datum(inhalt)
                if datum is None:
                    ergebnis.fehler(
                        "Scope",
                        f"{kennung}: {feld} ist kein gueltiges Datum (JJJJ-MM-TT): {inhalt!r}",
                        ort,
                    )
                daten_werte[feld] = datum

        eingestuft = daten_werte["eingestuft_am"]
        naechste = daten_werte["naechste_pruefung"]
        if eingestuft and naechste and naechste <= eingestuft:
            ergebnis.fehler(
                "Scope",
                f"{kennung}: naechste_pruefung ({naechste}) liegt nicht nach "
                f"eingestuft_am ({eingestuft}) - eine Wiedervorlage in der Vergangenheit "
                f"ist keine Wiedervorlage",
                ort,
            )

    for fehlend in (r for r in REGIME if r not in gesehen):
        ergebnis.fehler(
            "Scope",
            f"Regime {fehlend} fehlt in scope.yaml - jedes der vier Regime wird "
            f"ausdruecklich als greifend oder nicht greifend eingestuft",
            "scope.yaml",
        )


def _erstes_feld(eintrag: dict, *namen: str) -> tuple[str, Any]:
    """Liefert (Feldname, Wert) des ersten vorhandenen Feldes aus namen."""
    for name in namen:
        if name in eintrag:
            return name, eintrag[name]
    return namen[0], None


def pruefe_ropa(daten: Any, retention_klassen: set[str] | None, ergebnis: Ergebnis) -> None:
    """Gate G2 (Rechtsgrundlagen), Teil ropa.yaml - Art. 30 DSGVO.

    Je Verarbeitung: Zweck (Art. 30(1)(b)), Rechtsgrundlage und Loeschfrist
    (Art. 30(1)(f)). Die Loeschfrist wird NICHT hier ausgeschrieben, sondern
    verweist auf eine Datenklasse in retention-policy.yaml - sonst entstehen zwei
    Wahrheiten. Genau diese Verweisintegritaet wird geprueft: ein Verweis auf eine
    nicht existierende Klasse ist ein offener Punkt (Warnung, mit --strict Fehler).

    Feldnamen: Singular und Plural werden beide akzeptiert (zweck/zwecke,
    rechtsgrundlage/rechtsgrundlage_art6, loeschfrist/loeschfristen).
    """
    if not isinstance(daten, dict):
        ergebnis.fehler("ROPA", "ropa.yaml ist keine Abbildung", "ropa.yaml")
        return

    if daten.get("schema") != "ropa/v1":
        ergebnis.fehler(
            "ROPA", f"schema muss 'ropa/v1' sein, ist: {daten.get('schema')!r}", "ropa.yaml"
        )

    eintraege = [v for v in als_liste(daten.get("verarbeitungen")) if isinstance(v, dict)]
    if not eintraege:
        ergebnis.fehler("ROPA", "keine verarbeitungen[] vorhanden", "ropa.yaml")
        return

    if retention_klassen is None:
        ergebnis.offen(
            "ROPA",
            "Verweisintegritaet der Loeschfristen nicht pruefbar - retention-policy.yaml "
            "fehlt oder ist nicht lesbar",
            "ropa.yaml",
        )

    for nummer, eintrag in enumerate(eintraege, start=1):
        kennung = str(eintrag.get("id") or f"#{nummer}")
        ort = f"ropa.yaml:{kennung}"

        # -- Art. 30(1)(b): Zweck ---------------------------------------------
        feld, wert = _erstes_feld(eintrag, "zwecke", "zweck")
        zwecke = [z for z in als_liste(wert) if not ist_leer(z)]
        if not zwecke:
            ergebnis.fehler(
                "ROPA",
                f"{kennung}: {feld} fehlt - Art. 30(1)(b) verlangt die Zwecke der Verarbeitung",
                ort,
            )
        for zweck in zwecke:
            if ist_platzhalter(zweck):
                ergebnis.platzhalter(
                    "ROPA", f"{kennung}: {feld} ist noch Platzhalter: {zweck}", ort
                )

        # -- Rechtsgrundlage ---------------------------------------------------
        feld, wert = _erstes_feld(eintrag, "rechtsgrundlage_art6", "rechtsgrundlage")
        normen: list[Any] = []
        for posten in als_liste(wert):
            normen.append(posten.get("norm") if isinstance(posten, dict) else posten)
        if not [n for n in normen if not ist_leer(n)]:
            ergebnis.fehler(
                "ROPA",
                f"{kennung}: {feld} fehlt - eine Verarbeitung ohne Rechtsgrundlage je Zweck "
                f"ist nach Art. 6(1) DSGVO unzulaessig",
                ort,
            )
        for norm in normen:
            if ist_platzhalter(norm):
                ergebnis.platzhalter("ROPA", f"{kennung}: {feld} ist noch Platzhalter: {norm}", ort)

        # -- Art. 30(1)(f): Loeschfrist und Verweisintegritaet ------------------
        feld, wert = _erstes_feld(eintrag, "loeschfristen", "loeschfrist")
        klassen: list[Any] = []
        for posten in als_liste(wert):
            klassen.append(posten.get("klasse") if isinstance(posten, dict) else posten)
        klassen = [k for k in klassen if not ist_leer(k)]
        if not klassen:
            ergebnis.fehler(
                "ROPA",
                f"{kennung}: {feld} fehlt - Art. 30(1)(f) verlangt die Loeschfristen; "
                f"sie werden als Verweis auf eine Klasse in retention-policy.yaml gefuehrt",
                ort,
            )
        for klasse in klassen:
            if ist_platzhalter(klasse):
                ergebnis.platzhalter(
                    "ROPA", f"{kennung}: {feld}-Verweis ist noch Platzhalter: {klasse}", ort
                )
                continue
            if retention_klassen is None:
                continue
            if str(klasse) not in retention_klassen:
                ergebnis.offen(
                    "ROPA",
                    f"{kennung}: {feld} verweist auf die Datenklasse '{klasse}', die es in "
                    f"retention-policy.yaml nicht gibt - ein Verweis ins Leere ist keine Frist",
                    ort,
                )


def pruefe_retention(daten: Any, ergebnis: Ergebnis) -> set[str]:
    """Zusatzpruefung: Rechtsgrundlagen der Aufbewahrungsfristen.

    Geprueft werden ausschliesslich die Felder rechtsgrundlage.rechtsakt und
    rechtsgrundlage.norm - dort steht die Rechtsgrundlage. Das Feld begruendung
    darf 21 CFR erwaehnen (und sollte es sogar, zur Abgrenzung).

    Rueckgabe: die Namen der Datenklassen. Sie sind das Ziel der Verweise aus
    ropa.yaml und werden dort auf Verweisintegritaet geprueft.
    """
    namen: set[str] = set()
    if not isinstance(daten, dict):
        ergebnis.fehler("Retention", "retention-policy.yaml ist keine Abbildung")
        return namen

    klassen = [k for k in als_liste(daten.get("datenklassen")) if isinstance(k, dict)]
    if not klassen:
        ergebnis.fehler("Retention", "keine datenklassen[] vorhanden", "retention-policy.yaml")
        return namen

    for klasse in klassen:
        name = klasse.get("klasse", "<ohne name>")
        if not ist_leer(klasse.get("klasse")):
            namen.add(str(klasse.get("klasse")))
        ort = f"retention-policy.yaml:{name}"

        frist = klasse.get("frist")
        if ist_leer(frist):
            ergebnis.fehler(
                "Retention",
                f"{name}: frist fehlt - ohne Frist ist Art. 5(1)(e) DSGVO verletzt",
                ort,
            )
        elif ist_platzhalter(frist):
            ergebnis.platzhalter("Retention", f"{name}: frist ist Platzhalter: {frist}", ort)

        grundlage = klasse.get("rechtsgrundlage")
        if not isinstance(grundlage, dict):
            ergebnis.fehler("Retention", f"{name}: rechtsgrundlage fehlt oder ist kein Block", ort)
            continue

        for feld in ("rechtsakt", "norm"):
            wert = grundlage.get(feld)
            if ist_leer(wert):
                ergebnis.fehler(
                    "Retention",
                    f"{name}: rechtsgrundlage.{feld} fehlt - eine Frist ohne benannten "
                    f"Rechtsakt ist ein Erfahrungswert, keine Rechtsgrundlage",
                    ort,
                )
                continue
            if ist_platzhalter(wert):
                ergebnis.platzhalter(
                    "Retention", f"{name}: rechtsgrundlage.{feld} ist Platzhalter", ort
                )
                continue
            treffer = _RE_DRITTSTAATSRECHT.search(str(wert))
            if treffer:
                ergebnis.fehler(
                    "Retention",
                    f"{name}: rechtsgrundlage.{feld} verweist auf Drittstaatsrecht "
                    f"({treffer.group(0)}). Art. 17(3)(b) und Art. 6(1)(c) DSGVO verlangen "
                    f"Recht der Union oder der Mitgliedstaaten. 21 CFR Part 11 ist die "
                    f"technische Ausgestaltung, nicht die Rechtsgrundlage - unionsrechtlichen "
                    f"Zwilling benennen",
                    ort,
                )

        if ist_leer(klasse.get("verantwortlicher")):
            ergebnis.fehler("Retention", f"{name}: verantwortlicher fehlt", ort)
        if ist_leer(klasse.get("loeschverfahren")):
            ergebnis.fehler("Retention", f"{name}: loeschverfahren fehlt", ort)

    return namen


def pruefe_quellenpruefung(daten: Any, ergebnis: Ergebnis, heute: date | None = None) -> None:
    """Gate G5 (Aktualitaet) - liest compliance/quellenpruefung.yaml.

    Leichte Pruefung, weil der Inhalt nicht maschinell pruefbar ist: ob eine Frist
    stimmt, sieht nur ein Mensch in der Primaerquelle. Pruefbar ist dagegen, OB
    geprueft wurde und ob das Protokoll vollstaendig ist:
      - jeder Eintrag hat alle sieben Pflichtfelder,
      - "folge" ist nicht leer (ein Protokoll ohne Folge ist unvollstaendig:
        entweder folgt etwas, oder es steht ausdruecklich, dass nichts folgt),
      - der juengste Eintrag ist nicht aelter als 365 Tage.
    Ein zu alter oder fehlender Nachweis ist ein offener Punkt: Warnung, mit
    --strict Fehler.
    """
    heute = heute or date.today()

    if not isinstance(daten, dict):
        ergebnis.fehler(
            "Quellen", "quellenpruefung.yaml ist keine Abbildung", "quellenpruefung.yaml"
        )
        return

    eintraege = [p for p in als_liste(daten.get("pruefungen")) if isinstance(p, dict)]
    if not eintraege:
        ergebnis.fehler("Quellen", "keine pruefungen[] vorhanden", "quellenpruefung.yaml")
        return

    juengstes: date | None = None
    for nummer, eintrag in enumerate(eintraege, start=1):
        gegenstand = eintrag.get("gegenstand")
        brauchbar = not ist_leer(gegenstand) and not ist_platzhalter(gegenstand)
        bezeichner = str(gegenstand) if brauchbar else f"#{nummer}"
        ort = f"quellenpruefung.yaml:#{nummer}"

        for feld in QUELLEN_FELDER:
            wert = eintrag.get(feld)
            if ist_leer(wert):
                if feld == "folge":
                    ergebnis.fehler(
                        "Quellen",
                        f"Eintrag {bezeichner}: folge fehlt - ein Pruefprotokoll ohne Folge "
                        f"ist unvollstaendig: entweder folgt etwas, oder es steht "
                        f"ausdruecklich, dass nichts folgt",
                        ort,
                    )
                else:
                    ergebnis.fehler("Quellen", f"Eintrag {bezeichner}: {feld} fehlt", ort)
            elif ist_platzhalter(wert):
                ergebnis.platzhalter(
                    "Quellen", f"Eintrag {bezeichner}: {feld} ist noch Platzhalter", ort
                )

        rohdatum = eintrag.get("datum")
        if not ist_leer(rohdatum) and not ist_platzhalter(rohdatum):
            datum = als_datum(rohdatum)
            if datum is None:
                ergebnis.fehler(
                    "Quellen",
                    f"Eintrag {bezeichner}: datum ist kein gueltiges Datum (JJJJ-MM-TT): {rohdatum!r}",
                    ort,
                )
            else:
                if datum > heute:
                    ergebnis.fehler(
                        "Quellen",
                        f"Eintrag {bezeichner}: datum liegt in der Zukunft ({datum})",
                        ort,
                    )
                if juengstes is None or datum > juengstes:
                    juengstes = datum

    if juengstes is None:
        ergebnis.offen(
            "Quellen",
            "kein Eintrag mit gueltigem Datum - damit ist keine Aktualitaetspruefung belegt",
            "quellenpruefung.yaml",
        )
        return

    alter = (heute - juengstes).days
    if alter > QUELLEN_MAX_ALTER_TAGE:
        ergebnis.offen(
            "Quellen",
            f"juengste Quellenpruefung ist {alter} Tage alt ({juengstes}), erlaubt sind "
            f"{QUELLEN_MAX_ALTER_TAGE} - Fristen und Zustaendigkeiten altern, das Protokoll "
            f"nicht",
            "quellenpruefung.yaml",
        )


# =============================================================================
# Orchestrierung
# =============================================================================


def pruefe_repo(
    wurzel: Path,
    junit: Path | None = None,
    strict: bool = False,
    heute: date | None = None,
) -> Ergebnis:
    """Fuehrt alle Pruefungen aus und liefert das Ergebnis.

    heute  Stichtag fuer Altersvergleiche (Standard: heutiges Datum). Der
           Parameter existiert, damit die Tests einen festen Stichtag setzen
           koennen - ein Gate, dessen Ergebnis vom Kalender abhaengt, muss
           gegen einen bekannten Kalender pruefbar sein.
    """
    ergebnis = Ergebnis(strict=strict)
    verzeichnis = wurzel / "compliance"

    if not verzeichnis.is_dir():
        ergebnis.fehler("Dateien", f"Verzeichnis fehlt: {verzeichnis}")
        ergebnis.abbruch = True
        return ergebnis

    trace_daten = lade_yaml(verzeichnis / "traceability.yaml", ergebnis)
    soa_daten = lade_yaml(verzeichnis / "soa.yaml", ergebnis)
    if ergebnis.abbruch:
        return ergebnis

    anforderungen = pruefe_traceability_struktur(trace_daten, ergebnis)
    if ergebnis.abbruch:
        return ergebnis

    gate1_tests_vorhanden(anforderungen, ergebnis)
    gate2_artefakte_existieren(anforderungen, wurzel, ergebnis)
    gate3_tests_bestanden(anforderungen, junit, ergebnis)
    iso_abgedeckt = gate4_referenzen_bekannt(anforderungen, ergebnis)

    anwendbare = pruefe_soa(soa_daten, wurzel, ergebnis)
    if ergebnis.abbruch:
        return ergebnis
    gate5_jedes_control_hat_anforderung(anwendbare, iso_abgedeckt, ergebnis)

    # -- Gate G1: Geltungsbereich (scope.yaml) --------------------------------
    scope_daten = lade_yaml(verzeichnis / "scope.yaml", ergebnis, pruefung="Scope", pflicht=False)
    if scope_daten is not None:
        pruefe_scope(scope_daten, ergebnis)

    # -- Gate G2: Rechtsgrundlagen (retention-policy.yaml, ropa.yaml) ---------
    # Reihenfolge ist bindend: Die Datenklassen aus der Retention-Policy sind das
    # Ziel der Loeschfrist-Verweise im VVT.
    retention_klassen: set[str] | None = None
    retention_daten = lade_yaml(
        verzeichnis / "retention-policy.yaml", ergebnis, pruefung="Retention", pflicht=False
    )
    if retention_daten is not None:
        retention_klassen = pruefe_retention(retention_daten, ergebnis)

    ropa_daten = lade_yaml(verzeichnis / "ropa.yaml", ergebnis, pruefung="ROPA", pflicht=False)
    if ropa_daten is not None:
        pruefe_ropa(ropa_daten, retention_klassen, ergebnis)

    # -- Gate G5: Aktualitaet (quellenpruefung.yaml) --------------------------
    quellen_daten = lade_yaml(
        verzeichnis / "quellenpruefung.yaml", ergebnis, pruefung="Quellen", pflicht=False
    )
    if quellen_daten is not None:
        pruefe_quellenpruefung(quellen_daten, ergebnis, heute=heute)

    return ergebnis


# =============================================================================
# Ausgabe
# =============================================================================

_REIHENFOLGE = (
    "Dateien",
    "Struktur",
    "Scope",
    "Gate 1",
    "Gate 2",
    "Gate 3",
    "Gate 4",
    "SoA",
    "Gate 5",
    "ROPA",
    "Retention",
    "Quellen",
)

# Ergebnisblock: Schluessel -> Beschriftung. Die fuenf Gates kommen aus
# _REIHENFOLGE, die uebrigen Pruefungen stehen hier in ihrer Anzeigereihenfolge.
_ERGEBNISZEILEN = (
    ("Scope", "Geltungsbereich (scope.yaml)"),
    ("SoA", "SoA-Konsistenz"),
    ("ROPA", "VVT-Verweisintegritaet (ropa.yaml)"),
    ("Retention", "Retention-Rechtsgrundlagen"),
    ("Quellen", "Aktualitaet (quellenpruefung.yaml)"),
)


def _farbe_aktiv(erzwinge_aus: bool) -> bool:
    if erzwinge_aus or os.environ.get("NO_COLOR"):
        return False
    return sys.stdout.isatty()


def berichte(ergebnis: Ergebnis, wurzel: Path, farbe: bool) -> str:
    rot, gelb, gruen, grau, aus = (
        ("\033[31m", "\033[33m", "\033[32m", "\033[90m", "\033[0m") if farbe else ("",) * 5
    )

    zeilen: list[str] = []
    zeilen.append("=" * 78)
    zeilen.append(f"  Compliance-Pruefung {VERSION}   Wurzel: {wurzel}")
    zeilen.append(
        f"  Modus: {'STRICT (jede Warnung ist ein Fehler)' if ergebnis.strict else 'Normalbetrieb (Platzhalter sind Warnungen)'}"
    )
    zeilen.append("=" * 78)

    gruppen = sorted(
        {b.pruefung for b in ergebnis.befunde},
        key=lambda p: (_REIHENFOLGE.index(p) if p in _REIHENFOLGE else 99, p),
    )
    for gruppe in gruppen:
        befunde = [b for b in ergebnis.befunde if b.pruefung == gruppe]
        anzahl_fehler = sum(1 for b in befunde if b.stufe == FEHLER)
        kopf_farbe = (
            rot if anzahl_fehler else (gelb if any(b.stufe == WARNUNG for b in befunde) else grau)
        )
        zeilen.append("")
        zeilen.append(f"{kopf_farbe}--- {gruppe} ---{aus}")
        for befund in befunde:
            stufenfarbe = {FEHLER: rot, WARNUNG: gelb, INFO: grau}.get(befund.stufe, "")
            ort = f"  [{befund.ort}]" if befund.ort else ""
            zeilen.append(f"  {stufenfarbe}{befund.stufe:<8}{aus} {befund.meldung}{grau}{ort}{aus}")

    def zeile_fuer(schluessel: str, beschriftung: str) -> str:
        befunde = [b for b in ergebnis.befunde if b.pruefung == schluessel]
        if any(b.stufe == FEHLER for b in befunde):
            return f"  {rot}FEHLGESCHLAGEN{aus}  {beschriftung}"
        if any(b.stufe == WARNUNG for b in befunde):
            anzahl = sum(1 for b in befunde if b.stufe == WARNUNG)
            wort = "offener Punkt" if anzahl == 1 else "offene Punkte"
            return f"  {gelb}OFFEN{aus}           {beschriftung}  ({anzahl} {wort})"
        return f"  {gruen}BESTANDEN{aus}       {beschriftung}"

    zeilen.append("")
    zeilen.append("-" * 78)
    for gate in (g for g in _REIHENFOLGE if g.startswith("Gate")):
        zeilen.append(zeile_fuer(gate, gate))
    for schluessel, beschriftung in _ERGEBNISZEILEN:
        zeilen.append(zeile_fuer(schluessel, beschriftung))

    anzahl_fehler = len(ergebnis.fehlerliste)
    anzahl_warnungen = len(ergebnis.warnungsliste)
    zeilen.append("-" * 78)
    if anzahl_fehler:
        zeilen.append(f"  {rot}ERGEBNIS: {anzahl_fehler} Fehler, {anzahl_warnungen} Warnungen{aus}")
    elif anzahl_warnungen:
        zeilen.append(
            f"  {gelb}ERGEBNIS: keine Fehler, {anzahl_warnungen} Warnungen "
            f"(offene Platzhalter - mit --strict werden sie zu Fehlern){aus}"
        )
    else:
        zeilen.append(f"  {gruen}ERGEBNIS: keine Fehler, keine Warnungen{aus}")
    zeilen.append("=" * 78)
    return "\n".join(zeilen)


# =============================================================================
# CLI
# =============================================================================


def baue_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_compliance.py",
        description="Prueft die fuenf Traceability-Gates, die SoA-Konsistenz und die "
        "Rechtsgrundlagen der Retention-Policy.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Exit-Codes: 0 = keine Fehler, 1 = Compliance-Fehler, 2 = Aufruf-/Dateifehler",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repo-Wurzel (Standard: uebergeordnetes Verzeichnis von scripts/)",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Jede Warnung (offener Platzhalter) wird zum Fehler. Fuer den Reifebetrieb.",
    )
    parser.add_argument(
        "--junit",
        type=Path,
        default=None,
        help="JUnit-XML-Report; aktiviert Gate 3. Ohne diese Angabe wird Gate 3 uebersprungen.",
    )
    parser.add_argument(
        "--json-out", type=Path, default=None, help="Befunde zusaetzlich als JSON ablegen"
    )
    parser.add_argument("--no-color", action="store_true", help="Farbausgabe abschalten")
    parser.add_argument("--version", action="version", version=f"check_compliance.py {VERSION}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = baue_parser().parse_args(argv)
    wurzel = args.root.resolve()

    ergebnis = pruefe_repo(wurzel, junit=args.junit, strict=args.strict)

    print(berichte(ergebnis, wurzel, _farbe_aktiv(args.no_color)))

    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        nutzlast = {
            "version": VERSION,
            "wurzel": str(wurzel),
            "strict": args.strict,
            "exit_code": ergebnis.exit_code,
            "anzahl_fehler": len(ergebnis.fehlerliste),
            "anzahl_warnungen": len(ergebnis.warnungsliste),
            "befunde": [asdict(b) for b in ergebnis.befunde],
        }
        args.json_out.write_text(
            json.dumps(nutzlast, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return ergebnis.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
