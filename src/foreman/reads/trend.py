# ============================================================
#  FOREMAN — reads/trend.py
#  Zweck: Trend-Assemblierung des Read-Cores (F5) — der aggregierte readings_1m-
#         Verlauf eines Datenpunkts plus statisches Normalband (normal_min/
#         normal_max) UND das zustandsspezifische Eigenprofil-Band (F4). Geteilt
#         von der HTTP-Trend-Route (Erstbild) und dem WebSocket-Push (Snapshot
#         beim Abo, danach Delta-Punkte). Zwei Einstiege: über (machine_id, name)
#         für die HTTP-Route, über data_point_id für das WS-Thema `trend:{id}`.
#  CAGG-Aktualität: liest über reads.load_readings die Minuten-Aggregat-Sicht
#         readings_1m. Diese ist als real-time aggregation konfiguriert
#         (timescaledb.materialized_only = false) — der jüngste, noch nicht
#         materialisierte Bucket ist ohne Refresh sichtbar, sodass die Live-Kurve
#         dem Live-Puls nicht hinterherhinkt.
#  Eigenprofil-Overlay (F4): das zustandsspezifische Drift-Eigenprofil ist
#         persistiert (drift_profiles, am Laufende des Drift-Reasoners geschrieben)
#         und wird hier je Trend-Bucket auf den Korridor des geltenden Zustands
#         expandiert — median +/- effect_size_k * noise_sigma, die ECHTE Detektor-
#         Bewertungsbasis (KEINE Read-Rekonstruktion). Die Zustands-Zuordnung nutzt
#         DIESELBE `state_key_for`-Funktion wie der Detektor-Lauf. Kein/zu junges
#         Profil -> `profile_band` bleibt null (graceful, das FE lässt es weg).
#  Architektur-Einordnung: Read-Core (Schicht 2). Transport-neutral, gibt eine
#         reine dataclass zurück; HTTP/WS mappen sie auf ihren Vertrag.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import DataPoint, DriftProfile
from foreman.reads.queries import (
    MAX_READING_POINTS,
    ReadingBucket,
    load_drift_profile,
    load_readings,
    resolve_data_point,
)
from foreman.reasoners.drift.baseline import state_key_for


@dataclass(frozen=True)
class ProfileBandPoint:
    """Ein zeitaufgelöster Korridorpunkt des Eigenprofils (entlang der Kurvenpunkte)."""

    bucket: datetime
    lower: float
    mid: float
    upper: float


@dataclass(frozen=True)
class ProfileBand:
    """Das zustandsspezifische Eigenprofil-Band (F4) entlang der Trend-Buckets.

    `mid` ist der gleitende Zustands-Median, `lower`/`upper` der Korridor
    `median +/- effect_size_k * noise_sigma` — die echte Detektor-Bewertungsbasis.
    `computed_at` ist der Profil-Stand (Laufende), KEIN Live-Wert.
    """

    computed_at: datetime
    effect_size_k: float
    points: tuple[ProfileBandPoint, ...]


@dataclass(frozen=True)
class MachineTrend:
    """Aggregierter Sensortrend: statisches Normalband + F4-Eigenprofil-Band (F5)."""

    machine_id: int
    data_point_id: int
    data_point_name: str
    unit: str | None
    measurement_type: str | None
    normal_min: float | None
    normal_max: float | None
    points: tuple[ReadingBucket, ...]
    truncated: bool
    # Zustandsspezifisches Eigenprofil-Band (F4); null, wenn kein/zu junges Profil.
    profile_band: ProfileBand | None


def expand_profile_band(
    profile: DriftProfile | None, points: Sequence[ReadingBucket]
) -> ProfileBand | None:
    """Expandiert das persistierte Eigenprofil auf die Trend-Buckets.

    Je Bucket den Korridor des zu seinem Zeitstempel geltenden Zustands (state_key =
    Tagesstunde, GETEILTE Funktion mit dem Detektor-Lauf — sonst zeigte das Band den
    Korridor des falschen Zustands). Die Halbbreite ist `effect_size_k * noise_sigma`,
    genau die Schwelle, ab der der Detektor das Residuum als relevant wertet. Kein
    Profil oder kein Bucket im passenden Zustand -> None (graceful, FE lässt es weg).
    """
    if profile is None:
        return None
    half = profile.effect_size_k * profile.noise_sigma
    band_points: list[ProfileBandPoint] = []
    for point in points:
        entry = profile.state_medians.get(str(state_key_for(point.bucket)))
        if entry is None:
            continue
        median_value = float(entry["median"])
        band_points.append(
            ProfileBandPoint(
                bucket=point.bucket,
                lower=median_value - half,
                mid=median_value,
                upper=median_value + half,
            )
        )
    if not band_points:
        return None
    return ProfileBand(
        computed_at=profile.computed_at,
        effect_size_k=profile.effect_size_k,
        points=tuple(band_points),
    )


def _assemble_trend(
    data_point: DataPoint,
    points: list[ReadingBucket],
    truncated: bool,
    profile_band: ProfileBand | None,
) -> MachineTrend:
    """Setzt den Trend aus Datenpunkt-Metadaten + Punkten + Eigenprofil zusammen (rein)."""
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
        profile_band=profile_band,
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
    profile = await load_drift_profile(session, data_point.id)
    return _assemble_trend(data_point, points, truncated, expand_profile_band(profile, points))


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
    profile = await load_drift_profile(session, data_point.id)
    return _assemble_trend(data_point, points, truncated, expand_profile_band(profile, points))
