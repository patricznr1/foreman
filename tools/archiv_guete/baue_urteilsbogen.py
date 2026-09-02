#!/usr/bin/env python3
# ============================================================
#  FOREMAN — tools/archiv_guete/baue_urteilsbogen.py
#  Zweck: Stellt die UNBEURTEILTEN Paare (Anfrage, Vorgang) aus Messläufen
#         zusammen und schreibt einen Bogen, den ein Beurteiler ausfüllen kann.
#  Warum das ein Werkzeug ist und kein einmaliges Skript: Jede Änderung, die
#         andere Einträge nach oben spült — ein anderes Einbettungsmodell, ein
#         anderer Grenzwert, eine andere Fusion —, erweitert den Pool und macht
#         die vorhandenen Urteile lückenhaft. Das ist kein Sonderfall, sondern
#         der Normalfall nach jeder Verbesserung.
#  Warum ERZEUGT und nicht getippt: Am 25.08.2026 wurde ein Erhebungsbogen für
#         30 Fälle von Hand geschrieben, während die Rohdaten danebenlagen —
#         4 von 30 Zeilen waren falsch, das Instrument wertlos, und ein Mensch
#         hatte es umsonst ausgefüllt. Hier stammt jede Zeile aus einer Datei.
# ============================================================
from __future__ import annotations

import json
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
ZUORDNUNG = HIER / "goldset_v2_zuordnung.json"
ANFRAGEN = HIER / "goldset_v2_anfragen.yaml"

sys.path.insert(0, str(HIER))
import werte_aus as wa  # noqa: E402
from miss import lade_anfragen  # noqa: E402


def _rueckweg() -> dict[str, str]:
    """DB-Schlüssel → Vorgangskürzel. Der Bogen muss Kürzel führen, weil die
    vorhandenen Urteile sie führen — ein zweites Schlüsselsystem wäre der
    sichere Weg, die alten und die neuen Urteile unvergleichbar zu machen."""
    vorwaerts = json.loads(ZUORDNUNG.read_text(encoding="utf-8"))
    zurueck: dict[str, str] = {}
    for kuerzel, schluessel in vorwaerts.items():
        # Ein DB-Schlüssel unter ZWEI Kürzeln wäre eine stille Doppelung: Dasselbe
        # Paar bekäme zwei Urteile, und die Zählung stimmte nicht mehr.
        if schluessel in zurueck:
            raise SystemExit(
                f"❌ {schluessel} steht unter zwei Kuerzeln ({zurueck[schluessel]}, {kuerzel})."
            )
        zurueck[schluessel] = kuerzel
    return zurueck


def _paare(pfad: Path) -> dict[str, list[dict]]:
    """Je Anfrage die Treffer eines Rohlaufs, in der Reihenfolge der Ausgabe."""
    d = json.loads(pfad.read_text(encoding="utf-8"))
    return {lauf["anfrage_id"]: lauf["treffer"] for lauf in d["laeufe"]}


