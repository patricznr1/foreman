# ============================================================
#  FOREMAN — Goldset-Messung, Schritt 2 von 2: AUSWERTEN
#  Zweck: Rechnet Kennzahlen aus den ROHDATEIEN von miss.py gegen das Goldset.
#         Liest ausschliesslich Dateien — kein Wert stammt aus einem Zwischen-
#         schritt im Kopf. Vergleicht optional zwei Laeufe gegen die beiden
#         Freigabe-Schwellen aus GROUND_TRUTH §15.10.
#  Aufruf: python werte_aus.py messung_baseline.json [messung_vergleich.json]
# ============================================================
from __future__ import annotations

import json
import math
import sys

# Schwellen aus GROUND_TRUTH §15.10, Freigabe-Bedingung 1:
#   "auf keiner Anfrage geht ein zutreffender Treffer VERLOREN, auf >=30 % kommt
#    ein zusaetzlicher hinzu" (Fassung vom 27.08.2026, siehe unten)
ANTEIL_MIT_ZUSATZTREFFER_SOLL = 0.30


def _schluessel(treffer: dict) -> str:
    """Der Schluessel, gegen den das Goldset bewertet.

    Ein Treffer aus dem Gedaechtnis traegt seit dem 25.08.2026 den Rueckweg auf
    seine Quellzeile (`detail["quelle"]`, GROUND_TRUTH §15.10). Er wird HIER
    aufgeloest, damit die Bewertung ihn gegen dieselben Schluessel halten kann
    wie einen Treffer aus einer eigenen Quelle — ohne diese Aufloesung traegt
    jeder Gedaechtnis-Treffer `memory:0` und ist auf keinen Goldset-Schluessel
    abbildbar; die zweite Haelfte der Freigabe-Bedingung waere dann nicht
    messbar (C-060). Der Rueckweg kommt aus dem PRODUKTPFAD — die Antwort der
    Suche liefert ihn mit; hier wird nichts danebengerechnet.

    Fehlt er (Altbestand), bleibt es bei `memory:0`. Geraten wird nichts.
    """
    quelle = (treffer.get("detail") or {}).get("quelle")
    if isinstance(quelle, dict) and quelle.get("art") and quelle.get("id"):
        return f"{quelle['art']}:{quelle['id']}"
    return str(treffer["schluessel"])


def lade_goldset(pfad: str = "goldset.json") -> dict[str, dict[str, int]]:
    return json.load(open(pfad, encoding="utf-8"))


def dcg(stufen: list[int]) -> float:
    return sum(s / math.log2(i + 2) for i, s in enumerate(stufen))


def kennzahlen(treffer: list[dict], relevant: dict[str, int], k: int) -> dict:
    """Recall/Praezision/nDCG fuer EINE Anfrage. `relevant` bildet Schluessel auf Stufe (1|2) ab."""
    oben = treffer[:k]
    schluessel = [_schluessel(t) for t in oben]

    # EIN zutreffender Eintrag zaehlt EINMAL, auch wenn er mehrfach ausgeliefert
    # wird. Seit der Rueckweg aufgeloest wird (`_schluessel`), koennen zwei
    # verschiedene Erinnerungen auf DIESELBE Quellzeile zeigen — die
    # Zusammenfuehrung in der Suche entfernt Erinnerungen nur gegen eigene
    # Treffer, nicht untereinander. Ohne diese Entdoppelung stiege die
    # Trefferquote ueber 1,0 und die Rangguete ueber 1,0, ohne dass ein einziger
    # Eintrag mehr gefunden waere. Im Lauf vom 27.08.2026 trat der Fall nicht ein
    # (Dubletten ausschliesslich als `memory:0`, keine davon zutreffend) — er ist
    # hier abgefangen, BEVOR er eintritt.
    gesehen: set[str] = set()
    erstmals: list[str] = []  # Schluessel in Reihenfolge, Wiederholungen leer
    for s in schluessel:
        if s in gesehen:
            erstmals.append("")  # belegt einen Platz, bringt keine Information
        else:
            gesehen.add(s)
            erstmals.append(s)
    gefunden = [s for s in erstmals if s in relevant]

    # Recall: Anteil der relevanten Eintraege, die in den Top-k stehen.
    recall = len(gefunden) / len(relevant) if relevant else None
    # Praezision: Anteil der ausgelieferten PLAETZE, die einen zutreffenden
    # Eintrag ERSTMALS zeigen. Eine Wiederholung belegt einen Platz, ohne etwas
    # beizutragen — sie senkt die Praezision, und das ist richtig so.
    praezision = len(gefunden) / len(oben) if oben else None

    ist = dcg([relevant.get(s, 0) for s in erstmals])
    bestenfalls = dcg(sorted(relevant.values(), reverse=True)[:k])
    ndcg = (ist / bestenfalls) if bestenfalls > 0 else None

    return {
        "treffer_gesamt": len(oben),
        "davon_relevant": len(gefunden),
        "relevante_im_bestand": len(relevant),
        "recall": recall,
        "praezision": praezision,
        "ndcg": ndcg,
        "gefundene_schluessel": gefunden,
        "alle_schluessel": schluessel,
    }


