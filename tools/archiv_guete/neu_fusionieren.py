# ============================================================
#  FOREMAN — Goldset-Messung, Zwischenschritt: FUSION NACHBILDEN
#  Zweck: Baut aus EINZELQUELLEN-Laeufen (je ein `miss.py`-Lauf mit genau einer
#         Quelle) das fusionierte Ergebnis — mit der ECHTEN Fusionsfunktion des
#         Produkts, nicht mit einer Nachbildung.
#  Wozu das gut ist: Eine Aenderung an der Fusion laesst sich damit messen,
#         BEVOR sie ausgerollt ist. Die Einzelquellen-Listen haengen nicht an der
#         Fusion — `sources=note` liefert dieselbe Rangfolge, egal wie danach
#         zusammengefuehrt wird. Sie einmal zu erheben und lokal verschieden zu
#         fusionieren ist deshalb kein Behelf, sondern die saubere Trennung:
#         Erhebung gegen die Instanz, Rechnung gegen den Quelltext.
#  ABGESCHRIEBEN WIRD NICHT: `_fusioniere` kommt aus `foreman.archive.search`.
#         Eine zweite Fassung hier liefe frueher oder spaeter von der ersten weg,
#         und das Ergebnis saehe trotzdem plausibel aus.
#  Aufruf: python neu_fusionieren.py <ziel-lauf> <datei.json> [<datei.json> ...]
#          z.B. python neu_fusionieren.py v3_gedaechtnis \
#                   messung_q_note.json messung_q_maintenance.json \
#                   messung_q_alarm.json messung_q_memory.json
# ============================================================
from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

# Das Werkzeug liegt neben dem Anwendungscode, aber nicht darin — der Pfad wird
# einmal ergaenzt statt das Paket zu installieren.
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from foreman.archive.schemas import ArchiveHit, SourceType
from foreman.archive.search import _fusioniere

# Ersatz-Zeitpunkt, wenn ein Lauf noch ohne Zeitstempel erhoben wurde. Bewusst
# derselbe Wert wie im Produkt (`archive/search.py::_OHNE_ZEIT`): Ein Treffer
# ohne Zeit gehoert in einer zeitlich sortierten Liste nach HINTEN.
_OHNE_ZEIT = datetime(1970, 1, 1, tzinfo=UTC)


def _zu_treffer(roh: dict) -> ArchiveHit:
    zeit = roh.get("timestamp")
    return ArchiveHit(
        source_type=roh["source_type"],
        id=roh["id"],
        machine_id=roh.get("machine_id"),
        timestamp=datetime.fromisoformat(zeit) if zeit else _OHNE_ZEIT,
        excerpt=roh.get("excerpt", ""),
        detail=roh.get("detail") or {},
    )


