# ============================================================
#  FOREMAN — reads/queries.py
#  Zweck: Die geteilten Read-only-Datenzugriffe des Read-Cores. Dedizierte,
#         testbare SELECT-Funktionen mit injizierter Session (DI) — der saubere
#         Service-Layer, den ALLE Transporte teilen: MCP (F7), die HTTP-Read-
#         Routen und der WebSocket-Push-Layer (F5). Spiegelt die Read-Pfade als
#         wiederverwendbare Funktionen; KEIN Write, KEIN LLM-/Reasoner-Trigger.
#  Architektur-Einordnung: Read-Core (Schicht 2). Reine Datenzugriffsschicht;
#         die Session wird injiziert — ohne globalen Zustand testbar. Kennt
#         keinen Transport (kein FastAPI, kein MCP, kein WS).
#  Invariante: ausschließlich SELECT — keine Aktorik, keine teure Reasoner-
#         Berechnung. Aggregierte Trends über die Minuten-Aggregat-Sicht.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import (
    Alarm,
    DataPoint,
    DriftProfile,
    FailurePredictionRecord,
    FailureRecommendationRecord,
    Machine,
    ReasonerExplanationRecord,
    WorkerNote,
)
from foreman.embeddings.provider import EmbeddingProvider
from foreman.ingestion.normalized import ensure_utc
from foreman.notes.search import DEFAULT_SEARCH_K, embed_and_search
from foreman.reasoners.drift.service import DRIFT_ALARM_CODE

# Diskriminator der Ereignisketten-Erklärungen (Tabelle ist reasoner-übergreifend).
EVENT_CHAIN_REASONER = "event_chain"
# Obergrenze der zurückgegebenen Trend-Punkte (7 Tage Minuten-Auflösung) — bremst
# die Abruf-Last gegen Drittsysteme (Brief §5: sinnvolle Abruf-Limits).
MAX_READING_POINTS = 10_080


@dataclass(frozen=True)
class ReadingBucket:
    """Ein aggregierter Minuten-Punkt eines Sensortrends (Mittel/Min/Max/Last)."""

    bucket: datetime
    avg: float
    min: float
    max: float
    last: float | None


@dataclass(frozen=True)
class LatestValue:
    """Der jüngste aggregierte Wert eines Datenpunkts (für die lebende Karte).

    `value` ist `last_value` des neuesten readings_1m-Buckets (der zuletzt gesehene
    Rohwert dieser Minute), `at` der Bucket-Zeitstempel — die Grundlage von
    `last_value`/`last_value_at` der Maschinenkarte und der ehrlichen Stale-Anzeige.
    """

    value: float | None
    at: datetime


# ============================================================
#  Stammdaten + Status-Komposition
# ============================================================
async def list_machines(
    session: AsyncSession, *, limit: int = 100, offset: int = 0
) -> Sequence[Machine]:
    """Listet Maschinen-Stammdaten (stabile ID-Ordnung)."""
    result = await session.scalars(select(Machine).order_by(Machine.id).limit(limit).offset(offset))
    return result.all()


async def get_machine(session: AsyncSession, machine_id: int) -> Machine | None:
    """Liefert eine Maschine (Stammdaten) oder None."""
    return await session.get(Machine, machine_id)


async def open_alarms(session: AsyncSession, machine_id: int) -> Sequence[Alarm]:
    """Offene (nicht zurückgesetzte) Alarme einer Maschine — Grundlage des Status."""
    result = await session.scalars(
        select(Alarm)
        .where(Alarm.machine_id == machine_id, Alarm.cleared_at.is_(None))
        .order_by(Alarm.raised_at.desc())
    )
    return result.all()


async def open_alarms_for_machines(
    session: AsyncSession, machine_ids: Sequence[int]
) -> dict[int, list[Alarm]]:
    """Offene Alarme mehrerer Maschinen in EINER Abfrage (kein N+1 für die Liste)."""
    grouped: dict[int, list[Alarm]] = {machine_id: [] for machine_id in machine_ids}
    if not machine_ids:
        return grouped
    result = await session.scalars(
        select(Alarm).where(Alarm.machine_id.in_(machine_ids), Alarm.cleared_at.is_(None))
    )
    for alarm in result:
        grouped.setdefault(alarm.machine_id, []).append(alarm)
    return grouped


async def machines_for_data_points(
    session: AsyncSession, data_point_ids: Sequence[int]
) -> set[int]:
    """Die Maschinen der gegebenen Datenpunkte (für die Live-Push-NOTIFY-Anreicherung).

    Ein Reading-Change an einem Datenpunkt ist zugleich ein Change der lebenden Karte
    seiner Maschine — der Produzent reichert den ChangeSet damit an, sodass das pure
    `topics_for_change` die Themen `machine:{id}` (+ overview) automatisch mitzieht.
    """
    if not data_point_ids:
        return set()
    result = await session.scalars(
        select(DataPoint.machine_id).where(DataPoint.id.in_(data_point_ids)).distinct()
    )
    return set(result.all())


