#!/usr/bin/env python3
# ============================================================
#  FOREMAN — tools/materialimport/lade.py
#  Zweck: Spielt erzeugtes Störungsmaterial (Schichtnotizen, Wartungen, Alarme)
#         über die HTTP-Schreibwege der Anwendung ein.
#  WARUM ÜBER HTTP UND NICHT IN DIE DATENBANK: Der Dual-Write ins Gedächtnis
#         hängt an `record_semantic_event` in der Anwendungsschicht. Ein direkter
#         Einwurf erzeugte Zeilen OHNE Spiegelung — die vierte Archiv-Quelle sähe
#         die neuen Daten nie, und der Backfill fängt es nicht auf (er wählt
#         `semantic_events` mit `substrate_ref IS NULL`; wo gar keine Zeile
#         entstanden ist, hat er nichts zu holen).
#  WOZU DAS MATERIAL: Der bisherige Bestand führt keinen einzigen wiederkehrenden
#         Vorgang (C-050). Die Frage „hatten wir das schon mal" hat dort auch bei
#         perfekter Suche keine Antwort.
#  UNUMKEHRBAR: Was eingespielt ist, wird über diesen Weg nicht wieder entfernt.
# ============================================================
"""Materialimport über die HTTP-Schreibwege.

Aufruf::

    export FOREMAN_DEMO_URL=https://…
    export FOREMAN_DEMO_EMAIL=… FOREMAN_DEMO_PASSWORT=…
    python tools/materialimport/lade.py --material PFAD --dry-run
    python tools/materialimport/lade.py --material PFAD
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import pathlib
import sys
import urllib.error
import urllib.request
from typing import Any

BASIS = os.environ.get("FOREMAN_DEMO_URL", "http://localhost:3000")
EMAIL = os.environ.get("FOREMAN_DEMO_EMAIL", "")
PASSWORT = os.environ.get("FOREMAN_DEMO_PASSWORT", "")
ZEITGRENZE = 30

# Nach so vielen WEG-Fehlern hintereinander wird abgebrochen. Ein Ladelauf, der
# gegen eine gestörte Gegenstelle weiterläuft, erzeugt 300 gleichartige Fehler
# und verdeckt den einen, auf den es ankommt.
ABBRUCH_NACH_WEGFEHLERN = 5

# Der Bereich, in dem der Szenario-Schlüssel einer Komponente steht. Der
# HTTP-Weg liefert ihn NICHT (`ComponentRead` führt nur `label` und
# `component_type`), deshalb wird über die Bezeichnung abgebildet.
SZENARIEN = pathlib.Path("src/foreman/adapters/simulation/scenarios")


class Zaehler:
    """Getrennt, weil sie Verschiedenes messen.

    `wegfehler` und `eintragsfehler` dürfen NIE zusammenfallen. Eine gestörte
    Gegenstelle ist kein abgelehnter Eintrag: Der Eintrag ist in Ordnung und
    gehört in den nächsten Lauf, der abgelehnte gehört korrigiert. Wer beides
    zusammenzählt, weiss hinterher nicht, was zu tun ist.
    """

    def __init__(self) -> None:
        self.gelesen = 0
        self.uebersprungen = 0  # steht schon im Fortschritt
        self.angelegt = 0
        self.eintragsfehler = 0  # 4xx — der Eintrag selbst
        self.wegfehler = 0  # Netz, 5xx — der Weg

    def __str__(self) -> str:
        return (
            f"gelesen={self.gelesen} übersprungen={self.uebersprungen} "
            f"angelegt={self.angelegt} eintragsfehler={self.eintragsfehler} "
            f"wegfehler={self.wegfehler}"
        )


def melde_an() -> urllib.request.OpenerDirector:
    """Anmeldung wie in `tools/archiv_guete/miss.py` — dieselbe Bauform."""
    if not EMAIL or not PASSWORT:
        raise SystemExit(
            "❌ FOREMAN_DEMO_EMAIL und FOREMAN_DEMO_PASSWORT müssen gesetzt sein "
            "(optional FOREMAN_DEMO_URL, sonst http://localhost:3000)."
        )
    jar = http.cookiejar.CookieJar()
    oeffner = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    anfrage = urllib.request.Request(
        f"{BASIS}/api/session",
        data=json.dumps({"email": EMAIL, "password": PASSWORT}).encode(),
        headers={"content-type": "application/json"},
        method="POST",
    )
    with oeffner.open(anfrage, timeout=ZEITGRENZE) as antwort:
        if antwort.status != 200:
            raise SystemExit(f"❌ Anmeldung fehlgeschlagen: HTTP {antwort.status}")
        profil = json.load(antwort)
    # Nur die ROLLE ins Protokoll, nie die E-Mail. Ein Protokolleintrag wird
    # weitergereicht, aufbewahrt und durchsucht — er ist die Stelle, an der
    # Personendaten am leichtesten den Zweck verlassen. Für den Zweck hier
    # („bin ich mit ausreichenden Rechten angemeldet") trägt die Rolle alles,
    # was gebraucht wird. `tools/archiv_guete/miss.py` protokolliert an der
    # entsprechenden Stelle noch die Adresse — dort nachzuziehen.
    print(f"🔑 angemeldet, Rolle {profil['role']}")
    return oeffner


def hole(oeffner: urllib.request.OpenerDirector, pfad: str) -> Any:
    anfrage = urllib.request.Request(f"{BASIS}/api/v1{pfad}", method="GET")
    with oeffner.open(anfrage, timeout=ZEITGRENZE) as antwort:
        return json.load(antwort)


def sende(
    oeffner: urllib.request.OpenerDirector, pfad: str, nutzlast: dict[str, Any]
) -> tuple[dict[str, Any] | None, str | None, bool]:
    """Legt einen Eintrag an. Gibt (Antwort, Fehlertext, ist_wegfehler) zurück.

    Die Unterscheidung ist der Kern des Fehlerzweigs: **4xx ist ein
    EINTRAGS-Fehler** (der Eintrag taugt nicht und gehört korrigiert), **5xx und
    Netzfehler sind WEG-Fehler** (der Eintrag ist in Ordnung und gehört in den
    nächsten Lauf). Ein Weg-Fehler darf niemals einen Eintrag verbrauchen.
    """
    anfrage = urllib.request.Request(
        f"{BASIS}/api/v1{pfad}",
        data=json.dumps(nutzlast, ensure_ascii=False).encode("utf-8"),
        headers={"content-type": "application/json"},
        method="POST",
    )
    try:
        with oeffner.open(anfrage, timeout=ZEITGRENZE) as antwort:
            return json.load(antwort), None, False
    except urllib.error.HTTPError as fehler:
        rumpf = fehler.read().decode("utf-8", errors="replace")[:300]
        ist_weg = fehler.code >= 500
        return None, f"HTTP {fehler.code}: {rumpf}", ist_weg
    except (urllib.error.URLError, OSError, TimeoutError) as fehler:
        return None, f"{type(fehler).__name__}: {fehler}", True


def komponenten_schluessel() -> dict[tuple[str, str], str]:
    """Bildet (Maschinen-Kennung, Szenario-Schlüssel) auf die BEZEICHNUNG ab.

    Der HTTP-Weg gibt den Szenario-Schlüssel nicht heraus. Die Bezeichnung ist
    die einzige Brücke — sie steht in derselben Szenario-Datei wie der Schlüssel
    und wird beim Seeding unverändert in die Datenbank geschrieben.
    """
    import yaml

    aus: dict[tuple[str, str], str] = {}
    for datei in sorted(SZENARIEN.glob("park_*.yaml")):
        d = yaml.safe_load(datei.read_text(encoding="utf-8"))
        # Eine Park-Datei beschreibt GENAU EINE Maschine: `machine` und
        # `components` stehen nebeneinander auf oberster Ebene, nicht
        # verschachtelt. Wer hier eine Liste `machines` erwartet, bekommt ein
        # leeres Verzeichnis — ohne Fehler, und jedes `component_id` bliebe leer.
        kennung = (d.get("machine") or {}).get("external_id")
        if not kennung:
            continue
        for komponente in d.get("components") or []:
            schluessel, bezeichnung = komponente.get("key"), komponente.get("label")
            if schluessel and bezeichnung:
                aus[(kennung, schluessel)] = bezeichnung
    if not aus:
        raise SystemExit(
            f"❌ Kein einziger Komponenten-Schlüssel aus {SZENARIEN} gelesen. "
            "Vom Repo-Wurzelverzeichnis aus starten."
        )
    return aus


class Verzeichnis:
    """Löst Maschinen- und Komponenten-Kennungen des Materials auf echte IDs auf."""

    def __init__(self, oeffner: urllib.request.OpenerDirector) -> None:
        self._maschine: dict[str, int] = {}
        self._komponente: dict[tuple[str, str], int] = {}
        self._bezeichnung = komponenten_schluessel()

        for m in hole(oeffner, "/machines?limit=1000"):
            if m.get("external_id"):
                self._maschine[m["external_id"]] = int(m["id"])
        for kennung, machine_id in self._maschine.items():
            for k in hole(oeffner, f"/components?machine_id={machine_id}&limit=1000"):
                for (mk, schluessel), bez in self._bezeichnung.items():
                    if mk == kennung and bez == k.get("label"):
                        self._komponente[(kennung, schluessel)] = int(k["id"])

    def maschine(self, kennung: str) -> int:
        if kennung not in self._maschine:
            raise KeyError(f"Maschine {kennung} gibt es in der Instanz nicht")
        return self._maschine[kennung]

    def komponente(self, kennung: str, schluessel: str | None) -> int | None:
        """None statt Fehler: `component_id` ist überall optional.

        Ein nicht auflösbarer Schlüssel darf den Eintrag nicht kosten — der
        Freitext trägt die Suche, nicht die Komponente. Gemeldet wird es
        trotzdem, sonst verschwindet eine Lücke im Verzeichnis stillschweigend.
        """
        if not schluessel:
            return None
        treffer = self._komponente.get((kennung, schluessel))
        if treffer is None:
            print(f"⚠️ Komponente {kennung}/{schluessel} nicht auflösbar — Feld bleibt leer")
        return treffer

    def kennungen(self) -> list[str]:
        return sorted(self._maschine)

    def __str__(self) -> str:
        return f"{len(self._maschine)} Maschinen, {len(self._komponente)} Komponenten"


PROBE_TEXT = (
    "Vorflug-Probe des Materialimports. Prüft, ob die Instanz einen historischen "
    "Zeitpunkt übernimmt. Kein Betriebsvorgang."
)


def pruefe_zeitfeld(oeffner: urllib.request.OpenerDirector, machine_id: int) -> None:
    """Bricht ab, wenn die Instanz `occurred_at` still verwirft.

    WARUM DAS SEIN MUSS: `WorkerNoteCreate` hat kein `extra="forbid"` — ein
    unbekanntes Feld verfällt ohne Fehler, und die Antwort ist trotzdem 201.
    Läuft der Import gegen eine Instanz ohne das Feld, tragen ALLE Notizen den
    Ladezeitpunkt statt der Schichtzeit. Das Archiv ordnet Notiz-Treffer danach;
    die Chronologie jedes Störungsvorgangs bricht, und zwar lautlos.

    Deshalb wird die ANTWORT gegen das GESENDETE geprüft, nicht der Statuscode.
    Eine falsche Probe kostet einen Eintrag; ein falscher Lauf kostet 189.
    """
    vergangen = "2020-01-01T03:00:00+01:00"
    antwort, fehler, _weg = sende(
        oeffner,
        "/worker_notes",
        {"text": PROBE_TEXT, "machine_id": machine_id, "occurred_at": vergangen},
    )
    if antwort is None:
        raise SystemExit(f"❌ Vorflug-Probe fehlgeschlagen: {fehler}")

    gemeldet = str(antwort.get("created_at", ""))
    if not gemeldet.startswith("2020-01-01"):
        raise SystemExit(
            "❌ Die Instanz übernimmt `occurred_at` NICHT — gemeldet wurde "
            f"{gemeldet!r} statt {vergangen!r}.\n"
            "   Alle Notizen bekämen den Ladezeitpunkt, ohne dass ein Fehler "
            "entsteht. Erst die Fassung mit dem Zeitfeld ausrollen, dann laden.\n"
            "   Die Probe-Notiz ist angelegt und kann von Hand entfernt werden."
        )
    print(f"✅ Vorflug-Probe: historischer Zeitpunkt kommt an ({gemeldet[:10]})")


class Fortschritt:
    """Merkt sich, welche Materialkennung schon angelegt wurde.

    WARUM EINE DATEI UND KEINE ABFRAGE: Die Schreibwege geben keinen natürlichen
    Schlüssel zurück, an dem sich ein Eintrag wiedererkennen liesse — zwei
    gleiche Notizen an derselben Maschine zur selben Zeit sind über die API nicht
    unterscheidbar. Der Fortschritt wird deshalb hier geführt.

    WAS DAS BEDEUTET: Geht die Datei verloren, legt ein zweiter Lauf alles noch
    einmal an. Deshalb wird sie NACH JEDEM einzelnen Erfolg geschrieben, nicht am
    Ende — bricht der Lauf bei Eintrag 200 ab, sind 199 vermerkt.
    """

    def __init__(self, pfad: pathlib.Path) -> None:
        self._pfad = pfad
        self._fertig: set[str] = set()
        if pfad.exists():
            self._fertig = set(json.loads(pfad.read_text(encoding="utf-8"))["angelegt"])

    def __contains__(self, kennung: str) -> bool:
        return kennung in self._fertig

    def __len__(self) -> int:
        return len(self._fertig)

    def vermerke(self, kennung: str) -> None:
        self._fertig.add(kennung)
        self._pfad.write_text(
            json.dumps({"angelegt": sorted(self._fertig)}, indent=2), encoding="utf-8"
        )


def nutzlasten(material: pathlib.Path, v: Verzeichnis) -> list[tuple[str, str, dict[str, Any]]]:
    """Baut (Kennung, Pfad, Nutzlast) für jeden Eintrag — chronologisch.

    CHRONOLOGISCH, weil ein Vorgang sonst in der falschen Reihenfolge im Archiv
    steht, wenn der Lauf mittendrin abbricht.
    """
    aus: list[tuple[str, str, str, dict[str, Any]]] = []

    for n in json.loads((material / "worker_notes.json").read_text(encoding="utf-8"))[
        "worker_notes"
    ]:
        aus.append(
            (
                n["occurred_at"],
                n["id"],
                "/worker_notes",
                {
                    "text": n["text"],
                    "machine_id": v.maschine(n["machine_external_id"]),
                    "shift": n.get("shift"),
                    "occurred_at": n["occurred_at"],
                },
            )
        )

    for w in json.loads((material / "maintenance_events.json").read_text(encoding="utf-8"))[
        "maintenance_events"
    ]:
        kennung = w["machine_external_id"]
        aus.append(
            (
                w["performed_at"],
                w["id"],
                "/maintenance_events",
                {
                    "machine_id": v.maschine(kennung),
                    "component_id": v.komponente(kennung, w.get("component_key")),
                    "type": w["maintenance_type"],
                    "description": w.get("description"),
                    "performed_at": w["performed_at"],
                },
            )
        )

    for a in json.loads((material / "alarms.json").read_text(encoding="utf-8"))["alarms"]:
        kennung = a["machine_external_id"]
        aus.append(
            (
                a["triggered_at"],
                a["id"],
                "/alarms",
                {
                    "machine_id": v.maschine(kennung),
                    "component_id": v.komponente(kennung, a.get("component_key")),
                    "code": a["code"],
                    "severity": a["severity"],
                    "category": a["category"],
                    "message": a.get("message"),
                    "raised_at": a["triggered_at"],
                },
            )
        )

    aus.sort(key=lambda x: x[0])
    return [(kennung, pfad, last) for _zeit, kennung, pfad, last in aus]


def lade(
    oeffner: urllib.request.OpenerDirector,
    material: pathlib.Path,
    fortschritt: Fortschritt,
    *,
    trockenlauf: bool,
    limit: int | None,
) -> Zaehler:
    z = Zaehler()
    v = Verzeichnis(oeffner)
    print(f"📖 Verzeichnis: {v}")

    posten = nutzlasten(material, v)
    if limit is not None:
        posten = posten[:limit]
    print(f"📦 {len(posten)} Einträge, chronologisch · schon vermerkt: {len(fortschritt)}")

    # VOR dem ersten echten Eintrag: taugt die Gegenstelle überhaupt?
    if not trockenlauf:
        pruefe_zeitfeld(oeffner, v.maschine(next(iter(v.kennungen()))))

    wegfehler_in_folge = 0
    for kennung, pfad, last in posten:
        z.gelesen += 1
        if kennung in fortschritt:
            z.uebersprungen += 1
            continue
        if trockenlauf:
            continue

        antwort, fehler, ist_weg = sende(oeffner, pfad, last)
        if antwort is not None:
            # NUR nach einem Erfolg vermerken. Ein vorzeitiger Vermerk liesse den
            # Eintrag dauerhaft aus jedem künftigen Lauf fallen.
            fortschritt.vermerke(kennung)
            z.angelegt += 1
            wegfehler_in_folge = 0  # NUR der Erfolg nullt die Serie
            continue

        if ist_weg:
            z.wegfehler += 1
            wegfehler_in_folge += 1
            print(f"⚠️ {kennung}: Weg gestört ({fehler}) — Eintrag bleibt für den nächsten Lauf")
            if wegfehler_in_folge >= ABBRUCH_NACH_WEGFEHLERN:
                print(
                    f"❌ {ABBRUCH_NACH_WEGFEHLERN} Weg-Fehler hintereinander — Abbruch. "
                    "Der Fortschritt ist vermerkt, ein erneuter Lauf setzt fort."
                )
                break
            continue

        # Eintrags-Fehler: der Eintrag taugt nicht. Er wird NICHT vermerkt, damit
        # er nach einer Korrektur des Materials erneut versucht wird.
        z.eintragsfehler += 1
        print(f"❌ {kennung}: abgelehnt ({fehler})")

    return z


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python tools/materialimport/lade.py",
        description="Spielt Störungsmaterial über die HTTP-Schreibwege ein. UNUMKEHRBAR.",
    )
    p.add_argument(
        "--material", required=True, type=pathlib.Path, help="Verzeichnis mit den JSON-Dateien"
    )
    p.add_argument(
        "--fortschritt", type=pathlib.Path, default=pathlib.Path("materialimport_fortschritt.json")
    )
    p.add_argument("--dry-run", action="store_true", help="Nur zählen, nichts anlegen")
    p.add_argument("--limit", type=int, default=None)
    args = p.parse_args(argv)

    if not args.material.is_dir():
        raise SystemExit(f"❌ Kein Verzeichnis: {args.material}")

    oeffner = melde_an()
    fortschritt = Fortschritt(args.fortschritt)
    z = lade(oeffner, args.material, fortschritt, trockenlauf=args.dry_run, limit=args.limit)
    print(f"\n📊 {z}")
    if z.wegfehler:
        print(f"⚠️ {z.wegfehler} Einträge wegen Weg-Störungen offen — erneut laufen lassen.")
    if z.eintragsfehler:
        print(f"❌ {z.eintragsfehler} Einträge abgelehnt — Material prüfen, dann erneut.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