def _lies(pfad: str) -> dict:
    with open(pfad, encoding="utf-8") as datei:
        daten = json.load(datei)
    quellen = daten.get("quellen") or []
    if len(quellen) != 1:
        raise SystemExit(
            f"❌ {pfad} wurde mit {len(quellen)} Quellen erhoben ({quellen}). "
            "Dieses Werkzeug braucht EINZELQUELLEN-Laeufe — aus einem bereits "
            "fusionierten Ergebnis laesst sich der quelleninterne Rang nicht "
            "zurueckgewinnen."
        )
    return daten


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("Aufruf: python neu_fusionieren.py <ziel-lauf> <datei.json> [...]")
    ziel_lauf = sys.argv[1]
    dateien = sys.argv[2:]

    laeufe = [_lies(p) for p in dateien]

    # Alle Laeufe muessen denselben Bewertungssatz und dieselbe Ausgabelaenge
    # tragen. Ohne diese Pruefung liesse sich ein Lauf gegen die alten Anfragen
    # mit einem gegen die neuen mischen — und das Ergebnis saehe aus wie eine
    # Messung, waere aber keine.
    anfragedateien = {lauf.get("anfragedatei") for lauf in laeufe}
    if len(anfragedateien) != 1:
        raise SystemExit(f"❌ Verschiedene Anfragedateien in den Laeufen: {anfragedateien}")
    ks = {lauf.get("k") for lauf in laeufe}
    if len(ks) != 1:
        raise SystemExit(f"❌ Verschiedene Ausgabelaengen in den Laeufen: {ks}")
    k = ks.pop()

    # Reihenfolge der Quellen wie im Produkt (`ALL_SOURCES`), nicht wie auf der
    # Kommandozeile: Bei gleichem Punktestand entscheidet sie mit, welcher
    # Treffer Vertreter eines zusammengefuehrten Vorgangs wird.
    reihenfolge: list[SourceType] = ["note", "maintenance", "alarm", "memory"]
    laeufe.sort(key=lambda lauf: reihenfolge.index(lauf["quellen"][0]))

    je_anfrage: dict[str, dict] = {}
    for lauf in laeufe:
        quelle = lauf["quellen"][0]
        for eintrag in lauf["laeufe"]:
            kennung = eintrag["anfrage_id"]
            zusammen = je_anfrage.setdefault(
                kennung,
                {
                    "anfrage_id": kennung,
                    "anfrage": eintrag["anfrage"],
                    "machine_id": eintrag.get("machine_id"),
                    "dauer_s": 0.0,
                    "fehler": None,
                    "_listen": [],
                },
            )
            zusammen["dauer_s"] = round(zusammen["dauer_s"] + (eintrag.get("dauer_s") or 0.0), 2)
            if eintrag.get("fehler"):
                # Ein Fehler in EINER Quelle macht die ganze Anfrage unbrauchbar:
                # Das fusionierte Ergebnis waere dann eine Liste ohne diese Quelle
                # und liesse sich von einem echten Ergebnis nicht unterscheiden.
                neuer = f"{quelle}: {eintrag['fehler']}"
                vorher = zusammen["fehler"]
                zusammen["fehler"] = f"{vorher} | {neuer}" if vorher else neuer
            zusammen["_listen"].append((quelle, [_zu_treffer(t) for t in eintrag["treffer"]]))

    ergebnis = {
        "lauf": ziel_lauf,
        "anfragedatei": anfragedateien.pop(),
        "basis": laeufe[0].get("basis"),
        "quellen": [lauf["quellen"][0] for lauf in laeufe],
        "k": k,
        "herkunft": {
            "verfahren": "lokal fusioniert aus Einzelquellen-Laeufen",
            "dateien": dateien,
            "fusion": "foreman.archive.search._fusioniere",
        },
        "laeufe": [],
    }

    for kennung in sorted(je_anfrage):
        zusammen = je_anfrage[kennung]
        treffer = _fusioniere(zusammen.pop("_listen"), k)
        zusammen["treffer"] = [
            {
                "rang": i + 1,
                "schluessel": f"{t.source_type}:{t.id}",
                "source_type": t.source_type,
                "id": t.id,
                "machine_id": t.machine_id,
                "timestamp": t.timestamp.isoformat(),
                "gefunden_von": list(t.gefunden_von),
                "excerpt": t.excerpt,
                "detail": t.detail,
            }
            for i, t in enumerate(treffer)
        ]
        ergebnis["laeufe"].append(zusammen)
        bestaetigt = sum(1 for t in treffer if len(t.gefunden_von) > 1)
        print(f"  {kennung:6s} {len(treffer):2d} Treffer, davon {bestaetigt} bestaetigt")

    pfad = f"messung_{ziel_lauf}.json"
    with open(pfad, "w", encoding="utf-8") as datei:
        json.dump(ergebnis, datei, ensure_ascii=False, indent=1)
    print(f"\n💾 {pfad} geschrieben ({len(ergebnis['laeufe'])} Anfragen)")


if __name__ == "__main__":
    main()
