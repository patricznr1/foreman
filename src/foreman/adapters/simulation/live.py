# ============================================================
#  FOREMAN — adapters/simulation/live.py
#  Zweck: Live-Daten-Stream-Produzent — setzt den signalbasierten Generator am
#         ENDE der Backfill-Historie an und tickt mit WALL-CLOCK-Stempeln weiter
#         (nie Szenario-Sim-Zeit). Hält die Drift als Plateau (kein Weglaufen),
#         ist neustart-fest (Wiederaufsetzen am letzten DB-Stempel → kein Doppel,
#         keine Lücke) und schreibt über den UNVERÄNDERTEN Ingestion-/COPY-Pfad
#         (inkl. NOTIFY/WS-Push, §12.3 + F5).
#  Architektur-Einordnung: Datenakquise (Schicht 2). Dies ist die EINGANGS-
#         Simulation (digitaler Zwilling als Datenquelle) — strikt getrennt vom
#         FOREMAN-internen Reasoning-Simulieren (das inaktiv bleibt). „Ist das
#         live?" → Ja: echte Generierung mit aktuellen Zeitstempeln.
#  Abgrenzung zu runner.py `--mode live` (WallClockPacer): jener spielt das
#         Szenario ab Tag 0 mit SIM-Stempeln im Echtzeit-Takt ab (gedacht für eine
#         FRISCHE DB). Dieser Produzent setzt die HISTORIE fort — eigener Bau.
# ============================================================
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterator, Sequence
from datetime import UTC, datetime, timedelta

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.adapters.simulation.adapter import SimulationAdapter
from foreman.adapters.simulation.scenario import Scenario
from foreman.ingestion.adapter import SourceAdapter
from foreman.ingestion.normalized import NormalizedEvent, NormalizedReading, ensure_utc

logger = logging.getLogger("foreman.adapters.simulation.live")


def _utc_now() -> datetime:
    """Wall-Clock jetzt (UTC, tz-aware) — injizierbar für Tests."""
    return datetime.now(UTC)


