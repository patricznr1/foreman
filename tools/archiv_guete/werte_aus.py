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


def lade_beurteilte(goldset_pfad: str) -> dict[str, dict[str, int]] | None:
    """Die BEURTEILTE Menge zum Bewertungssatz — oder None, wenn es sie nicht gibt.

    Das Goldset fuehrt nur die ZUTREFFENDEN Eintraege. Es kann deshalb nicht
    ausdruecken, was ein Beurteiler gesehen und als nicht zutreffend eingestuft
    hat — und genau dieser Unterschied traegt die Verzerrungskorrektur: Ein
    Eintrag, den NIEMAND beurteilt hat, zaehlt in der gewoehnlichen Rechnung als
    nicht zutreffend. Jede neue Variante bringt solche Eintraege mit und wird
    dafuer bestraft (Buettcher et al., SIGIR 2007: im Mittel rund zwei
    Rangplaetze, in Einzelfaellen zwoelf bis vierzehn).

    Erzeugt wird die Datei von `baue_goldset_v3.py`. Fehlt sie, wird die
    verdichtete Rangguete NICHT gerechnet und auch nicht geschaetzt — eine Zahl,
    die so tut, als waere die Verzerrung behandelt, ist schlimmer als keine.
    """
    pfad = goldset_pfad.replace("goldset", "beurteilt", 1)
    if pfad == goldset_pfad:
        return None
    try:
        with open(pfad, encoding="utf-8") as datei:
            return json.load(datei)
    except FileNotFoundError:
        return None


def dcg(stufen: list[int]) -> float:
    return sum(s / math.log2(i + 2) for i, s in enumerate(stufen))


# Ab dieser Anzahl Anfragen wird der Permutationstest nicht mehr vollstaendig
# aufgezaehlt (2^n Vorzeichen-Belegungen), sondern deterministisch gezogen.
_EXAKT_BIS = 16
_ZIEHUNGEN = 200_000


def permutationstest(differenzen: list[float]) -> tuple[float, bool] | None:
    """Zweiseitiger gepaarter Permutationstest ueber die Vorzeichen. → (p, exakt?)

    WARUM DIESER TEST: Urbano, Lima & Hanjalic (SIGIR 2019, arXiv:1905.11096)
    haben Typ-I/II/III-Fehler empirisch verglichen. t-Test und Permutationstest
    halten alpha = 0,05 korrekt ein (0,05 / 0,05), Bootstrap-Shift liegt bei
    0,059, Wilcoxon und Vorzeichentest sind systematisch verzerrt. Ihre
    Empfehlung woertlich: t-Test fuer Hypothesen zur mittleren Effektivitaet,
    Permutationstest sonst; Bootstrap-Shift und Wilcoxon aufgeben.

    Der Permutationstest braucht keine Verteilungsannahme, und bei zehn Anfragen
    sind alle 2^10 = 1024 Belegungen aufzaehlbar — es gibt hier also gar keinen
    Grund fuer eine Naeherung.

    WAS ER NICHT LEISTET: Bei zehn Anfragen ist die Aussagekraft gering. Dincer
    (2013) rechnet fuer TREC-Daten 10 bis 722 Topics je Systempaar fuer 95 %
    Konfidenz, im Mittel rund 50 bei einer Differenz >= 0,035. Ein p-Wert ueber
    0,05 heisst hier "nicht gezeigt", nicht "kein Unterschied".
    """
    echte = [d for d in differenzen if d is not None]
    if not echte:
        return None
    n = len(echte)
    beobachtet = abs(sum(echte))

    if n <= _EXAKT_BIS:
        mindestens_so_gross = 0
        for muster in range(1 << n):
            summe = sum(d if (muster >> i) & 1 else -d for i, d in enumerate(echte))
            if abs(summe) >= beobachtet - 1e-12:
                mindestens_so_gross += 1
        return mindestens_so_gross / (1 << n), True

    # Deterministisch gezogen (fester Startwert): Zwei Laeufe ueber dieselben
    # Daten muessen denselben p-Wert liefern, sonst ist die Zahl nicht zitierbar.
    import random

    wuerfel = random.Random(0)
    mindestens_so_gross = 0
    for _ in range(_ZIEHUNGEN):
        summe = sum(d if wuerfel.getrandbits(1) else -d for d in echte)
        if abs(summe) >= beobachtet - 1e-12:
            mindestens_so_gross += 1
    return mindestens_so_gross / _ZIEHUNGEN, False