def werte_lauf(pfad: str, goldset: dict) -> dict:
    roh = json.load(open(pfad, encoding="utf-8"))
    k = roh["k"]
    je_anfrage = {}
    for lauf in roh["laeufe"]:
        aid = lauf["anfrage_id"]
        if lauf.get("fehler"):
            # Ein Fehler ist KEIN Nullergebnis. Er wird ausgewiesen, nicht verrechnet.
            je_anfrage[aid] = {"fehler": lauf["fehler"], "anfrage": lauf["anfrage"]}
            continue
        z = kennzahlen(lauf["treffer"], goldset.get(aid, {}), k)
        z["anfrage"] = lauf["anfrage"]
        z["dauer_s"] = lauf["dauer_s"]
        je_anfrage[aid] = z
    return {
        "pfad": pfad,
        "lauf": roh["lauf"],
        "quellen": roh["quellen"],
        "k": k,
        "je_anfrage": je_anfrage,
    }


def mittel(werte: list) -> float | None:
    echte = [w for w in werte if w is not None]
    return sum(echte) / len(echte) if echte else None


def zeige(a: dict) -> None:
    print(f"\n{'=' * 78}")
    print(f"LAUF: {a['lauf']}  |  Quellen: {','.join(a['quellen'])}  |  k={a['k']}")
    print("=" * 78)
    print(
        f"{'ID':6s} {'Tref':>4s} {'rel':>4s} {'/Best':>6s} {'Recall':>7s} {'Praez':>7s} {'nDCG':>7s}  Anfrage"
    )
    print("-" * 78)
    for aid, z in a["je_anfrage"].items():
        if "fehler" in z:
            print(f"{aid:6s}  FEHLER: {z['fehler']}")
            continue

        def f(x):
            return f"{x:.2f}" if x is not None else "   -"

        print(
            f"{aid:6s} {z['treffer_gesamt']:4d} {z['davon_relevant']:4d} "
            f"{z['relevante_im_bestand']:6d} {f(z['recall']):>7s} {f(z['praezision']):>7s} "
            f"{f(z['ndcg']):>7s}  {z['anfrage'][:30]}"
        )
    gueltig = [z for z in a["je_anfrage"].values() if "fehler" not in z]
    print("-" * 78)
    print(
        f"MITTEL  Recall {mittel([z['recall'] for z in gueltig]) or 0:.3f} · "
        f"Praezision {mittel([z['praezision'] for z in gueltig]) or 0:.3f} · "
        f"nDCG {mittel([z['ndcg'] for z in gueltig]) or 0:.3f}"
    )
    ohne = [
        aid for aid, z in a["je_anfrage"].items() if "fehler" not in z and z["davon_relevant"] == 0
    ]
    print(f"Anfragen ohne EINEN relevanten Treffer: {len(ohne)} von {len(gueltig)}  {ohne}")