class RealTimePacer:
    """Live-Takt: wartet, bis die Wall-Clock den Ziel-Zeitstempel erreicht.

    Anders als `WallClockPacer` (skalierte Sim-Zeit gegen `monotonic`) IST hier der
    Tick-Stempel der reale Instant — `speed` gibt es nicht (Echtzeit 1:1). Liegt das
    Ziel in der Vergangenheit (Aufhol-Phase nach Backfill/Neustart), wird NICHT
    gewartet — so wird eine Lücke ohne Echtzeit-Verzug aufgefüllt, danach läuft der
    Produzent synchron zur Uhr weiter. `now`/`sleep` sind injizierbar (Tests ohne
    echtes Warten)."""

    def __init__(
        self,
        *,
        now: Callable[[], datetime] = _utc_now,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self._now = now
        self._sleep = sleep
        self.tick_count = 0

    async def __call__(self, target: datetime) -> None:
        self.tick_count += 1
        delay = (ensure_utc(target) - self._now()).total_seconds()
        if delay > 0:
            await self._sleep(delay)


def live_tick_times(
    anchor: datetime, interval: timedelta, max_ticks: int | None = None
) -> Iterator[datetime]:
    """Reine Tick-Zeitachse ab dem Historien-Ende: `anchor+interval`, `+2·interval`, …

    Erster Tick liegt STRIKT nach `anchor` (kein Overlap mit der Historie — der PK
    `(data_point_id, time)` kollidiert nie) und die Achse ist lückenlos im Abstand
    `interval` (kein Gap), streng monoton. `max_ticks` begrenzt den Lauf (Tests/
    endliche Läufe); `None` = unendlich (Dauer-Worker)."""
    if interval <= timedelta(0):
        raise ValueError("interval muss > 0 sein.")
    n = 0
    while max_ticks is None or n < max_ticks:
        n += 1
        yield anchor + n * interval


def cap_resume_anchor(
    last: datetime, *, now: datetime, interval: timedelta, max_catchup_ticks: int | None
) -> datetime:
    """Deckelt die Aufhol-Phase: liegt `last` mehr als `max_catchup_ticks·interval`
    vor `now`, wird der Anker auf `now - interval` gekappt — eine BEWUSSTE, deutlich
    geloggte Lücke statt eines Boot-Storms (Zehntausende Tote-Ticks nach langem
    Stillstand). `None` (Default) = kein Deckel: die Lücke wird lückenlos im Aufhol-
    Takt gefüllt (harte „keine Lücke"-Leitplanke). Reine Funktion (DB-frei testbar)."""
    if max_catchup_ticks is None:
        return last
    if now - last > max_catchup_ticks * interval:
        logger.warning(
            "⏩ Historien-Ende liegt %s zurück (> %d Aufhol-Ticks) — überspringe die "
            "Lücke und setze bei now an (Boot-Storm-Schutz; --max-catchup-ticks anpassen).",
            now - last,
            max_catchup_ticks,
        )
        return now - interval
    return last


async def resolve_resume_anchor(
    session: AsyncSession,
    data_point_ids: Sequence[int],
    *,
    now: datetime,
    interval: timedelta,
    max_catchup_ticks: int | None = None,
) -> datetime:
    """Bestimmt den Wiederaufsetz-Punkt: den letzten Reading-Stempel der Park-Datenpunkte.

    Der erste Live-Tick liegt bei `anchor + interval` (strikt danach → kein Doppel,
    keine Lücke; neustart-fest, weil der Anker bei jedem Start frisch aus der DB
    gelesen wird). Ohne Historie (leere DB / unbekannte Datenpunkte) → `now - interval`,
    sodass der erste Tick bei `now` startet — mit deutlichem Log-Hinweis. `max_catchup_ticks`
    deckelt optional eine sehr große Aufhol-Phase (siehe `cap_resume_anchor`)."""
    if not data_point_ids:
        logger.warning("⏩ Keine Park-Datenpunkte aufgelöst — Live-Anker auf now-interval.")
        return now - interval
    stmt = text(
        "SELECT max(time) AS last_time FROM readings WHERE data_point_id IN :ids"
    ).bindparams(bindparam("ids", expanding=True))
    result = await session.execute(stmt, {"ids": list(data_point_ids)})
    last = result.scalar_one_or_none()
    if last is None:
        logger.warning("⏩ Keine Historie für die Park-Datenpunkte — Live-Anker auf now-interval.")
        return now - interval
    return cap_resume_anchor(
        ensure_utc(last), now=now, interval=interval, max_catchup_ticks=max_catchup_ticks
    )


class LiveParkAdapter(SourceAdapter):
    """SourceAdapter, der den ganzen Twin-Park am Historien-Ende fortsetzt.

    Bündelt je Park-Szenario einen `SimulationAdapter` und tickt sie GEMEINSAM auf
    EINER Wall-Clock-Zeitachse weiter (ein Tick = ein Stempel über alle Maschinen →
    ein gebündeltes NOTIFY je Commit). Pro Datenpunkt läuft die Drift als Plateau
    (konstantes `elapsed_s = end_elapsed_s`); gesunde Maschinen bleiben gesund
    (Drift `None` → kein erfundenes Signal, Ehrlichkeitslinie). `events()` ist leer
    — der Produzent erfindet keine Alarme; neue Alarme entstehen erst, wenn die
    Reasoner den fortlaufenden Strom auswerten."""

    def __init__(
        self,
        scenarios: Sequence[Scenario],
        *,
        interval: timedelta,
        seed: int | None = None,
        max_ticks: int | None = None,
        max_catchup_ticks: int | None = None,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        if not scenarios:
            raise ValueError("LiveParkAdapter braucht mindestens ein Szenario.")
        if interval <= timedelta(0):
            raise ValueError("interval muss > 0 sein.")
        self._adapters = [SimulationAdapter(scenario, seed=seed) for scenario in scenarios]
        self._interval = interval
        self._max_ticks = max_ticks
        self._max_catchup_ticks = max_catchup_ticks
        self._now = now
        self._anchor: datetime | None = None

    @property
    def name(self) -> str:
        return "simulation_live"

    @property
    def anchor(self) -> datetime:
        if self._anchor is None:
            raise RuntimeError("seed_topology() muss vor readings() laufen.")
        return self._anchor

    async def seed_topology(self, session: AsyncSession) -> None:
        """Seedet die Topologie aller Park-Szenarien idempotent und bestimmt den Anker."""
        for adapter in self._adapters:
            await adapter.seed_topology(session)
        data_point_ids = [
            dp_id
            for adapter in self._adapters
            for dp_id in adapter.topology.data_point_ids.values()
        ]
        self._anchor = await resolve_resume_anchor(
            session,
            data_point_ids,
            now=self._now(),
            interval=self._interval,
            max_catchup_ticks=self._max_catchup_ticks,
        )
        logger.info(
            "⏱️ Live-Anker = %s · interval = %s · max_ticks = %s · Maschinen = %d",
            self._anchor.isoformat(),
            self._interval,
            self._max_ticks,
            len(self._adapters),
        )

    def readings(self) -> Iterator[NormalizedReading]:
        anchor = self.anchor
        # Pro Sub-Adapter einmal den Erzeugungszustand aufbauen (RNG-Strom, Plateau-
        # elapsed, ID-Auflösung, lokale Zeitzone) — über alle Ticks fortgeschrieben.
        prepared = [
            (
                adapter,
                adapter.new_rngs(),
                adapter.end_elapsed_s(),
                adapter.topology.data_point_ids,
                adapter.local_timezone,
            )
            for adapter in self._adapters
        ]
        for tick_time in live_tick_times(anchor, self._interval, self._max_ticks):
            for adapter, rngs, plateau_elapsed, data_point_ids, tz in prepared:
                local_dt = tick_time.astimezone(tz)
                yield from adapter.tick_readings(
                    utc_time=tick_time,
                    local_dt=local_dt,
                    elapsed_s=plateau_elapsed,
                    rngs=rngs,
                    data_point_ids=data_point_ids,
                )

    def events(self) -> Iterator[NormalizedEvent]:
        # Der Live-Produzent erfindet keine diskreten Ereignisse (Ehrlichkeitslinie).
        return iter(())