# ============================================================
#  Alarme + Drift
# ============================================================
async def list_alarms(
    session: AsyncSession,
    *,
    machine_id: int | None = None,
    since: datetime | None = None,
    severity: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[Alarm]:
    """Listet Alarme (jüngste zuerst), optional gefiltert nach Maschine/Zeit/Schwere."""
    stmt = select(Alarm).order_by(Alarm.raised_at.desc())
    if machine_id is not None:
        stmt = stmt.where(Alarm.machine_id == machine_id)
    if since is not None:
        stmt = stmt.where(Alarm.raised_at >= since)
    if severity is not None:
        stmt = stmt.where(Alarm.severity == severity)
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()


async def list_drift_warnings(
    session: AsyncSession,
    *,
    machine_id: int,
    only_open: bool = True,
    limit: int = 100,
    offset: int = 0,
) -> Sequence[Alarm]:
    """Drift-Warnungen einer Maschine (code=DRIFT); `only_open` = noch nicht quittiert."""
    stmt = (
        select(Alarm)
        .where(Alarm.code == DRIFT_ALARM_CODE, Alarm.machine_id == machine_id)
        .order_by(Alarm.raised_at.desc())
    )
    if only_open:
        stmt = stmt.where(Alarm.acknowledged_at.is_(None))
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()


# ============================================================
#  Ausfallvorhersage + Empfehlung (gespeicherte KI-Outputs)
# ============================================================
async def list_predictions(
    session: AsyncSession, *, machine_id: int | None = None, limit: int = 50, offset: int = 0
) -> Sequence[FailurePredictionRecord]:
    """Listet gespeicherte Ausfallvorhersagen (jüngste zuerst)."""
    stmt = select(FailurePredictionRecord).order_by(FailurePredictionRecord.created_at.desc())
    if machine_id is not None:
        stmt = stmt.where(FailurePredictionRecord.machine_id == machine_id)
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()


async def get_prediction(
    session: AsyncSession, prediction_id: int
) -> FailurePredictionRecord | None:
    """Liefert eine gespeicherte Vorhersage oder None."""
    return await session.get(FailurePredictionRecord, prediction_id)


async def get_latest_recommendation(
    session: AsyncSession, prediction_id: int
) -> FailureRecommendationRecord | None:
    """Liefert die jüngste gespeicherte Empfehlung zu einer Vorhersage (oder None)."""
    stmt = (
        select(FailureRecommendationRecord)
        .where(FailureRecommendationRecord.prediction_id == prediction_id)
        .order_by(
            FailureRecommendationRecord.created_at.desc(),
            FailureRecommendationRecord.id.desc(),
        )
        .limit(1)
    )
    return (await session.scalars(stmt)).first()


# ============================================================
#  Ereignisketten-Erklärungen (gespeicherte KI-Outputs)
# ============================================================
async def list_event_chains(
    session: AsyncSession, *, machine_id: int | None = None, limit: int = 50, offset: int = 0
) -> Sequence[ReasonerExplanationRecord]:
    """Listet gespeicherte Ereignisketten-Erklärungen (jüngste zuerst).

    Filtert auf den Ereignisketten-Reasoner — die Tabelle ist reasoner-übergreifend;
    ohne den Filter würden Erklärungen anderer Reasoner durchsickern.
    """
    stmt = (
        select(ReasonerExplanationRecord)
        .where(ReasonerExplanationRecord.reasoner == EVENT_CHAIN_REASONER)
        .order_by(ReasonerExplanationRecord.created_at.desc())
    )
    if machine_id is not None:
        stmt = stmt.where(ReasonerExplanationRecord.machine_id == machine_id)
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()


async def get_event_chain(
    session: AsyncSession, explanation_id: int
) -> ReasonerExplanationRecord | None:
    """Liefert eine gespeicherte Ereignisketten-Erklärung oder None.

    None auch, wenn der Datensatz von einem anderen Reasoner stammt — dieses Tool
    exponiert ausschließlich Ereignisketten.
    """
    record = await session.get(ReasonerExplanationRecord, explanation_id)
    if record is None or record.reasoner != EVENT_CHAIN_REASONER:
        return None
    return record


# ============================================================
#  Datenpunkte + aggregierte Sensortrends
# ============================================================
async def resolve_data_point(session: AsyncSession, machine_id: int, name: str) -> DataPoint | None:
    """Löst den technischen Datenpunkt-Namen auf die ID auf (auf die Maschine begrenzt)."""
    stmt = (
        select(DataPoint).where(DataPoint.machine_id == machine_id, DataPoint.name == name).limit(1)
    )
    return (await session.scalars(stmt)).first()


async def load_drift_profile(session: AsyncSession, data_point_id: int) -> DriftProfile | None:
    """Lädt das persistierte Eigenprofil eines Datenpunkts (F4) oder None.

    Read-only Basis des Eigenprofil-Overlays — die Read-Schicht expandiert daraus
    je Trend-Bucket den Zustands-Korridor (`reads.trend.expand_profile_band`)."""
    stmt = select(DriftProfile).where(DriftProfile.data_point_id == data_point_id)
    return (await session.scalars(stmt)).first()


async def load_drift_profiles_for_data_points(
    session: AsyncSession, data_point_ids: Sequence[int]
) -> dict[int, DriftProfile]:
    """Lädt die Eigenprofile mehrerer Datenpunkte in EINER Abfrage (kein N+1).

    Für die Status-Ableitung der lebenden Maschinenkarte über eine ganze Maschine/
    Flotte — je Datenpunkt höchstens ein Profil (UNIQUE data_point_id, §5)."""
    if not data_point_ids:
        return {}
    result = await session.scalars(
        select(DriftProfile).where(DriftProfile.data_point_id.in_(data_point_ids))
    )
    return {profile.data_point_id: profile for profile in result}


async def latest_values_for_data_points(
    session: AsyncSession, data_point_ids: Sequence[int]
) -> dict[int, LatestValue]:
    """Jüngster Wert JE DATENPUNKT (last_value des neuesten readings_1m-Buckets).

    EINE Abfrage über die Minuten-Aggregat-Sicht (`DISTINCT ON` je Datenpunkt, neuester
    Bucket zuerst) — günstig, kein Full-Scan, kein N+1 für eine ganze Maschine/Flotte.
    Datenpunkte ohne Readings fehlen im Ergebnis (ehrlich leer — die Karte zeigt dann
    keinen Wert, statt einen zu erfinden).
    """
    if not data_point_ids:
        return {}
    stmt = text(
        "SELECT DISTINCT ON (data_point_id) data_point_id, bucket, last_value "
        "FROM readings_1m "
        "WHERE data_point_id = ANY(:dp_ids) "
        "ORDER BY data_point_id, bucket DESC"
    )
    rows = (await session.execute(stmt, {"dp_ids": list(data_point_ids)})).all()
    return {
        data_point_id: LatestValue(value=last_value, at=ensure_utc(bucket))
        for data_point_id, bucket, last_value in rows
    }


async def load_readings(
    session: AsyncSession,
    data_point_id: int,
    start: datetime,
    end: datetime,
    *,
    limit: int = MAX_READING_POINTS,
) -> tuple[list[ReadingBucket], bool]:
    """Lädt den aggregierten Minuten-Trend eines Datenpunkts im Fenster [start, end).

    Liest die Minuten-Aggregat-Sicht (read-only). Gibt (Punkte, truncated) zurück —
    `truncated` ist True, wenn das Fenster die Punkt-Obergrenze überschritt.
    """
    # Harte Lastgrenze: nie mehr als die Obergrenze ziehen, unabhängig vom Aufrufer.
    limit = min(limit, MAX_READING_POINTS)
    stmt = text(
        "SELECT bucket, avg_value, min_value, max_value, last_value "
        "FROM readings_1m "
        "WHERE data_point_id = :dp_id AND bucket >= :start AND bucket < :end "
        "ORDER BY bucket "
        "LIMIT :limit"
    )
    rows = (
        await session.execute(
            stmt, {"dp_id": data_point_id, "start": start, "end": end, "limit": limit + 1}
        )
    ).all()
    truncated = len(rows) > limit
    points: list[ReadingBucket] = []
    for bucket, avg_value, min_value, max_value, last_value in rows[:limit]:
        if avg_value is None:
            continue
        points.append(
            ReadingBucket(
                bucket=ensure_utc(bucket),
                avg=avg_value,
                min=min_value if min_value is not None else avg_value,
                max=max_value if max_value is not None else avg_value,
                last=last_value,
            )
        )
    return points, truncated


# ============================================================
#  Semantische Notiz-Suche (billig: Query einbetten + vektoriell suchen, read-only)
# ============================================================
async def search_notes(
    provider: EmbeddingProvider,
    session: AsyncSession,
    query: str,
    *,
    machine_id: int | None = None,
    k: int = DEFAULT_SEARCH_K,
) -> Sequence[WorkerNote]:
    """Sucht semantisch ähnliche Notizen (bettet den Query ein, sucht — kein LLM)."""
    return await embed_and_search(provider, session, query, machine_id=machine_id, k=k)
