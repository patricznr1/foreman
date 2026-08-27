# ============================================================
#  FOREMAN — Goldset-Messung, Schritt 1 von 2: ERHEBEN
#  Zweck: Faehrt jede Goldset-Anfrage gegen die Archiv-Suche der laufenden
#         Instanz und legt die Trefferlisten ROH ab. Es wird hier NICHTS
#         bewertet und NICHTS gerechnet — die Auswertung (werte_aus.py) liest
#         ausschliesslich diese Dateien. Trennung, damit kein Zwischenergebnis
#         aus dem Gedaechtnis in die Kennzahl wandert.
#  Aufruf: python miss.py <lauf-name> [quelle,quelle,...]
#          z.B. python miss.py baseline note,maintenance,alarm
#               python miss.py mit_gedaechtnis note,maintenance,alarm,memory
# ============================================================
from __future__ import annotations

import http.cookiejar
import json
import os
import sys
import time
import urllib.parse
import urllib.request

BASIS = os.environ.get("FOREMAN_DEMO_URL", "http://localhost:3000")
EMAIL = os.environ.get("FOREMAN_DEMO_EMAIL", "")
# KEIN Vorgabewert: Ein Zugang gehört nicht in eine Datei, auch kein absichtlich
# offener. Wer misst, gibt ihn über die Umgebung mit.
PASSWORT = os.environ.get("FOREMAN_DEMO_PASSWORT", "")

ZEITGRENZE = 60


def lade_anfragen(pfad: str = "goldset_anfragen.yaml") -> tuple[list[dict], int]:
    """Minimaler Leser fuer die Anfrage-Datei (kein PyYAML noetig)."""
    anfragen: list[dict] = []
    k = 10
    aktuell: dict | None = None
    for zeile in open(pfad, encoding="utf-8"):
        roh = zeile.rstrip("\n")
        if roh.strip().startswith("#") or not roh.strip():
            continue
        if roh.startswith("k:"):
            k = int(roh.split(":", 1)[1].strip())
            continue
        if roh.lstrip().startswith("- id:"):
            if aktuell:
                anfragen.append(aktuell)
            aktuell = {"id": roh.split(":", 1)[1].strip()}
            continue
        if aktuell is None:
            continue
        for feld in ("anfrage", "machine_id", "absicht"):
            marke = f"{feld}:"
            if roh.strip().startswith(marke):
                wert = roh.strip()[len(marke) :].strip().strip('"')
                aktuell[feld] = int(wert) if feld == "machine_id" else wert
    if aktuell:
        anfragen.append(aktuell)
    return anfragen, k


def melde_an() -> urllib.request.OpenerDirector:
    if not EMAIL or not PASSWORT:
        raise SystemExit(
            "❌ FOREMAN_DEMO_EMAIL und FOREMAN_DEMO_PASSWORT müssen gesetzt sein "
            "(optional FOREMAN_DEMO_URL, sonst http://localhost:3000)."
        )
    jar = http.cookiejar.CookieJar()
    oeffner = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    nutzlast = json.dumps({"email": EMAIL, "password": PASSWORT}).encode()
    anfrage = urllib.request.Request(
        f"{BASIS}/api/session",
        data=nutzlast,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with oeffner.open(anfrage, timeout=ZEITGRENZE) as antwort:
        if antwort.status != 200:
            raise SystemExit(f"❌ Anmeldung fehlgeschlagen: HTTP {antwort.status}")
        profil = json.load(antwort)
    print(f"🔑 angemeldet als {profil['email']} (Rolle {profil['role']})")
    return oeffner


def suche(oeffner, frage: dict, quellen: list[str], k: int) -> tuple[list[dict], float, str | None]:
    parameter: list[tuple[str, str]] = [("q", frage["anfrage"]), ("k", str(k))]
    for quelle in quellen:
        parameter.append(("sources", quelle))
    if frage.get("machine_id") is not None:
        parameter.append(("machine_id", str(frage["machine_id"])))
    adresse = f"{BASIS}/api/v1/archive/search?" + urllib.parse.urlencode(parameter)
    begonnen = time.monotonic()
    try:
        with oeffner.open(adresse, timeout=ZEITGRENZE) as antwort:
            treffer = json.load(antwort)
        return treffer, time.monotonic() - begonnen, None
    except Exception as fehler:  # Fehler wird MITGESCHRIEBEN, nicht verschluckt
        return [], time.monotonic() - begonnen, f"{type(fehler).__name__}: {fehler}"


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Aufruf: python miss.py <lauf-name> [quelle,quelle,...]")
    lauf = sys.argv[1]
    quellen = (sys.argv[2] if len(sys.argv) > 2 else "note,maintenance,alarm").split(",")

    anfragen, k = lade_anfragen()
    print(f"📋 {len(anfragen)} Anfragen, k={k}, Quellen={quellen}")

    oeffner = melde_an()
    ergebnis = {
        "lauf": lauf,
        "basis": BASIS,
        "quellen": quellen,
        "k": k,
        "laeufe": [],
    }
    fehlerzahl = 0
    for frage in anfragen:
        treffer, dauer, fehler = suche(oeffner, frage, quellen, k)
        if fehler:
            fehlerzahl += 1
        ergebnis["laeufe"].append(
            {
                "anfrage_id": frage["id"],
                "anfrage": frage["anfrage"],
                "machine_id": frage.get("machine_id"),
                "dauer_s": round(dauer, 2),
                "fehler": fehler,
                "treffer": [
                    {
                        "rang": i + 1,
                        "schluessel": f"{t['source_type']}:{t['id']}",
                        "source_type": t["source_type"],
                        "id": t["id"],
                        "machine_id": t.get("machine_id"),
                        "excerpt": t.get("excerpt", ""),
                        "detail": t.get("detail") or {},
                    }
                    for i, t in enumerate(treffer)
                ],
            }
        )
        marke = "❌" if fehler else "✅"
        print(
            f"  {marke} {frage['id']:6s} {len(treffer):2d} Treffer  {dauer:5.2f}s  {frage['anfrage'][:45]}"
        )

    ziel = f"messung_{lauf}.json"
    json.dump(ergebnis, open(ziel, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"\n💾 {ziel} geschrieben — {fehlerzahl} Fehler von {len(anfragen)} Anfragen")
    if fehlerzahl:
        print(
            "⚠️  Fehlerhafte Anfragen stehen mit Fehlertext in der Datei und gehen NICHT als 'keine Treffer' durch."
        )


if __name__ == "__main__":
    main()
