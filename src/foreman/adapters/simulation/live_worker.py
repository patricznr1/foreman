# ============================================================
#  FOREMAN — adapters/simulation/live_worker.py
#  Zweck: Entrypoint des Live-Daten-Stream-Workers — fährt den ganzen Twin-Park
#         als DAUER-Prozess am Historien-Ende fort (Wall-Clock-Stempel) und
#         schreibt über den unveränderten Ingestion-/COPY-Pfad inkl. NOTIFY-Push.
#  Architektur-Einordnung: Datenakquise (Schicht 2). Eigener Railway-Worker-
#         Service (KEIN Job-Worker im Sinne von Celery, §3 — ein dünner
#         Vordergrund-Dauerprozess). Neustart-Strategie: bei Fehler/Stop beendet
#         sich der Prozess; Railway startet ihn neu, der Anker wird frisch aus der
#         DB gelesen (kein Doppel, keine Lücke) — siehe live.py + DEPLOY.md.
#  Abgrenzung: park.py `--mode live` spielt das Szenario ab Tag 0 mit Sim-Zeit ab
#         (frische DB). Dieser Worker SETZT die Historie fort — der scharfe
#         Live-Demo-Produzent.
#  Aufruf: python -m foreman.adapters.simulation.live_worker
#          [--interval-seconds 60] [--seed --batch-size --max-ticks --db-url]
# ============================================================
from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from foreman.adapters.simulation.live import LiveParkAdapter, RealTimePacer
from foreman.adapters.simulation.park import park_scenario_paths
from foreman.adapters.simulation.scenario import Scenario, load_scenario_file
from foreman.config import Settings, get_settings
from foreman.core.pseudonymize import Pseudonymizer, build_pseudonymizer
from foreman.core.redact import Redactor, build_redactor
from foreman.ingestion.service import IngestionService, IngestStats, Pacer
from foreman.logging_setup import setup_logging
from foreman.substrate.client import SubstrateClient

logger = logging.getLogger("foreman.adapters.simulation.live_worker")

# Default-Live-Takt: ein Reading-Satz je Minute. Faithful genug (deckt sich mit dem
# readings_1m-Aggregat des Dashboards/Reasoners) und sichtbar „lebendig". Für die
# Vorführung dichter (z. B. 5-10 s); 600 s wäre der historientreue Park-Takt.
DEFAULT_INTERVAL_SECONDS = 60.0


def park_scenarios() -> list[Scenario]:
    """Lädt + validiert alle Park-Szenarien (`park_*.yaml`) als Scenario-Objekte."""
    paths = park_scenario_paths()
    if not paths:
        raise FileNotFoundError("Keine Park-Szenarien (park_*.yaml) gefunden.")
    return [load_scenario_file(path) for path in paths]


async def run_live_worker(
    session: object,
    *,
    scenarios: list[Scenario] | None = None,
    interval_seconds: float = DEFAULT_INTERVAL_SECONDS,
    seed: int | None = None,
    batch_size: int = 5000,
    max_ticks: int | None = None,
    max_catchup_ticks: int | None = None,
    pseudonymizer: Pseudonymizer,
    redactor: Redactor,
    substrate: SubstrateClient | None = None,
    pacer: Pacer | None = None,
    now: Callable[[], datetime] | None = None,
) -> IngestStats:
    """Testbarer Kern: baut den Live-Adapter + Pacer und fährt den Ingestion-Pfad.

    `scenarios=None` → der ganze Park. `max_ticks=None` → Dauerlauf (Worker);
    endliche Werte für Tests/begrenzte Läufe. `pace`/`now` injizierbar (Tests ohne
    echtes Warten). Schreibt über den UNVERÄNDERTEN `IngestionService.ingest`
    (COPY-Einzigkeit + NOTIFY je Commit) — kein zweiter Schreibweg."""
    if interval_seconds <= 0:
        raise ValueError("interval_seconds muss > 0 sein.")
    from sqlalchemy.ext.asyncio import AsyncSession

    assert isinstance(session, AsyncSession)
    now_fn = now if now is not None else (lambda: datetime.now(UTC))
    interval = timedelta(seconds=interval_seconds)

    adapter = LiveParkAdapter(
        scenarios if scenarios is not None else park_scenarios(),
        interval=interval,
        seed=seed,
        max_ticks=max_ticks,
        max_catchup_ticks=max_catchup_ticks,
        now=now_fn,
    )
    pace: Pacer = pacer if pacer is not None else RealTimePacer(now=now_fn)
    service = IngestionService(
        session,
        pseudonymizer=pseudonymizer,
        redactor=redactor,
        substrate=substrate,
        batch_size=batch_size,
    )
    return await service.ingest(adapter, pace=pace)


