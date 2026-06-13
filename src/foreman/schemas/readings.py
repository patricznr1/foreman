# ============================================================
#  FOREMAN — schemas/readings.py
#  Zweck: Batch-Schema für die Messwert-Aufnahme (POST /api/v1/readings).
#  Architektur-Einordnung: Ingestion-Vertrag (Schicht 2). Der Batch wird über
#         asyncpg-COPY in die readings-Hypertable geschrieben (Research §3.4).
# ============================================================
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

# Obergrenze gegen unbegrenzten Verbrauch (Eingabe-Validierung); großzügig
# für COPY-Batches, aber endlich.
MAX_BATCH_SIZE = 100_000


class ReadingIn(BaseModel):
    """Ein einzelner Messwert. value Pflicht, quality optional (smallint)."""

    data_point_id: int
    time: datetime
    value: float
    quality: int | None = None


class ReadingBatch(BaseModel):
    """Validierter Batch von Messwerten."""

    readings: list[ReadingIn] = Field(min_length=1, max_length=MAX_BATCH_SIZE)


class ReadingBatchResult(BaseModel):
    """Ergebnis der Batch-Aufnahme."""

    written: int
