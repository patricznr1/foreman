# ============================================================
#  FOREMAN — Goldset-Fusion
#  Zweck: Verdichtet die drei unabhaengigen Relevanzurteile zu EINEM Goldset.
#         Mehrheitsregel: ein Eintrag gilt als relevant, wenn ihn mindestens
#         zwei der drei Bewerter nennen. Die Stufe ist der Median der Stufen
#         derer, die ihn genannt haben.
#  Warum Mehrheit: Ein Goldset aus einem einzigen Urteil misst dieses Urteil mit.
#         Die Uebereinstimmung der Bewerter wird mit ausgewiesen — ist sie
#         niedrig, ist die Aufgabe schlecht gestellt und die Messung wackelig.
#  Quelle: die Roh-Ausgabe des Bewertungslaufs. Nichts wird abgetippt.
# ============================================================
from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict

MINDESTSTIMMEN = 2


def main() -> None:
    quelle = sys.argv[1] if len(sys.argv) > 1 else "urteile_roh.json"
    roh = json.load(open(quelle, encoding="utf-8"))
    bewerter_liste = roh["result"]["urteile"] if "result" in roh else roh["urteile"]

    # stimmen[anfrage_id][schluessel] = [(bewerter, stufe), ...]
    stimmen: dict[str, dict[str, list[tuple[str, int]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    namen = []
    for eintrag in bewerter_liste:
        name = eintrag["bewerter"]
        namen.append(name)
        for u in eintrag["urteile"]:
            for r in u["relevant"]:
                stimmen[u["anfrage_id"]][r["schluessel"]].append((name, r["stufe"]))

    goldset: dict[str, dict[str, int]] = {}
    knapp: list[str] = []
    verworfen: list[str] = []

    for aid in sorted(stimmen):
        goldset[aid] = {}
        for schluessel, liste in sorted(stimmen[aid].items()):
            if len(liste) >= MINDESTSTIMMEN:
                stufe = int(round(statistics.median([s for _, s in liste])))
                goldset[aid][schluessel] = stufe
                if len(liste) == MINDESTSTIMMEN:
                    knapp.append(f"{aid}/{schluessel}")
            else:
                verworfen.append(f"{aid}/{schluessel} (nur {liste[0][0]})")

    json.dump(
        goldset,
        open("goldset.json", "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=1,
    )

    print(f"Bewerter: {', '.join(namen)}")
    print(f"Regel   : relevant ab {MINDESTSTIMMEN} von {len(namen)} Stimmen\n")
    print(f"{'ID':6s} {'rel':>4s} {'Stufe2':>7s}  Schluessel")
    print("-" * 76)
    gesamt = 0
    for aid, treffer in goldset.items():
        gesamt += len(treffer)
        zwei = sum(1 for s in treffer.values() if s == 2)
        print(
            f"{aid:6s} {len(treffer):4d} {zwei:7d}  {', '.join(sorted(treffer))[:52]}"
        )
    print("-" * 76)
    print(f"Relevante Zuordnungen gesamt : {gesamt}")
    print(f"davon knapp (genau {MINDESTSTIMMEN} Stimmen) : {len(knapp)}")
    print(f"verworfen (nur 1 Stimme)     : {len(verworfen)}")

    # Uebereinstimmung: Anteil der Zuordnungen, die ALLE Bewerter nannten.
    alle = sum(
        1 for a in stimmen.values() for liste in a.values() if len(liste) == len(namen)
    )
    genannt = sum(len(a) for a in stimmen.values())
    print(
        f"\nUebereinstimmung: {alle} von {genannt} genannten Zuordnungen von ALLEN {len(namen)} "
        f"Bewertern getragen = {alle / genannt:.1%}"
    )
    if verworfen:
        print("\nNur von einem Bewerter genannt (nicht im Goldset):")
        for v in verworfen[:25]:
            print("   ", v)


if __name__ == "__main__":
    main()
