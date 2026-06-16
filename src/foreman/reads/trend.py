# ============================================================
#  FOREMAN — reads/trend.py
#  Zweck: Trend-Assemblierung des Read-Cores (F5) — der aggregierte readings_1m-
#         Verlauf eines Datenpunkts plus statisches Normalband (normal_min/
#         normal_max) und Metadaten. Geteilt von der HTTP-Trend-Route (Erstbild)
#         und dem WebSocket-Push (Snapshot beim Abo, danach Delta-Punkte). Zwei
#         Einstiege: über (machine_id, name) für die HTTP-Route, über
#         data_point_id für das WS-Thema `trend:{data_point_id}`.
#  CAGG-Aktualität: liest über reads.load_readings die Minuten-Aggregat-Sicht
#         readings_1m. Diese ist als real-time aggregation konfiguriert
#         (timescaledb.materialized_only = false) — der jüngste, noch nicht
#         materialisierte Bucket ist ohne Refresh sichtbar, sodass die Live-Kurve
#         dem Live-Puls nicht hinterherhinkt.
#  Eigenprofil-Overlay (F4): das zustandsspezifische Drift-Normalband ist NICHT
#         persistiert (gegateter Replay, reasoners/drift) und folgt als eigener
#         Schritt; dieser Trend trägt zunächst das statische Normalband, das
#         Transport-Feld `profile_band` bleibt dafür nullable.
#  Architektur-Einordnung: Read-Core (Schicht 2). Transport-neutral, gibt eine
#         reine dataclass zurück; HTTP/WS mappen sie auf ihren Vertrag.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import DataPoint
from foreman.reads.queries import (
    MAX_READING_POINTS,
    ReadingBucket,
    load_readings,
    resolve_data_point,
)


@dataclass(frozen=True)
class MachineTrend:
    """Aggregierter Sensortrend eines Datenpunkts plus statisches Normalband (F5)."""

    machine_id: int
    data_point_id: int
    data_point_name: str
    unit: str | None
    measurement_type: str | None
    normal_min: float | None
    normal_max: float | None
    points: tuple[ReadingBucket, ...]
    truncated: bool


def _assemble_trend(
    data_point: DataPoint, points: list[ReadingBucket], truncated: bool
) -> MachineTrend:
    """Setzt den Trend aus Datenpunkt-Metadaten + geladenen Punkten zusammen (rein)."""
    return MachineTrend(
        machine_id=data_point.machine_id,
        data_point_id=data_point.id,
        data_point_name=data_point.name,
        unit=data_point.unit,
        measurement_type=data_point.measurement_type,
        normal_min=data_point.normal_min,
        normal_max=data_point.normal_max,
        points=tuple(points),
        truncated=truncated,
    )


async def build_trend(
    session: AsyncSession,
    machine_id: int,
    data_point_name: str,
    *,
    start: datetime,
    end: datetime,
    limit: int = MAX_READING_POINTS,
) -> MachineTrend | None:
    """Baut den Trend eines Datenpunkts (per Name, auf die Maschine begrenzt).

    None, wenn der Datenpunkt an dieser Maschine nicht existiert.
    """
    data_point = await resolve_data_point(session, machine_id, data_point_name)
    if data_point is None:
        return None
    points, truncated = await load_readings(session, data_point.id, start, end, limit=limit)
    return _assemble_trend(data_point, points, truncated)


async def build_trend_by_id(
    session: AsyncSession,
    data_point_id: int,
    *,
    start: datetime,
    end: datetime,
    limit: int = MAX_READING_POINTS,
) -> MachineTrend | None:
    """Baut den Trend eines Datenpunkts per ID (für das WS-Thema trend:{id}).

    None, wenn der Datenpunkt nicht existiert.
    """
    data_point = await session.get(DataPoint, data_point_id)
    if data_point is None:
        return None
    points, truncated = await load_readings(session, data_point.id, start, end, limit=limit)
    return _assemble_trend(data_point, points, truncated)
