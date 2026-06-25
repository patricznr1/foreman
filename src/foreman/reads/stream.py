# ============================================================
#  FOREMAN — reads/stream.py
#  Zweck: Der schlanke, datengetriebene Zustand des EINGANGS-Live-Streams (der
#         digitale Zwilling als Datenquelle, §12.6): tickt der Live-Worker gerade
#         fortlaufend Wall-Clock-Readings — oder liegt nur geseedete Historie vor?
#         Abgeleitet aus dem jüngsten `readings`-Stempel der internen Simulations-
#         Quelle gegen ein Frischefenster. Dies ist die EINE Wahrheit, die sowohl
#         die Plattform-Topologie-Kachel „Simulation (intern)" als auch das globale
#         „Live"-Badge tragen — sie laufen damit nie auseinander.
#  Verfassung (Ehrlichkeit): „aktiv" NUR, wenn wirklich getickt wird — kein
#         Etikett. Dies ist die EINGANGS-Simulation (Zwilling), NICHT FOREMANs
#         internes Reasoning-Simulieren (#5, bleibt außen vor).
#  Architektur-Einordnung: Read-Core (Schicht 2). Transport-neutral, ausschließlich
#         SELECT — keine Aktorik, kein Write.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import DataPoint, Reading

# Quelle des digitalen Zwillings (intern erzeugte Readings, §22.2). Konsistent mit
# topology/service.py — derselbe `data_points.source`-Wert.
SIM_SOURCE = "simulation"

# Frischefenster des Eingangs-Streams: jünger → aktiv, älter → inaktiv. Bewusst
# enger als das generische Topologie-Fenster (60 min) — ein „Live"-Stream, der vor
# einer Stunde verstummte, ist nicht live. Kalibriert auf den Worker-Default-Takt
# (60 s, live_worker.DEFAULT_INTERVAL_SECONDS): toleriert ~5 verpasste Ticks
# (Deploy-Neustart, kurzer Hänger) und erkennt einen gestoppten Worker binnen 5 min.
STREAM_FRESH_WINDOW = timedelta(minutes=5)


@dataclass(frozen=True)
class StreamStatus:
    """Zustand des Eingangs-Live-Streams (Zwilling als Datenquelle).

    `active=True` heißt: der Worker tickt fortlaufend frische Wall-Clock-Readings.
    `last_reading_at` ist der jüngste Reading-Stempel der Simulationsquelle (der
    ehrliche „Stand") — None, wenn nie ein solches Reading floss.
    """

    active: bool
    last_reading_at: datetime | None


def classify_stream(
    last_reading_at: datetime | None, *, now: datetime, fresh_window: timedelta
) -> bool:
    """Aktiv genau dann, wenn das jüngste Reading im Frischefenster liegt (rein).

    Ohne Reading (`None`) → inaktiv (nie „aktiv" geraten). Ein naiver Stempel wird
    defensiv als UTC interpretiert, damit der Vergleich nie auf tz-Mischung wirft.
    Die Fenstergrenze zählt noch als frisch (`>=`).
    """
    if last_reading_at is None:
        return False
    stamp = last_reading_at if last_reading_at.tzinfo is not None else last_reading_at.replace(
        tzinfo=UTC
    )
    return stamp >= now - fresh_window


async def latest_source_reading(
    session: AsyncSession, *, source: str = SIM_SOURCE
) -> datetime | None:
    """Jüngster `readings`-Stempel über alle Datenpunkte einer Quelle (oder None)."""
    latest: datetime | None = await session.scalar(
        select(func.max(Reading.time))
        .select_from(Reading)
        .join(DataPoint, Reading.data_point_id == DataPoint.id)
        .where(DataPoint.source == source)
    )
    return latest


async def build_stream_status(
    session: AsyncSession,
    *,
    now: datetime,
    fresh_window: timedelta = STREAM_FRESH_WINDOW,
    source: str = SIM_SOURCE,
) -> StreamStatus:
    """Baut den Eingangs-Stream-Status aus dem jüngsten Reading der Simulationsquelle."""
    last = await latest_source_reading(session, source=source)
    return StreamStatus(
        active=classify_stream(last, now=now, fresh_window=fresh_window),
        last_reading_at=last,
    )
