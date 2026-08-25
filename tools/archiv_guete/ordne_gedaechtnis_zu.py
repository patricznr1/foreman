# ============================================================
#  FOREMAN — Hilfsauswertung: was die vierte Quelle beitragen WÜRDE
#  Zweck: Ein Treffer aus dem Gedächtnis trägt `id=0` — die Erinnerung hat keinen
#         Primärschlüssel, und `RecallItem` reicht `source_type`/`source_id` der
#         Spiegel-Nutzlast nicht durch (offener Punkt in GROUND_TRUTH §15.10).
#         Damit ist er auf keinen Goldset-Schlüssel abbildbar und kann per
#         Konstruktion NIE als relevant gezählt werden. Die Freigabe-Bedingung 2
#         ist deshalb heute nicht MESSBAR — was etwas anderes ist als nicht erfüllt.
#  Was dieses Skript tut: Es ordnet Gedächtnis-Treffer über Maschine und Zeitpunkt
#         aus dem Auszug ihrer Quellzeile zu — dasselbe Verfahren, das der
#         Nachtrag benutzt, und aus demselben Grund nur bei EINDEUTIGKEIT.
#  Was es NICHT ist: ein Ersatz für die Messung. Es beziffert, was ein
#         durchgereichter Rückweg sichtbar machen würde.
# ============================================================
from __future__ import annotations

import json
import math
import re

# "an Maschine 2 durchgeführt (2026-06-06T17:03:51.561708+00:00)"
MUSTER_WARTUNG = re.compile(r"an Maschine (\d+) durchgeführt \(([0-9T:+.\-]+)\)")
# "an Maschine 2 ausgelöst (2026-06-17T...)"
MUSTER_ALARM = re.compile(r"an Maschine (\d+) ausgelöst \(([0-9T:+.\-]+)\)")


def lade_bestand() -> dict[tuple[str, int, str], str]:
    """Bildet (art, maschine, zeitpunkt) auf den Goldset-Schlüssel ab."""
    karte: dict[tuple[str, int, str], str] = {}
    for e in json.load(open("bestand_flach.json", encoding="utf-8")):
        if e["quelle"] in ("maintenance", "alarm"):
            karte[(e["quelle"], e["machine_id"], e["zeit"])] = e["schluessel"]
    return karte


def zuordnen(auszug: str, karte: dict) -> str | None:
    """Findet die Quellzeile zu einem Gedächtnis-Auszug. None, wenn nicht eindeutig."""
    for muster, art in ((MUSTER_WARTUNG, "maintenance"), (MUSTER_ALARM, "alarm")):
        treffer = muster.search(auszug)
        if treffer:
            maschine = int(treffer.group(1))
            tag = treffer.group(2)[:10]
            return karte.get((art, maschine, tag))
    return None


def dcg(stufen: list[int]) -> float:
    return sum(s / math.log2(i + 2) for i, s in enumerate(stufen))


def main() -> None:
    gold = json.load(open("goldset.json", encoding="utf-8"))
    karte = lade_bestand()
    basis = json.load(open("messung_baseline_neu.json", encoding="utf-8"))
    neu = json.load(open("messung_mit_gedaechtnis_v2.json", encoding="utf-8"))
    k = neu["k"]

    basis_je = {lauf["anfrage_id"]: lauf for lauf in basis["laeufe"]}

    zugeordnet = nicht_zuordenbar = 0
    mit_zusatz: list[str] = []
    schlechter: list[str] = []
    recall_alt: list[float] = []
    recall_neu: list[float] = []
    ndcg_alt: list[float] = []
    ndcg_neu: list[float] = []

    print(f"{'ID':6s} {'Recall alt':>10s} {'Recall neu':>10s}  zusätzlich gefunden")
    print("-" * 78)
    for lauf in neu["laeufe"]:
        aid = lauf["anfrage_id"]
        rel = gold.get(aid, {})
        if not rel:
            continue

        # Gedächtnis-Treffer auf Quellzeilen abbilden, Reihenfolge erhalten.
        aufgeloest: list[str] = []
        for t in lauf["treffer"][:k]:
            if t["source_type"] != "memory":
                aufgeloest.append(t["schluessel"])
                continue
            ziel = zuordnen(t["excerpt"], karte)
            if ziel is None:
                nicht_zuordenbar += 1
                aufgeloest.append("memory:?")
            else:
                zugeordnet += 1
                aufgeloest.append(ziel)

        alt = [t["schluessel"] for t in basis_je[aid]["treffer"][:k]]
        gef_alt = [s for s in alt if s in rel]
        gef_neu = [s for s in dict.fromkeys(aufgeloest) if s in rel]

        r_alt = len(gef_alt) / len(rel)
        r_neu = len(gef_neu) / len(rel)
        recall_alt.append(r_alt)
        recall_neu.append(r_neu)

        best = dcg(sorted(rel.values(), reverse=True)[:k])
        ndcg_alt.append(dcg([rel.get(s, 0) for s in alt]) / best if best else 0.0)
        ndcg_neu.append(dcg([rel.get(s, 0) for s in aufgeloest]) / best if best else 0.0)

        neue = [s for s in gef_neu if s not in gef_alt]
        verloren = [s for s in gef_alt if s not in gef_neu]
        if neue:
            mit_zusatz.append(aid)
        if verloren:
            schlechter.append(aid)
        print(f"{aid:6s} {r_alt:10.2f} {r_neu:10.2f}  {', '.join(neue) or '—'}")

    n = len(recall_alt)

    def m(werte: list[float]) -> float:
        return sum(werte) / len(werte)

    print("-" * 78)
    print(f"Recall  {m(recall_alt):.3f} -> {m(recall_neu):.3f}")
    print(f"nDCG    {m(ndcg_alt):.3f} -> {m(ndcg_neu):.3f}")
    print()
    print(f"Gedächtnis-Treffer zugeordnet     : {zugeordnet}")
    print(f"davon nicht eindeutig zuordenbar  : {nicht_zuordenbar}")
    print(
        f"Anfragen mit Zusatztreffer        : {len(mit_zusatz)} von {n} = {len(mit_zusatz) / n:.1%}  {mit_zusatz}"
    )
    print(f"Anfragen mit verlorenem Treffer   : {len(schlechter)}  {schlechter}")
    print()
    print("HINWEIS: Das ist eine HILFSauswertung. Sie ordnet nachträglich zu, was")
    print("die Schnittstelle heute nicht mitliefert. Für eine Freigabe zählt die")
    print("Messung über werte_aus.py — und die kann Bedingung 2 nicht prüfen,")
    print("solange ein Gedächtnis-Treffer keine Kennung auf seine Quellzeile trägt.")


if __name__ == "__main__":
    main()
