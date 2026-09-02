# ============================================================
#  FOREMAN — Goldset-Messung, Schritt 0: DEN BEWERTUNGSSATZ BAUEN
#  Zweck: Erzeugt aus den Rohurteilen des Fragenkatalogs zwei Dateien:
#         - goldset_v3.json     — nur die ZUTREFFENDEN Eintraege (Stufe 1|2)
#         - beurteilt_v3.json   — ALLE beurteilten Eintraege, auch die mit 0
#  Warum es diese Datei gibt (Befund 27.08.2026): goldset_v3.json war von Hand
#         entstanden. Ein Bewertungssatz, dessen Erzeugung nicht reproduzierbar
#         ist, kann nicht ERWEITERT werden — und genau das verlangt jede weitere
#         Variante, weil sie neue Eintraege in die Trefferliste bringt, die
#         niemand beurteilt hat. Unbeurteilt zaehlt als nicht zutreffend, und
#         damit wird jede neue Variante systematisch benachteiligt
#         (Pool-Verzerrung; Buettcher et al., SIGIR 2007: im Mittel rund zwei
#         Rangplaetze, in Einzelfaellen zwoelf bis vierzehn).
#  Warum ZWEI Dateien: Der Unterschied zwischen "beurteilt und nicht zutreffend"
#         und "gar nicht beurteilt" ist der ganze Punkt. Das Goldset allein kann
#         ihn nicht ausdruecken — es fuehrt nur die Treffer.
#  KONTROLLPUNKT: Der Lauf vergleicht das erzeugte Goldset mit dem vorhandenen
#         und bricht bei Abweichung ab. Ohne diesen Vergleich waere nicht zu
#         unterscheiden, ob die Rekonstruktion stimmt oder nur plausibel aussieht.
#  Aufruf: python baue_goldset_v3.py [--schreiben] [--erweitern]
#          Ohne --schreiben nur pruefen (Trockenlauf).
#          --erweitern erlaubt das Neuschreiben, wenn der Satz WAECHST —
#          also Eintraege hinzukommen und keiner wegfaellt. Verliert er
#          etwas, bricht der Lauf unabhaengig vom Schalter ab.
# ============================================================
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
# ALLE Urteilsdateien, nach Namen sortiert. Der Bewertungssatz waechst, wenn eine
# Aenderung andere Eintraege nach oben spuelt — und dann kommt eine Datei dazu,
# statt eine bestehende umgeschrieben zu werden. Das erhaelt, WANN welches Urteil
# entstanden ist; ein nachtraeglich veraenderter Massstab waere nicht mehr
# nachvollziehbar.
URTEILSDATEIEN = sorted((HIER / "gegenprobe").glob("relevanz_urteile_*.txt"))
ZUORDNUNG = HIER / "goldset_v2_zuordnung.json"
GOLDSET = HIER / "goldset_v3.json"
BEURTEILT = HIER / "beurteilt_v3.json"

# B02-SN-098=0 — Anfrage, Vorgangskuerzel, Stufe.
_URTEIL = re.compile(r"^(?P<anfrage>B\d+)-(?P<kuerzel>[A-Z]{2}-\d+)=(?P<stufe>[012])$")


def lies_urteile() -> dict[str, dict[str, int]]:
    """Rohurteile → {Anfrage: {Vorgangskuerzel: Stufe}}.

    Ein nicht deutbares Wort bricht ab, statt uebersprungen zu werden: Ein still
    verworfenes Urteil senkt die Zahl der beurteilten Eintraege, ohne dass es
    jemandem auffiele — und genau die Zahl traegt die Verzerrungskorrektur.
    """
    if not URTEILSDATEIEN:
        raise SystemExit("❌ Keine Urteilsdatei unter gegenprobe/relevanz_urteile_*.txt.")
    je_anfrage: dict[str, dict[str, int]] = {}
    herkunft: dict[tuple[str, str], str] = {}
    for datei in URTEILSDATEIEN:
        for zeile in datei.read_text(encoding="utf-8").splitlines():
            # Kommentarzeilen ueberspringen. DER BOGEN VERSPRICHT DAS: Er traegt
            # zu jedem Paar den Auszug als '#'-Zeile und sagt dem Beurteiler, sie
            # bleibe stehen. Ohne diese Zeile bricht der Einlesevorgang am ersten
            # Auszug ab — und der ausgefuellte Bogen muesste von Hand gesaeubert
            # werden, was die Auszuege verloere. Genau sie machen ein Urteil aber
            # nachtraeglich pruefbar: Sie zeigen, WAS dem Beurteiler vorlag.
            if zeile.lstrip().startswith("#"):
                continue
            for wort in zeile.split():
                treffer = _URTEIL.match(wort)
                if not treffer:
                    raise SystemExit(f"❌ Unverstaendliches Urteil: {wort!r} in {datei.name}")
                anfrage = treffer["anfrage"]
                kuerzel = treffer["kuerzel"]
                stufe = int(treffer["stufe"])
                bisher = je_anfrage.setdefault(anfrage, {})
                if kuerzel in bisher and bisher[kuerzel] != stufe:
                    # Ueber mehrere Dateien hinweg ist das der wichtige Fall: Dasselbe
                    # Paar zweimal verschieden beurteilt. Raten waere hier das
                    # Schlimmste — die Auswahl entschiede der Zufall der Dateinamen.
                    raise SystemExit(
                        f"❌ Widersprechende Urteile zu {anfrage}-{kuerzel}: "
                        f"{bisher[kuerzel]} ({herkunft[(anfrage, kuerzel)]}) und "
                        f"{stufe} ({datei.name}). Von Hand klaeren, nicht raten."
                    )
                bisher[kuerzel] = stufe
                herkunft[(anfrage, kuerzel)] = datei.name
    return je_anfrage


