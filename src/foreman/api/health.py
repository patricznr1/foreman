# ============================================================
#  FOREMAN — api/health.py
#  Zweck: Zwei getrennte Sonden, §4. GET /health beantwortet, ob der Prozess
#         lebt; GET /readyz beantwortet, ob er arbeiten kann. Beide ohne Auth.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2).
#  Warum getrennt: Eine Lebendigkeitssonde soll NICHT von der Datenbank abhängen,
#         sonst startet ein Neustart-Karussell, sobald die Datenbank kurz weg ist —
#         der Prozess ist ja gesund, ihm fehlt nur die Gegenstelle. Eine
#         Bereitschaftssonde muss genau davon abhängen, sonst meldet sie „bereit",
#         während jede Anfrage in einen Fehler läuft. Beides in eine Sonde zu legen
#         heißt, sich für den einen oder den anderen Fehler zu entscheiden.
# ============================================================
from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from foreman.api.deps import SessionDep
from foreman.logging_setup import ERROR, get_logger

router = APIRouter(tags=["health"])
logger = get_logger("foreman.api.health")


@router.get("/health")
async def health() -> dict[str, str]:
    """Lebendigkeit: 200, solange der Prozess Anfragen beantwortet.

    Bewusst ohne Datenbank-Zugriff. Wer hier eine Abhängigkeit prüft, lässt den
    Orchestrierer einen gesunden Prozess töten, weil eine andere Komponente
    ausgefallen ist — und der Neustart behebt nichts, weil der Prozess nie das
    Problem war.
    """
    return {"status": "ok", "service": "foreman"}


@router.get("/readyz")
async def readyz(session: SessionDep) -> JSONResponse:
    """Bereitschaft: 200 nur, wenn die Datenbank antwortet — sonst 503.

    Geprüft wird mit einem echten Umlauf, nicht mit dem Zustand des
    Verbindungspools: Ein Pool kann Verbindungen führen, die längst tot sind, und
    genau dieser Fall soll hier auffallen.

    Die Antwort nennt keinen Grund. Der steht im Log, wo der Betreiber ihn findet;
    nach außen ginge sonst der Zustand der Infrastruktur heraus (§8, wie bei den
    Gateway-Fehlern). 503 statt 500, weil das ein bekannter Betriebszustand ist
    und keine Störung der Anwendung.

    Die Konfiguration wird hier NICHT erneut geprüft: Ein Prozess mit unsicherem
    Geheimnis oder ohne benannte Umgebung startet gar nicht erst (config.py,
    `require_secure_secrets` und `_umgebung_muss_benannt_sein`). Was den Start
    verhindert, kann zur Laufzeit nicht mehr fehlen.
    """
    try:
        # ORM-Ausnahme: Geprüft wird die Verbindung, nicht ein Datenbestand. `SELECT 1`
        # berührt keine Tabelle und keine Abbildung — es gibt hier nichts, was das ORM
        # ausdrücken könnte. Eine echte Abfrage stattdessen zu fahren würde die Sonde
        # an ein Schema binden und bei jeder Migration mitwandern müssen.
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.exception("%s Bereitschaftsprüfung fehlgeschlagen: Datenbank antwortet nicht", ERROR)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "unavailable", "service": "foreman"},
        )
    return JSONResponse(content={"status": "ready", "service": "foreman"})