def build_argparser() -> argparse.ArgumentParser:
    """Baut den CLI-Parser für den Live-Daten-Stream-Worker."""
    parser = argparse.ArgumentParser(
        prog="foreman-live-worker",
        description="FOREMAN Live-Daten-Stream — setzt den Twin-Park am Historien-Ende fort.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=DEFAULT_INTERVAL_SECONDS,
        help=f"Wall-Clock-Abstand zwischen Reading-Sätzen (Default {DEFAULT_INTERVAL_SECONDS:g}s).",
    )
    parser.add_argument("--seed", type=int, default=None, help="RNG-Seed (Reproduzierbarkeit).")
    parser.add_argument("--batch-size", type=int, default=5000, help="COPY-Batch-Größe.")
    parser.add_argument(
        "--max-ticks",
        type=int,
        default=None,
        help="Auf N Ticks begrenzen (Test/Smoke). Default: unbegrenzter Dauerlauf.",
    )
    parser.add_argument(
        "--max-catchup-ticks",
        type=int,
        default=None,
        help="Aufhol-Phase deckeln: bei einer Lücke > N Ticks bei 'now' ansetzen statt "
        "alles nachzuholen (geloggte Lücke, Boot-Storm-Schutz). Default: lückenlos füllen.",
    )
    parser.add_argument(
        "--db-url", default=None, help="Override der Datenbank-URL (sonst aus .env)."
    )
    return parser


async def amain(
    argv: list[str] | None = None,
    *,
    settings: Settings | None = None,
    redactor: Redactor | None = None,
) -> int:
    """Async-Entrypoint: parst Argumente, baut Engine/Session und fährt den Worker."""
    args = build_argparser().parse_args(argv)
    cfg = settings or get_settings()
    database_url = args.db_url or cfg.database_url

    pseudonymizer = build_pseudonymizer(cfg)
    used_redactor = redactor or build_redactor()
    substrate = SubstrateClient.from_settings(cfg) if cfg.substrate_base_url else None

    # Dedizierte Verbindung für den Dauerlauf (NullPool: genau eine, langlebig).
    engine = create_async_engine(database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    try:
        async with maker() as session:
            logger.info(
                "🔴 Live-Daten-Stream startet: interval=%.3gs seed=%s max_ticks=%s",
                args.interval_seconds,
                args.seed,
                args.max_ticks,
            )
            stats = await run_live_worker(
                session,
                interval_seconds=args.interval_seconds,
                seed=args.seed,
                batch_size=args.batch_size,
                max_ticks=args.max_ticks,
                max_catchup_ticks=args.max_catchup_ticks,
                pseudonymizer=pseudonymizer,
                redactor=used_redactor,
                substrate=substrate,
            )
            # Nur erreichbar bei endlichem --max-ticks (Dauerlauf endet sonst nicht).
            logger.info("✅ Live-Lauf beendet: %d Readings geschrieben.", stats.readings_written)
    except (KeyboardInterrupt, asyncio.CancelledError):
        # Sauberer Stop (SIGINT/SIGTERM): der laufende, noch nicht committete Tick
        # geht verloren — der Neustart setzt am letzten committeten Stempel an.
        logger.info("🟡 Live-Daten-Stream gestoppt — Neustart setzt am letzten Stempel an.")
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