def kennzahlen(
    treffer: list[dict],
    relevant: dict[str, int],
    k: int,
    beurteilt: dict[str, int] | None = None,
) -> dict:
    """Recall/Praezision/nDCG fuer EINE Anfrage. `relevant` bildet Schluessel auf Stufe (1|2) ab.

    `beurteilt` ist die vollstaendige beurteilte Menge dieser Anfrage (auch die
    Nullen). Liegt sie vor, wird zusaetzlich die VERDICHTETE Rangguete gerechnet
    (Sakai 2007): Eintraege, die niemand beurteilt hat, werden aus der Liste
    ENTFERNT, statt als nicht zutreffend zu zaehlen.
    """
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

    # VERDICHTETE Rangguete (Sakai 2007): dieselbe Rechnung, aber ueber eine
    # Liste, aus der die UNBEURTEILTEN Eintraege entfernt sind. Die Ideallinie
    # (Nenner) bleibt dieselbe — verglichen wird gegen das Beste, was im Bestand
    # moeglich waere, nicht gegen das Beste unter den Beurteilten.
    #
    # Wiederholungen fallen dabei mit heraus (sie stehen als "" in `erstmals`).
    # Das ist vertretbar, seit die Fusion auf den Vorgang zusammenfuehrt und
    # Wiederholungen gar nicht mehr entstehen; die gewoehnliche Rangguete
    # bestraft sie weiterhin.
    if beurteilt is None:
        ndcg_verdichtet = None
        unbeurteilt = None
    else:
        verdichtet = [s for s in erstmals if s in beurteilt]
        unbeurteilt = len([s for s in erstmals if s and s not in beurteilt])
        ist_v = dcg([relevant.get(s, 0) for s in verdichtet])
        ndcg_verdichtet = (ist_v / bestenfalls) if bestenfalls > 0 else None

    return {
        "treffer_gesamt": len(oben),
        "davon_relevant": len(gefunden),
        "relevante_im_bestand": len(relevant),
        "recall": recall,
        "praezision": praezision,
        "ndcg": ndcg,
        "ndcg_verdichtet": ndcg_verdichtet,
        "unbeurteilt": unbeurteilt,
        "gefundene_schluessel": gefunden,
        "alle_schluessel": schluessel,
    }


def pruefe_goldset(goldset: dict, pfad: str) -> None:
    """Weist einen Bewertungssatz ohne einen einzigen relevanten Eintrag ab.

    WARUM ABWEISEN STATT RECHNEN (Befund 27.08.2026): Ein Lauf gegen das falsche
    Goldset findet keinen passenden Schluessel, alle Kennzahlen werden null — und
    das Ergebnis sieht aus wie ein vernichtendes Urteil ueber die Suche. Genau so
    passiert, als der Goldset-Pfad noch fest verdrahtet war und ein Lauf gegen
    den neuen Bestand stillschweigend die alten Urteile nahm.

    Ein Aufbaufehler, der sich als Messergebnis liest, ist schlimmer als ein
    Absturz: Er wird geglaubt.
    """
    if not any(goldset.values()):
        raise SystemExit(f"❌ {pfad}: kein einziger relevanter Eintrag — falsches Goldset?")


def werte_lauf(pfad: str, goldset: dict, beurteilte: dict | None = None) -> dict:
    roh = json.load(open(pfad, encoding="utf-8"))
    k = roh["k"]
    je_anfrage = {}
    for lauf in roh["laeufe"]:
        aid = lauf["anfrage_id"]
        if lauf.get("fehler"):
            # Ein Fehler ist KEIN Nullergebnis. Er wird ausgewiesen, nicht verrechnet.
            je_anfrage[aid] = {"fehler": lauf["fehler"], "anfrage": lauf["anfrage"]}
            continue
        z = kennzahlen(
            lauf["treffer"],
            goldset.get(aid, {}),
            k,
            (beurteilte or {}).get(aid) if beurteilte is not None else None,
        )
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
    # Die VERDICHTETE Rangguete steht daneben, nicht anstelle: Sie behandelt die
    # Pool-Verzerrung, aber sie ist gegenueber der gewoehnlichen nach oben
    # verzerrt, weil sie unbeurteilte Eintraege gratis aus der Liste nimmt.
    # Beide Zahlen nebeneinander sagen mehr als eine allein.
    verdichtet = mittel([z.get("ndcg_verdichtet") for z in gueltig])
    if verdichtet is not None:
        unbeurteilt = sum(z.get("unbeurteilt") or 0 for z in gueltig)
        plaetze = sum(z["treffer_gesamt"] for z in gueltig)
        print(
            f"        nDCG verdichtet {verdichtet:.3f} "
            f"(unbeurteilt: {unbeurteilt} von {plaetze} Plaetzen)"
        )
    ohne = [
        aid for aid, z in a["je_anfrage"].items() if "fehler" not in z and z["davon_relevant"] == 0
    ]
    print(f"Anfragen ohne EINEN relevanten Treffer: {len(ohne)} von {len(gueltig)}  {ohne}")


