# ============================================================
#  FOREMAN — api/routers/readings.py
#  Zweck: Batch-Aufnahme von Messwerten (POST /api/v1/readings), §4.
#  Architektur-Einordnung: Ingestion (Schicht 2). Schreibt den validierten Batch
#         über den geteilten COPY-Pfad (`ingestion.service.copy_readings`,
#         Research §3.4 — schnellster Massen-Schreibpfad, keine Einzel-Inserts).
#         Derselbe Schreibweg wird vom Simulations-/Protokoll-Adapter (F3) genutzt
#         — kein zweiter Reading-Schreibpfad.
#  Maschinen-Scope (§20.4): Ein Batch erreicht über seine Datenpunkte konkrete
#         Maschinen — auch das ist Zugriff. Die Auflösung Datenpunkt → Maschine
#         läuft EINMAL und dient beidem: der Prüfung davor und der Live-
#         Benachrichtigung danach.
# ============================================================
from __future__ import annotations

from datetime import UTC

import asyncpg
from fastapi import APIRouter, HTTPException, status

from foreman.api.deps import ResourceScopeDep, SessionDep
from foreman.ingestion.service import ReadingRow, copy_readings
from foreman.reads.queries import machines_for_data_points
from foreman.realtime.channels import ChangeSet
from foreman.realtime.notify import notify_changes
from foreman.schemas.readings import ReadingBatch, ReadingBatchResult

router = APIRouter(prefix="/readings", tags=["readings"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ReadingBatchResult)
async def ingest_readings(
    body: ReadingBatch, session: SessionDep, scope: ResourceScopeDep
) -> ReadingBatchResult:
    """Nimmt einen validierten Messwert-Batch auf und schreibt ihn per COPY.

    403, sobald der Batch einen Datenpunkt einer Maschine außerhalb des Ausschnitts
    enthält — alles oder nichts. Ein Batch, aus dem still die unerlaubten Zeilen
    fielen, meldete Erfolg über eine Aufnahme, die so nie stattgefunden hat.
    """
    # Die berührten Maschinen EINMAL auflösen: erst als Zugriffsprüfung, später als
    # Ziel der Live-Benachrichtigung. Zwei Auflösungen wären zwei Wahrheiten.
    data_point_ids = frozenset(r.data_point_id for r in body.readings)
    machines = (
        await machines_for_data_points(session, list(data_point_ids)) if data_point_ids else []
    )
    await scope.require_all(machines)

    # tz-naive Zeitstempel als UTC interpretieren (timestamptz erwartet tz-aware).
    rows: list[ReadingRow] = [
        (
            r.time if r.time.tzinfo is not None else r.time.replace(tzinfo=UTC),
            r.data_point_id,
            r.value,
            r.quality,
        )
        for r in body.readings
    ]

    try:
        written = await copy_readings(session, rows)
    except asyncpg.UniqueViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Doppelter (data_point_id, time)-Schlüssel im Batch oder Bestand",
        ) from exc
    except asyncpg.ForeignKeyViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unbekannter data_point_id im Batch",
        ) from exc
    except asyncpg.PostgresError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Batch konnte nicht geschrieben werden: {exc}",
        ) from exc

    # Live-Push (F5): ein NOTIFY pro Batch (Vorgabe 4) — transaktional auf den
    # Commit der Request-Session; der Hub debounct und lädt nach. Die berührten
    # Maschinen reisen mit, damit auch die lebende Karte (machine:{id}) + das Cockpit
    # (overview) nachrücken, nicht nur das Trend-Thema.
    if body.readings:
        await notify_changes(
            session,
            ChangeSet(
                machines=frozenset(machines),
                data_points=data_point_ids,
                kinds=frozenset({"reading"}),
            ),
        )
    return ReadingBatchResult(written=written)
