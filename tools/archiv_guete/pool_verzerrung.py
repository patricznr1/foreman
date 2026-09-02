#!/usr/bin/env python3
# ============================================================
#  FOREMAN — tools/archiv_guete/pool_verzerrung.py
#  Zweck: Zaehlt aus, wie oft ein ausgelieferter Platz BEURTEILT ist — getrennt
#         danach, welche Quelle ihn gefunden hat.
#  Warum das gebraucht wird: Ein Platz, den niemand beurteilt hat, zaehlt in
#         Trefferquote und einfacher Rangguete als NICHT zutreffend
#         (werte_aus.lade_beurteilte, dort ausfuehrlich begruendet). Wenn nun
#         ausgerechnet die Treffer, die eine NEUE Quelle allein beisteuert,
#         seltener beurteilt sind als die der alten, wird die neue Quelle
#         systematisch schlechter gemessen als sie ist — die Pool-Verzerrung,
#         die baue_goldset_v3.py im Kopf zitiert (Buettcher et al., SIGIR 2007).
#         Der Effekt ist keine Vermutung, er ist auszaehlbar. Genau das tut das
#         Werkzeug hier: Es beziffert, wie schief der Massstab liegt.
#  Was es NICHT tut: urteilen. Es sagt, welche Paare einem Beurteiler vorgelegt
#         werden muessen — den Bogen dafuer baut baue_urteilsbogen.py.
#  Aufruf: python pool_verzerrung.py <messung.json> [<messung.json> ...]
# ============================================================
from __future__ import annotations

import json
import sys
from pathlib import Path

HIER = Path(__file__).resolve().parent
sys.path.insert(0, str(HIER))

# Der Vorgangsschluessel kommt aus der Auswertung, statt hier ein zweites Mal
# gebaut zu werden: Zwei Fassungen derselben Regel laufen auseinander, und beide
# sehen plausibel aus. Weicht die Zaehlung hier von der dortigen ab, waere nicht
# zu sagen, welche recht hat.
from werte_aus import _schluessel  # noqa: E402

GOLDSET = HIER / "goldset_v3.json"
BEURTEILT = HIER / "beurteilt_v3.json"


def _quote(teil: int, ganz: int) -> str:
    return f"{teil}/{ganz} ({teil / ganz:.0%})" if ganz else f"{teil}/0 (—)"


def werte_aus_lauf(pfad: Path, goldset: dict, beurteilt: dict) -> dict:
    """Zaehlt die Plaetze eines Laufs nach Herkunft und Beurteilungsstand.

    `gefunden_von == ["memory"]` ist die tragende Unterscheidung: Nur diese
    Plaetze verdankt die Ausgabe ALLEIN der vierten Quelle. Ein Platz, den auch
    eine eigene Quelle gefunden hat, war schon im alten Pool und ist deshalb
    beurteilt — er kann die Verzerrung gar nicht zeigen.
    """
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    zahlen = {
        "exklusiv": [0, 0, 0],  # gesamt, beurteilt, zutreffend
        "eigen": [0, 0, 0],
    }
    offen: list[tuple[str, str]] = []
    for lauf in daten["laeufe"]:
        if lauf.get("fehler"):
            continue
        aid = lauf["anfrage_id"]
        for treffer in lauf["treffer"]:
            s = _schluessel(treffer)
            gruppe = "exklusiv" if treffer.get("gefunden_von") == ["memory"] else "eigen"
            zahlen[gruppe][0] += 1
            if s in beurteilt.get(aid, {}):
                zahlen[gruppe][1] += 1
            else:
                offen.append((aid, s))
            if goldset.get(aid, {}).get(s, 0) > 0:
                zahlen[gruppe][2] += 1
    return {"zahlen": zahlen, "offen": offen, "lauf": daten.get("lauf", pfad.stem)}


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Aufruf: python pool_verzerrung.py <messung.json> [...]")
    goldset = json.loads(GOLDSET.read_text(encoding="utf-8"))
    beurteilt = json.loads(BEURTEILT.read_text(encoding="utf-8"))

    for arg in sys.argv[1:]:
        e = werte_aus_lauf(Path(arg), goldset, beurteilt)
        exkl, eigen = e["zahlen"]["exklusiv"], e["zahlen"]["eigen"]
        print(f"\n📊 {e['lauf']}")
        print(
            f"   nur vom Gedaechtnis : beurteilt {_quote(exkl[1], exkl[0])}"
            f" — davon zutreffend {exkl[2]}"
        )
        print(
            f"   von eigenen Quellen : beurteilt {_quote(eigen[1], eigen[0])}"
            f" — davon zutreffend {eigen[2]}"
        )
        if exkl[0] and eigen[0]:
            a, b = exkl[1] / exkl[0], eigen[1] / eigen[0]
            # Der Vergleich ist der ganze Punkt: Eine niedrige Quote allein sagt
            # nichts — erst der Abstand zur alten Quelle zeigt, dass der Massstab
            # die neue benachteiligt und nicht einfach grob ist.
            print(f"   ➜ Abstand: {b - a:+.0%} zulasten der vierten Quelle")
        print(
            f"   unbeurteilte Plaetze: {len(e['offen'])}"
            f" — Bogen dafuer: python baue_urteilsbogen.py goldset_v3.json {arg}"
        )


if __name__ == "__main__":
    main()
