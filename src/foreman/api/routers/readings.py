# ============================================================
#  FOREMAN — api/routers/readings.py
#  Zweck: Batch-Aufnahme von Messwerten (POST /api/v1/readings), §4.
#  Architektur-Einordnung: Ingestion (Schicht 2). Schreibt den validierten Batch
#         über asyncpg-COPY in die readings-Hypertable (Research §3.4 — schnellster
#         Massen-Schreibpfad, keine Einzel-Inserts). Kein Protokoll-Adapter (F3).
# ============================================================
from __future__ import annotations

from datetime import UTC

import asyncpg
from fastapi import APIRouter, HTTPException, status

from foreman.api.deps import SessionDep
from foreman.schemas.readings import ReadingBatch, ReadingBatchResult

router = APIRouter(prefix="/readings", tags=["readings"])

# Spaltenreihenfolge des COPY-Streams (muss zur readings-Tabelle passen).
_COPY_COLUMNS = ["time", "data_point_id", "value", "quality"]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ReadingBatchResult)
async def ingest_readings(body: ReadingBatch, session: SessionDep) -> ReadingBatchResult:
    """Nimmt einen validierten Messwert-Batch auf und schreibt ihn per COPY."""
    # tz-naive Zeitstempel als UTC interpretieren (timestamptz erwartet tz-aware).
    rows = [
        (
            r.time if r.time.tzinfo is not None else r.time.replace(tzinfo=UTC),
            r.data_point_id,
            r.value,
            r.quality,
        )
        for r in body.readings
    ]

    # Rohe asyncpg-Verbindung der laufenden Session/Transaktion holen.
    sa_conn = await session.connection()
    raw = await sa_conn.get_raw_connection()
    asyncpg_conn = raw.driver_connection
    if asyncpg_conn is None:  # pragma: no cover — nur ohne asyncpg-Treiber möglich
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Keine asyncpg-Verbindung für COPY verfügbar",
        )

    try:
        await asyncpg_conn.copy_records_to_table(
            "readings", records=rows, columns=_COPY_COLUMNS
        )
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

    return ReadingBatchResult(written=len(rows))