def zeige_permutationstest(differenzen: dict[str, list[float]]) -> None:
    """Traegt der Unterschied? — gepaarter Permutationstest je Kennzahl."""
    print("\n" + "-" * 78)
    print("TRAEGT DER UNTERSCHIED? (gepaarter Permutationstest, zweiseitig)")
    for name, werte in differenzen.items():
        ergebnis = permutationstest(werte)
        if ergebnis is None:
            print(f"  {name:16s} keine vergleichbaren Paare")
            continue
        p_wert, exakt = ergebnis
        mittlere = sum(werte) / len(werte)
        art = "exakt" if exakt else f"gezogen, {_ZIEHUNGEN}"
        print(
            f"  {name:16s} n={len(werte):2d}  mittlere Differenz {mittlere:+.3f}  "
            f"p={p_wert:.3f} ({art})"
        )
    print(
        "  Lesehilfe: p > 0,05 heisst NICHT GEZEIGT, nicht 'kein Unterschied'. Bei zehn\n"
        "  Anfragen reicht die Erhebung fuer eine Richtungsaussage, nicht fuer eine\n"
        "  Kennzahl mit Vertrauensbereich (Dincer 2013: 10 bis 722 Topics je Systempaar).\n"
        "  Die Freigabe-Bedingung oben haengt NICHT an diesem Wert — sie zaehlt verlorene\n"
        "  und gewonnene Treffer, und das ist eine andere Frage als die nach dem Mittel."
    )


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
    # Paarweise Differenzen je Anfrage — die Grundlage des Permutationstests
    # unten. Gesammelt wird HIER, wo die Paare ohnehin gebildet werden; ein
    # zweiter Durchlauf koennte anders paaren, ohne dass es auffiele.
    differenzen: dict[str, list[float]] = {"recall": [], "ndcg": [], "ndcg_verdichtet": []}
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

        for name in differenzen:
            a_wert, b_wert = alt.get(name), jung.get(name)
            if a_wert is not None and b_wert is not None:
                differenzen[name].append(b_wert - a_wert)

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

    zeige_permutationstest(differenzen)


def main() -> None:
    # DER BEWERTUNGSSATZ IST PFLICHT UND STEHT IMMER ZULETZT.
    #
    # Er war bis zum 27.08.2026 waehlbar MIT VORGABE `goldset.json` — und genau
    # diese Vorgabe hat an einem Tag zweimal zugeschlagen: Ein Lauf gegen den
    # neuen Bestand rechnete stillschweigend gegen die ALTEN Urteile, kein
    # Schluessel passte, alle Kennzahlen wurden null. Das las sich wie ein
    # vernichtendes Urteil ueber die Suche statt wie ein Verdrahtungsfehler.
    #
    # Waehlbar-mit-Vorgabe war der halbe Schritt: Wer den Pfad vergisst, bekommt
    # weiterhin ein Ergebnis, nur das falsche. Ohne Vorgabe kann der Fehler nicht
    # mehr eintreten. Die Zahl der Argumente entscheidet, ob verglichen wird —
    # damit braucht es keine Schalter und keine Reihenfolge zum Merken:
    #   werte_aus.py <messung.json> <goldset.json>
    #   werte_aus.py <messung.json> <vergleich.json> <goldset.json>
    if len(sys.argv) not in (3, 4):
        raise SystemExit(
            "Aufruf: python werte_aus.py <messung.json> [<vergleich.json>] <goldset.json>\n"
            "        Der Bewertungssatz steht IMMER zuletzt und ist Pflicht."
        )
    goldset_pfad = sys.argv[-1]
    messungen = sys.argv[1:-1]
    # AUFBAU-KONTROLLE gegen den Dreher: Eine Rohdatei als Bewertungssatz
    # uebergeben ergaebe wieder null passende Schluessel — dieselbe Klasse.
    if "messung" in goldset_pfad:
        raise SystemExit(
            f"❌ {goldset_pfad} sieht nach einer Rohdatei aus, nicht nach einem "
            "Bewertungssatz. Der Bewertungssatz steht ZULETZT."
        )
    goldset = lade_goldset(goldset_pfad)

    pruefe_goldset(goldset, goldset_pfad)

    beurteilte = lade_beurteilte(goldset_pfad)
    if beurteilte is None:
        print(
            "⚠️  Keine beurteilte Menge gefunden — die VERDICHTETE Rangguete bleibt leer.\n"
            "   Ohne sie ist nicht unterscheidbar, ob ein Eintrag als nicht zutreffend\n"
            "   BEURTEILT oder gar nicht ANGESEHEN wurde.\n"
            "   Erzeugen mit: python baue_goldset_v3.py --schreiben"
        )

    basis = werte_lauf(messungen[0], goldset, beurteilte)
    zeige(basis)
    if len(messungen) > 1:
        neu = werte_lauf(messungen[1], goldset, beurteilte)
        zeige(neu)
        vergleiche(basis, neu)


if __name__ == "__main__":
    main()