def loese_auf(
    urteile: dict[str, dict[str, int]], zuordnung: dict[str, str]
) -> tuple[dict[str, dict[str, int]], dict[str, dict[str, int]]]:
    """Vorgangskuerzel → Datenbank-Schluessel. Liefert (Goldset, Beurteilte)."""
    goldset: dict[str, dict[str, int]] = {}
    beurteilt: dict[str, dict[str, int]] = {}
    for anfrage in sorted(urteile):
        goldset[anfrage] = {}
        beurteilt[anfrage] = {}
        for kuerzel, stufe in urteile[anfrage].items():
            schluessel = zuordnung.get(kuerzel)
            if schluessel is None:
                raise SystemExit(
                    f"❌ {kuerzel} steht in den Urteilen, aber nicht in "
                    f"{ZUORDNUNG.name}. Geraten wird nicht."
                )
            beurteilt[anfrage][schluessel] = stufe
            if stufe > 0:
                goldset[anfrage][schluessel] = stufe
    return goldset, beurteilt


def main() -> None:
    schreiben = "--schreiben" in sys.argv[1:]
    erweitern = "--erweitern" in sys.argv[1:]

    urteile = lies_urteile()
    zuordnung = json.loads(ZUORDNUNG.read_text(encoding="utf-8"))
    goldset, beurteilt = loese_auf(urteile, zuordnung)

    beurteilte = sum(len(v) for v in beurteilt.values())
    zutreffende = sum(len(v) for v in goldset.values())
    stufe2 = sum(1 for v in goldset.values() for s in v.values() if s == 2)
    print(
        f"📋 {len(goldset)} Anfragen · {beurteilte} beurteilte Eintraege · "
        f"{zutreffende} zutreffend ({stufe2} Stufe 2, {zutreffende - stufe2} Stufe 1)"
    )

    # KONTROLLPUNKT gegen den vorhandenen Bewertungssatz.
    if GOLDSET.exists():
        vorhanden = json.loads(GOLDSET.read_text(encoding="utf-8"))
        if vorhanden != goldset:
            fehlend = {
                a: sorted(set(vorhanden.get(a, {})) ^ set(goldset.get(a, {})))
                for a in set(vorhanden) | set(goldset)
            }
            abweichend = {a: s for a, s in fehlend.items() if s}
            # ERWEITERN IST DER NORMALFALL, ueberschreiben nie. Eine Aenderung, die
            # nur HINZUFUEGT, ist der erwartete Ausgang, wenn eine neue
            # Urteilsdatei dazukommt — sie muss trotzdem angesagt werden. Eine
            # Aenderung, die etwas WEGNIMMT, bricht dagegen immer ab: Dort ist ein
            # Urteil verschwunden oder gekippt, und das darf kein Schalter
            # durchwinken.
            verloren = {
                a: sorted(set(vorhanden.get(a, {})) - set(goldset.get(a, {}))) for a in vorhanden
            }
            verloren = {a: s for a, s in verloren.items() if s}
            if verloren:
                raise SystemExit(
                    f"❌ Der erzeugte Bewertungssatz VERLIERT Eintraege: {verloren}\n"
                    "   Ein Urteil ist verschwunden oder gekippt. Von Hand klaeren."
                )
            if not erweitern:
                raise SystemExit(
                    f"❌ Der erzeugte Bewertungssatz ergaenzt den vorhandenen: {abweichend}\n"
                    "   Verloren geht nichts. Wenn das gewollt ist, mit --erweitern "
                    "ausfuehren."
                )
            zusatz = sum(len(s) for s in abweichend.values())
            print(f"📈 {zusatz} Eintraege kommen hinzu, keiner faellt weg")
        else:
            print(f"✅ Deckt sich mit dem vorhandenen {GOLDSET.name}")
    else:
        print(f"📋 {GOLDSET.name} existiert noch nicht — kein Vergleich moeglich")

    if not schreiben:
        print("🔎 Trockenlauf — nichts geschrieben (mit --schreiben ausfuehren)")
        return

    # Der Bewertungssatz wird NUR geschrieben, wenn er fehlt. Deckt er sich (der
    # Kontrollpunkt oben laesst nichts anderes durch), waere ein Ueberschreiben
    # reine Bewegung in der Aenderungsansicht — und in einer Datei, die Urteile
    # traegt, ist eine Aenderung ohne Grund das Letzte, was jemand sehen will.
    if GOLDSET.exists() and not erweitern:
        print(f"↩️  {GOLDSET.name} unveraendert gelassen (deckungsgleich)")
    else:
        GOLDSET.write_text(
            json.dumps(goldset, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
        print(f"💾 {GOLDSET.name} geschrieben")
    BEURTEILT.write_text(
        json.dumps(beurteilt, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(f"💾 {BEURTEILT.name} geschrieben")


if __name__ == "__main__":
    main()
