# ============================================================
#  FOREMAN — adapters/simulation/park.py
#  Zweck: Schlanker Park-Seed-Orchestrator (F3) — seedet/ingestiert die 12
#         Park-Szenarien der "Montagelinie 1" nacheinander an DIESELBE Linie.
#         Der runner.py laedt nur EIN Szenario je Aufruf; dieser Orchestrator
#         faehrt die ganze Park-Linie mit einem Befehl.
#  Architektur-Einordnung: Datenakquise (Schicht 2). REINE Orchestrierung —
#         keine Engine-/Signal-/Schema-Logik. Jede Maschine ist eine eigene
#         Szenario-Datei (park_*.yaml) mit gemeinsamer line.label; der Park
#         entsteht ohne Schema-Aenderung (seed.py schluesselt die Linie auf label).
#  Aufruf: python -m foreman.adapters.simulation.park --mode backfill|live
#          [--seed --batch-size --db-url]
# ============================================================
from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from foreman.adapters.simulation.adapter import SimulationAdapter
from foreman.adapters.simulation.runner import DEFAULT_LIVE_SPEED, run_ingestion
from foreman.adapters.simulation.scenario import SCENARIOS_DIR
from foreman.config import Settings, get_settings
from foreman.core.pseudonymize import Pseudonymizer, build_pseudonymizer
from foreman.core.redact import Redactor, build_redactor
from foreman.ingestion.service import IngestStats
from foreman.logging_setup import setup_logging
from foreman.substrate.client import SubstrateClient

logger = logging.getLogger("foreman.adapters.simulation.park")

# Gemeinsame Linie aller Park-Szenarien (Idempotenz-Schluessel in seed.py).
PARK_LINE_LABEL = "Montagelinie 1"
# Namens-Praefix der Park-Szenariodateien (eine Datei je Maschine).
PARK_SCENARIO_PREFIX = "park_"


def park_scenario_paths() -> list[Path]:
    """Alle Park-Szenariodateien (park_*.yaml), deterministisch sortiert."""
    return sorted(SCENARIOS_DIR.glob(f"{PARK_SCENARIO_PREFIX}*.yaml"))


async def run_park(
    session: AsyncSession,
    *,
    mode: str = "backfill",
    seed: int | None = None,
    end_anchor: datetime | None = None,
    speed: float = DEFAULT_LIVE_SPEED,
    batch_size: int = 5000,
    pseudonymizer: Pseudonymizer,
    redactor: Redactor,
    substrate: SubstrateClient | None = None,
) -> dict[str, IngestStats]:
    """Testbarer Kern: seedet + ingestiert alle Park-Szenarien in derselben Session.

    Jede Datei laeuft durch den unveraenderten run_ingestion-Pfad (eigenes
    idempotentes Topologie-Seeding; ingest() committet je Szenario). Da alle
    Dateien dieselbe line.label tragen, haengen ihre Maschinen an EINER Linie.
    Liefert die Statistik je Szenario-Name.
    """
    paths = park_scenario_paths()
    if not paths:
        raise FileNotFoundError(
            f"Keine Park-Szenarien ({PARK_SCENARIO_PREFIX}*.yaml) in {SCENARIOS_DIR} gefunden."
        )
    results: dict[str, IngestStats] = {}
    for path in paths:
        adapter = SimulationAdapter.from_config(
            scenario_path=str(path), seed=seed, end_anchor=end_anchor
        )
        logger.info("🏭 Park-Szenario %s -> Linie %r", path.stem, PARK_LINE_LABEL)
        results[path.stem] = await run_ingestion(
            session,
            adapter,
            mode=mode,
            speed=speed,
            batch_size=batch_size,
            pseudonymizer=pseudonymizer,
            redactor=redactor,
            substrate=substrate,
        )
    return results


def build_argparser() -> argparse.ArgumentParser:
    """Baut den CLI-Parser fuer den Park-Orchestrator."""
    parser = argparse.ArgumentParser(
        prog="foreman-park",
        description="FOREMAN Twin-Park 'Montagelinie 1' — seedet alle Park-Szenarien.",
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
    parser.add_argument("--batch-size", type=int, default=5000, help="COPY-Batch-Groesse.")
    parser.add_argument(
        "--db-url", default=None, help="Override der Datenbank-URL (sonst aus .env)."
    )
    parser.add_argument(
        "--anchor-now",
        action="store_true",
        help="Backfill-Ende auf 'jetzt' (UTC) verschieben statt fester Szenario-Zeit — "
        "haelt die Demo-Daten frisch. Erhaelt die relative Struktur (Offsets/Saisonalitaet).",
    )
    return parser


async def amain(
    argv: list[str] | None = None,
    *,
    settings: Settings | None = None,
    redactor: Redactor | None = None,
) -> int:
    """Async-Entrypoint: parst Argumente, baut Engine/Session und faehrt den Park."""
    args = build_argparser().parse_args(argv)
    cfg = settings or get_settings()
    database_url = args.db_url or cfg.database_url
    end_anchor = datetime.now(UTC) if args.anchor_now else None

    pseudonymizer = build_pseudonymizer(cfg)
    used_redactor = redactor or build_redactor()
    substrate = SubstrateClient.from_settings(cfg) if cfg.substrate_base_url else None

    engine = create_async_engine(database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    try:
        async with maker() as session:
            logger.info(
                "🔄 Starte Park-Ingestion (mode=%s, seed=%s, anchor_now=%s)",
                args.mode,
                args.seed,
                args.anchor_now,
            )
            results = await run_park(
                session,
                mode=args.mode,
                seed=args.seed,
                end_anchor=end_anchor,
                speed=args.speed,
                batch_size=args.batch_size,
                pseudonymizer=pseudonymizer,
                redactor=used_redactor,
                substrate=substrate,
            )
            total_readings = sum(stats.readings_written for stats in results.values())
            logger.info(
                "✅ Park fertig: %d Szenarien, %d Readings gesamt auf Linie %r.",
                len(results),
                total_readings,
                PARK_LINE_LABEL,
            )
    finally:
        await engine.dispose()
        if substrate is not None:
            await substrate.aclose()
    return 0


def main() -> None:  # pragma: no cover — duenner Sync-Wrapper um amain
    """Synchroner Konsolen-Entrypoint (python -m …)."""
    setup_logging()
    raise SystemExit(asyncio.run(amain()))


if __name__ == "__main__":  # pragma: no cover
    main()