def vergleiche(basis: dict, neu: dict) -> None:
    print(f"\n{'=' * 78}")
    print(f"VERGLEICH  {basis['lauf']}  ->  {neu['lauf']}")
    print("Schwellen (GROUND_TRUTH §15.10, Freigabe-Bedingung 1, Fassung vom 27.08.2026):")
    print("  (1) auf KEINER Anfrage geht ein zutreffender Treffer VERLOREN")
    print(
        f"  (2) auf >= {ANTEIL_MIT_ZUSATZTREFFER_SOLL:.0%} der Anfragen ein ZUSAETZLICHER relevanter Treffer"
    )
    print("=" * 78)

    schlechter, mit_zusatz, unveraendert = [], [], []
    print(f"{'ID':6s} {'Recall':>16s} {'nDCG':>16s}  neue relevante Treffer")
    print("-" * 78)
    for aid, alt in basis["je_anfrage"].items():
        jung = neu["je_anfrage"].get(aid)
        if jung is None or "fehler" in alt or "fehler" in jung:
            print(f"{aid:6s}  nicht vergleichbar (Fehler in einem der Laeufe)")
            continue
        neue = [s for s in jung["gefundene_schluessel"] if s not in alt["gefundene_schluessel"]]
        verlorene = [
            s for s in alt["gefundene_schluessel"] if s not in jung["gefundene_schluessel"]
        ]

        r_alt, r_neu = alt["recall"], jung["recall"]
        n_alt, n_neu = alt["ndcg"], jung["ndcg"]

        # "Schlechter" heisst: ein zutreffender Treffer ist VERLOREN gegangen.
        #
        # PRAEZISIERT am 27.08.2026 (GROUND_TRUTH §15.10, Register C-064): Vorher
        # zaehlte auch eine gefallene Rangguete. Damit galt eine Anfrage schon
        # dann als verschlechtert, wenn ein zutreffender Treffer eine Position
        # nach hinten rutschte — auch wenn keiner verloren ging und MEHR
        # gefunden wurde. Gemessen traf das G-11: Trefferquote 0,50 -> 0,67,
        # kein Verlust, und trotzdem "schlechter". Eine Bedingung, die eine
        # Verbesserung als Verschlechterung ausweist, misst nicht, was sie soll.
        #
        # Die Rangguete wird weiterhin erhoben und ausgewiesen — sie ist eine
        # Kennzahl, keine Schwelle.
        #
        # DIE AENDERUNG IST FUER DAS ERGEBNIS ENTSCHEIDEND: Auf demselben Lauf
        # zaehlt die alte Lesart SIEBEN von 18 Anfragen als verschlechtert, die
        # neue KEINE. Wer die Praezisierung nicht teilt, liest den Lauf anders.
        ist_schlechter = bool(verlorene)
        if ist_schlechter:
            schlechter.append(aid)
        if neue:
            mit_zusatz.append(aid)
        if not neue and not verlorene:
            unveraendert.append(aid)

        def pf(a, b):
            if a is None or b is None:
                return "      -  ->      -"
            pfeil = "↑" if b > a + 1e-9 else ("↓" if b < a - 1e-9 else "=")
            return f"{a:6.2f} -> {b:6.2f} {pfeil}"

        hinweis = ", ".join(neue) if neue else ""
        if verlorene:
            hinweis += f"   VERLOREN: {', '.join(verlorene)}"
        print(f"{aid:6s} {pf(r_alt, r_neu):>16s} {pf(n_alt, n_neu):>16s}  {hinweis}")

    gesamt = len([a for a in basis["je_anfrage"] if a in neu["je_anfrage"]])
    anteil = len(mit_zusatz) / gesamt if gesamt else 0.0
    print("-" * 78)
    print(f"Anfragen gesamt vergleichbar : {gesamt}")
    print(f"davon schlechter geworden    : {len(schlechter)}  {schlechter}")
    print(f"davon mit Zusatztreffer      : {len(mit_zusatz)} = {anteil:.1%}  {mit_zusatz}")
    print(f"davon unveraendert           : {len(unveraendert)}")
    print()
    b1 = len(schlechter) == 0
    b2 = anteil >= ANTEIL_MIT_ZUSATZTREFFER_SOLL
    print(f"  Bedingung (1) kein verlorener Treffer: {'ERFUELLT' if b1 else 'NICHT ERFUELLT'}")
    print(
        f"  Bedingung (2) >= {ANTEIL_MIT_ZUSATZTREFFER_SOLL:.0%} Zusatztreffer  : {'ERFUELLT' if b2 else 'NICHT ERFUELLT'} ({anteil:.1%})"
    )
    print(f"\n  FREIGABE-BEDINGUNG 1 INSGESAMT: {'ERFUELLT' if (b1 and b2) else 'NICHT ERFUELLT'}")


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Aufruf: python werte_aus.py <messung.json> [<vergleich.json>]")
    goldset = lade_goldset()
    basis = werte_lauf(sys.argv[1], goldset)
    zeige(basis)
    if len(sys.argv) > 2:
        neu = werte_lauf(sys.argv[2], goldset)
        zeige(neu)
        vergleiche(basis, neu)


if __name__ == "__main__":
    main()