def _sammle_offene(
    messungen: list[str],
    beurteilt: dict[str, dict[str, int]],
    zurueck: dict[str, str],
) -> tuple[dict[str, dict[str, dict]], set[tuple[str, str]]]:
    """Alle noch unbeurteilten Paare über alle angegebenen Läufe.

    Zurück kommen zwei Mengen: die beurteilbaren (je Anfrage die Treffer unter
    ihrem Vorgangskürzel) und die, für die das Material kein Kürzel führt.

    Erst sammeln, DANN schreiben: Ein Paar, das zwei Läufe zeigen, ist EIN
    Urteil und darf nicht zweimal im Bogen stehen.
    """
    offen: dict[str, dict[str, dict]] = {}
    ohne_kuerzel: set[tuple[str, str]] = set()
    for pfad in messungen:
        for anfrage_id, treffer in _paare(Path(pfad)).items():
            for t in treffer:
                schluessel = wa._schluessel(t)
                if schluessel in beurteilt.get(anfrage_id, {}):
                    continue
                kuerzel = zurueck.get(schluessel)
                if kuerzel is None:
                    ohne_kuerzel.add((anfrage_id, schluessel))
                    continue
                offen.setdefault(anfrage_id, {}).setdefault(kuerzel, t)

    return offen, ohne_kuerzel  # Paare, nicht Eintraege


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit(
            "Aufruf: python baue_urteilsbogen.py <bewertungssatz.json> <messung.json> [...]\n"
            "        Der Bewertungssatz steht ZUERST, danach ein oder mehrere Rohlaeufe.\n"
            "  Beispiel: python baue_urteilsbogen.py goldset_v3.json \\\n"
            "            modellvergleich_2026-08-28/messung_armA_s06.json \\\n"
            "            modellvergleich_2026-08-28/messung_armB_s075.json"
        )
    goldset_pfad, *messungen = sys.argv[1:]
    if "messung" in goldset_pfad:
        raise SystemExit(
            f"❌ {goldset_pfad} sieht nach einer Rohdatei aus. Der Bewertungssatz steht ZUERST."
        )

    beurteilt = wa.lade_beurteilte(goldset_pfad)
    if beurteilt is None:
        raise SystemExit(f"❌ Keine beurteilte Menge zu {goldset_pfad} gefunden.")
    zurueck = _rueckweg()
    anfragen, _ = lade_anfragen(str(ANFRAGEN))
    text_zu = {a["id"]: a["anfrage"] for a in anfragen}

    offen, ohne_kuerzel = _sammle_offene(messungen, beurteilt, zurueck)
    gesamt = sum(len(v) for v in offen.values())
    zeilen: list[str] = [
        "# Urteilsbogen — unbeurteilte Paare aus den angegebenen Laeufen",
        "#",
        "# FRAGE JE ZEILE: Wollte ein Inbetriebnehmer diesen Eintrag zu DIESER",
        "# Anfrage sehen? Nicht: gehoert er zum selben Stoerungstyp.",
        "#   2 = gleiche Ursache (dasselbe Stoerungsbild)",
        "#   1 = gleiches Symptombild, ANDERE Ursache",
        "#   0 = nein",
        "#",
        "# AUSFUELLEN: das ? hinter dem = durch 0, 1 oder 2 ersetzen.",
        "# Die Zeilen mit '#' bleiben stehen, sie werden beim Einlesen ignoriert.",
        "#",
        f"# {gesamt} Paare ueber {len(offen)} Anfragen.",
    ]
    # NICHT VERSCHWIEGEN: Treffer ohne Vorgangskuerzel sind hier nicht
    # beurteilbar — die vorhandenen Urteile fuehren Kuerzel, und ein zweites
    # Schluesselsystem machte alte und neue Urteile unvergleichbar. Sie stehen
    # trotzdem im Bogen, als Liste statt als Zeile zum Ausfuellen. Ein still
    # ausgelassenes Paar senkte die Zahl der beurteilten Eintraege, ohne dass es
    # auffiele — und genau die Zahl traegt die Verzerrungskorrektur.
    if ohne_kuerzel:
        # PAARE zaehlen, nicht Eintraege: Ein Eintrag kann zu mehreren Anfragen
        # auftauchen, und beurteilt wird je Paar. Die Zahl der fehlenden Urteile
        # ist deshalb hoeher als die Zahl der fehlenden Eintraege — wer nur die
        # Eintraege zaehlt, unterschaetzt die Luecke.
        eintraege = {s for _, s in ohne_kuerzel}
        zeilen += [
            "#",
            f"# NICHT IM BOGEN: {len(ohne_kuerzel)} Paare ueber {len(eintraege)} Eintraege",
            f"# ohne Vorgangskuerzel in {ZUORDNUNG.name}. Die Zuordnung beginnt erst",
            "# bei note:16 (SN-001); diese Eintraege fuehrt das Bewertungsmaterial",
            "# gar nicht, sie sind damit nicht beurteilbar:",
            *(f"#   {s}" for s in sorted(eintraege)),
        ]
    zeilen.append("")
    for anfrage_id in sorted(offen):
        zeilen.append("")
        zeilen.append(f'## {anfrage_id} — "{text_zu.get(anfrage_id, "(unbekannt)")}"')
        for kuerzel in sorted(offen[anfrage_id]):
            t = offen[anfrage_id][kuerzel]
            # NICHT ein zweites Mal kuerzen: Das Archiv deckelt den Auszug
            # bereits (EXCERPT_BUDGET). Ein Schnitt bei 150 Zeichen nahm dem
            # Beurteiler genau den Teil, auf den es ankommt — bei B07-WA-021
            # endete die Zeile auf "Umkehrspie", waehrend die Messwerte
            # ("0,08 bis 0,11 mm gegen 0,02") dahinter standen, die das Urteil
            # entscheiden. Ein Bogen, der die tragende Angabe abschneidet,
            # erzeugt Urteile ueber etwas anderes als den Treffer.
            auszug = " ".join((t.get("excerpt") or "").split())
            zeilen.append(f"#   [{t['source_type']}] {auszug}")
            zeilen.append(f"{anfrage_id}-{kuerzel}=?")

    ziel = HIER / "gegenprobe" / "urteilsbogen_offen.txt"
    ziel.write_text("\n".join(zeilen) + "\n", encoding="utf-8")
    print(f"📋 {gesamt} unbeurteilte Paare ueber {len(offen)} Anfragen -> {ziel}")
    for anfrage_id in sorted(offen):
        print(f"   {anfrage_id}: {len(offen[anfrage_id])}")


if __name__ == "__main__":
    main()
