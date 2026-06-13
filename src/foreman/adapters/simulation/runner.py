# ============================================================
#  FOREMAN — adapters/simulation/runner.py
#  Zweck: CLI-/Modul-Entrypoint des Simulations-Adapters (F3) mit zwei Modi:
#         - backfill: erzeugt N Tage Historie schnell (F4-Validierung + Dashboard);
#         - live:     streamt Readings im Wall-Clock-Takt (Live-Demo).
#  Architektur-Einordnung: Datenakquise (Schicht 2). Kein Celery/Job-Worker
#         (Stack §3) — der Runner ist ein Vordergrund-Prozess:
#         python -m foreman.adapters.simulation.runner --scenario … --mode …
#  Backfill-Sonderlauf (Research §6): schreibt per COPY in vergangene Chunks.
#         In frischer DB unkritisch (noch keine komprimierten Chunks). Bewusster
#         Sonderlauf, kein Dauer-Schreibweg in alte/komprimierte Chunks.
# ============================================================
from __future__ import annotations

import argparse
import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import datetime

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from foreman.adapters.simulation.adapter import SimulationAdapter
from foreman.config import Settings, get_settings
from foreman.core.pseudonymize import Pseudonymizer, build_pseudonymizer
from foreman.core.redact import Redactor, build_redactor
from foreman.ingestion.service import IngestionService, IngestStats
from foreman.logging_setup import setup_logging
from foreman.substrate.client import SubstrateClient

logger = logging.getLogger("foreman.adapters.simulation.runner")

# Default-Geschwindigkeit im live-Modus: Sim-Sekunden pro Echtzeit-Sekunde.
DEFAULT_LIVE_SPEED = 60.0


class WallClockPacer:
    """Taktet den live-Modus: wartet, bis die Echtzeit den (skalierten) Sim-Zeitpunkt
    erreicht. `speed` = Sim-Sekunden pro Echtzeit-Sekunde (60 → 1 min Sim/Sekunde).

    Verankert sich beim ersten Aufruf (kein Warten vor dem ersten Tick). Sleep- und
    Monotonic-Quelle sind injizierbar (Tests ohne echtes Warten)."""

    def __init__(
        self,
        speed: float = DEFAULT_LIVE_SPEED,
        *,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if speed <= 0:
            raise ValueError("speed muss > 0 sein.")
        self._speed = speed
        self._sleep = sleep
        self._monotonic = monotonic
        self._sim_anchor: datetime | None = None
        self._real_anchor: float = 0.0
        self.tick_count = 0

    async def __call__(self, sim_time: datetime) -> None:
        self.tick_count += 1
        if self._sim_anchor is None:
            self._sim_anchor = sim_time
            self._real_anchor = self._monotonic()
            return
        sim_elapsed_s = (sim_time - self._sim_anchor).total_seconds() / self._speed
        target = self._real_anchor + sim_elapsed_s
        delay = target - self._monotonic()
        if delay > 0:
            await self._sleep(delay)


def _build_substrate(settings: Settings) -> SubstrateClient | None:
    """Baut den Substrat-Client, falls konfiguriert — sonst None (Fallback, §9)."""
    if not settings.substrate_base_url:
        logger.info("💤 Kein Substrat konfiguriert — Dual-Write übersprungen (Fallback).")
        return None
    return SubstrateClient.from_settings(settings)


async def run_ingestion(
    session: object,
    adapter: SimulationAdapter,
    *,
    mode: str,
    speed: float = DEFAULT_LIVE_SPEED,
    batch_size: int = 5000,
    pseudonymizer: Pseudonymizer,
    redactor: Redactor,
    substrate: SubstrateClient | None = None,
) -> IngestStats:
    """Testbarer Kern: baut den Service und fährt den Adapter im gewählten Modus.

    `session` ist eine AsyncSession (lose typisiert, um Test-Doubles zuzulassen).
    """
    from sqlalchemy.ext.asyncio import AsyncSession

    assert isinstance(session, AsyncSession)
    service = IngestionService(
        session,
        pseudonymizer=pseudonymizer,
        redactor=redactor,
        substrate=substrate,
        batch_size=batch_size,
    )
    pace = WallClockPacer(speed) if mode == "live" else None
    return await service.ingest(adapter, pace=pace)


def build_argparser() -> argparse.ArgumentParser:
    """Baut den CLI-Parser für den Simulations-Runner."""
    parser = argparse.ArgumentParser(
        prog="foreman-simulation",
        description="FOREMAN Simulations-Adapter — Backfill/Live-Datengenerierung.",
    )
    parser.add_argument(
        "--scenario",
        required=True,
        help="Szenario-Name (aus scenarios/) oder Pfad zu einer YAML-Datei.",
    )
    parser.add_argument(
        "--mode",
        choices=["backfill", "live"],
        default="backfill",
        help="backfill = Historie schnell erzeugen; live = im Wall-Clock-Takt streamen.",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=DEFAULT_LIVE_SPEED,
        help="live-Modus: Sim-Sekunden pro Echtzeit-Sekunde (Default 60).",
    )
    parser.add_argument("--seed", type=int, default=None, help="RNG-Seed (Reproduzierbarkeit).")
    parser.add_argument("--batch-size", type=int, default=5000, help="COPY-Batch-Größe.")
    parser.add_argument(
        "--db-url", default=None, help="Override der Datenbank-URL (sonst aus .env)."
    )
    return parser


def _resolve_adapter(scenario_arg: str, seed: int | None) -> SimulationAdapter:
    """Baut den Adapter aus Name (scenarios/) oder Dateipfad."""
    if scenario_arg.endswith((".yaml", ".yml")) or "/" in scenario_arg or "\\" in scenario_arg:
        return SimulationAdapter.from_config(scenario_path=scenario_arg, seed=seed)
    return SimulationAdapter.from_config(scenario_name=scenario_arg, seed=seed)


async def amain(
    argv: list[str] | None = None,
    *,
    settings: Settings | None = None,
    redactor: Redactor | None = None,
) -> int:
    """Async-Entrypoint: parst Argumente, baut Engine/Session und fährt den Lauf."""
    args = build_argparser().parse_args(argv)
    scenario_arg: str = args.scenario
    mode: str = args.mode
    speed: float = args.speed
    seed: int | None = args.seed
    batch_size: int = args.batch_size
    db_url_override: str | None = args.db_url

    cfg = settings or get_settings()
    database_url = db_url_override or cfg.database_url

    adapter = _resolve_adapter(scenario_arg, seed)
    pseudonymizer = build_pseudonymizer(cfg)
    used_redactor = redactor or build_redactor()
    substrate = _build_substrate(cfg)

    engine = create_async_engine(database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    try:
        async with maker() as session:
            logger.info(
                "🔄 Starte Ingestion: scenario=%s mode=%s seed=%s",
                scenario_arg,
                mode,
                seed,
            )
            stats = await run_ingestion(
                session,
                adapter,
                mode=mode,
                speed=speed,
                batch_size=batch_size,
                pseudonymizer=pseudonymizer,
                redactor=used_redactor,
                substrate=substrate,
            )
            logger.info("✅ Fertig: %d Readings geschrieben.", stats.readings_written)
    finally:
        await engine.dispose()
        if substrate is not None:
            await substrate.aclose()
    return 0


def main() -> None:  # pragma: no cover — dünner Sync-Wrapper um amain
    """Synchroner Konsolen-Entrypoint (python -m …)."""
    setup_logging()
    raise SystemExit(asyncio.run(amain()))


if __name__ == "__main__":  # pragma: no cover
    main()
