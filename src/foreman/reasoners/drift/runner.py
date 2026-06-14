# ============================================================
#  FOREMAN — reasoners/drift/runner.py
#  Zweck: Replay des Drift-Reasoners über readings_1m für einen Zeitraum
#         (Validierung + Batch-Lauf, F4 Baustein 5).
#  Architektur-Einordnung: Reasoning-Schicht (F4). Vor dem Replay muss das
#         readings_1m-Continuous-Aggregate aktualisiert werden: nach einem
#         Backfill (F3-Runner) ist es leer/veraltet (WITH NO DATA). Der Refresh
#         läuft bewusst im AUTOCOMMIT — `refresh_continuous_aggregate` darf NICHT
#         in einem Transaktionsblock laufen (TimescaleDB-Einschränkung).
# ============================================================
from __future__ import annotations

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from foreman.logging_setup import OK, get_logger
from foreman.reasoners.drift.relevance import (
    DEFAULT_MIN_EFFECT_SIZE,
    DEFAULT_PERSISTENCE_INTERVALS,
)
from foreman.reasoners.drift.service import DriftFinding, DriftService
from foreman.substrate.client import SubstrateClient

logger = get_logger("foreman.reasoners.drift.runner")


async def refresh_readings_1m(connection: AsyncConnection) -> None:
    """Aktualisiert das readings_1m-Continuous-Aggregate (gesamter Bereich).

    Erwartet eine Connection im AUTOCOMMIT-Modus (kein Transaktionsblock) — der
    Aufrufer setzt `execution_options(isolation_level="AUTOCOMMIT")`. Nötig nach
    einem Backfill, bevor der Reasoner readings_1m liest.
    """
    await connection.execute(
        text("CALL refresh_continuous_aggregate('readings_1m', NULL, NULL)")
    )
    logger.info("%s readings_1m aktualisiert (Continuous Aggregate refresh)", OK)


async def replay_machine(
    session: AsyncSession,
    machine_id: int,
    start: datetime,
    end: datetime,
    *,
    substrate: SubstrateClient | None = None,
    min_effect_size: float = DEFAULT_MIN_EFFECT_SIZE,
    persistence_intervals: int = DEFAULT_PERSISTENCE_INTERVALS,
) -> list[DriftFinding]:
    """Fährt den Drift-Reasoner für eine Maschine über [start, end) und
    persistiert die erkannten, relevanten Drift-Ereignisse.

    Setzt voraus, dass readings_1m bereits aktuell ist (siehe `refresh_readings_1m`).
    """
    service = DriftService(
        session,
        substrate=substrate,
        min_effect_size=min_effect_size,
        persistence_intervals=persistence_intervals,
    )
    return await service.run_machine(machine_id, start, end)
