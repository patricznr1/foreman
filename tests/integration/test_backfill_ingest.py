# ============================================================
#  FOREMAN — tests/integration/test_backfill_ingest.py
#  Zweck: Pflicht-Test: backfill schreibt Readings über den COPY-Pfad; PK
#  (data_point_id, time) greift; analoge + digitale Signale, production_runs und
#  Alarme landen. Plus: live-Modus streamt im Wall-Clock-Takt (kurzer Lauf).
#  Architektur-Einordnung: Quality Gate §10.3 (Integration, braucht DB).
# ============================================================
from __future__ import annotations

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.adapters.simulation.adapter import SimulationAdapter
from foreman.adapters.simulation.runner import WallClockPacer, run_ingestion
from foreman.adapters.simulation.scenario import Scenario, load_scenario_by_name
from foreman.core.pseudonymize import Pseudonymizer
from foreman.core.redact import Redactor
from foreman.ingestion.service import IngestionService

pytestmark = pytest.mark.integration


async def test_backfill_schreibt_readings_und_diskrete_ereignisse(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    adapter = SimulationAdapter(load_scenario_by_name("minimal_bearing_drift"), seed=1)
    service = IngestionService(
        db_session, pseudonymizer=pseudonymizer, redactor=fake_redactor, batch_size=500
    )

    stats = await service.ingest(adapter)

    # Readings über COPY geschrieben.
    readings_count = await raw_conn.fetchval("SELECT count(*) FROM readings")
    assert readings_count == stats.readings_written > 0

    # Analoge UND digitale Signale liegen vor.
    kinds = {
        row["kind"]
        for row in await raw_conn.fetch(
            "SELECT DISTINCT dp.kind FROM readings r JOIN data_points dp ON dp.id = r.data_point_id"
        )
    }
    assert {"analog", "digital"} <= kinds

    # Digitale Werte sind 0/1 (machine_running).
    digital_values = {
        row["value"]
        for row in await raw_conn.fetch(
            "SELECT DISTINCT r.value FROM readings r "
            "JOIN data_points dp ON dp.id = r.data_point_id WHERE dp.kind = 'digital'"
        )
    }
    assert digital_values <= {0.0, 1.0}

    # production_runs + Alarme gelandet.
    assert await raw_conn.fetchval("SELECT count(*) FROM production_runs") == 2
    assert await raw_conn.fetchval("SELECT count(*) FROM alarms") == 1
    assert stats.production_runs == 2
    assert stats.alarms == 1

    # source = 'simulation' (kein reales Protokoll getarnt).
    sources = {
        row["source"] for row in await raw_conn.fetch("SELECT DISTINCT source FROM data_points")
    }
    assert sources == {"simulation"}


async def test_pk_data_point_id_time_greift_bei_doppeltem_backfill(
    db_session: AsyncSession,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    # Zweimal dasselbe Szenario → identische (data_point_id, time)-Schlüssel →
    # der Composite-PK muss den zweiten COPY mit UniqueViolation abweisen.
    adapter1 = SimulationAdapter(load_scenario_by_name("minimal_steady"), seed=1)
    service1 = IngestionService(db_session, pseudonymizer=pseudonymizer, redactor=fake_redactor)
    await service1.ingest(adapter1)

    adapter2 = SimulationAdapter(load_scenario_by_name("minimal_steady"), seed=1)
    service2 = IngestionService(db_session, pseudonymizer=pseudonymizer, redactor=fake_redactor)
    with pytest.raises(asyncpg.UniqueViolationError):
        await service2.ingest(adapter2)


def _tiny_live_scenario() -> Scenario:
    """Mini-Szenario (2h/30m = wenige Ticks) für den live-Modus-Test."""
    return Scenario.model_validate(
        {
            "schema_version": 1,
            "scenario": {
                "name": "live_tiny",
                "start": "2026-05-04T07:00:00+02:00",
                "duration": "2h",
                "sample_interval": "30m",
            },
            "line": {"label": "Live-Linie"},
            "machine": {"external_id": "LIVE-1", "label": "Live-Maschine"},
            "components": [],
            "seasonality": {"shifts": {"frueh": {"from": "06:00", "to": "14:00"}}},
            "data_points": [
                {
                    "key": "state",
                    "name": "machine_running",
                    "machine_level": True,
                    "kind": "digital",
                    "unit": "bool",
                    "source": "simulation",
                    "baseline": {"driven_by": "shift_schedule"},
                },
                {
                    "key": "vib",
                    "name": "vib_live",
                    "kind": "analog",
                    "measurement_type": "signal",
                    "unit": "mm/s",
                    "source": "simulation",
                    "baseline": {"mean": 2.0, "noise_std": 0.1, "gated_by": "state"},
                },
            ],
        }
    )


async def test_live_modus_streamt_im_wall_clock_takt(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    # Sleep-Quelle injizieren: kein echtes Warten, aber Takt-Aufrufe zählbar.
    slept: list[float] = []

    async def _fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    # Hoher speed → minimale Soll-Delays; Sleep ohnehin gestubbt.
    pacer = WallClockPacer(speed=10_000.0, sleep=_fake_sleep)
    adapter = SimulationAdapter(_tiny_live_scenario(), seed=1)
    service = IngestionService(db_session, pseudonymizer=pseudonymizer, redactor=fake_redactor)

    stats = await service.ingest(adapter, pace=pacer)

    assert stats.readings_written > 0
    assert await raw_conn.fetchval("SELECT count(*) FROM readings") == stats.readings_written
    # Pacer wurde getaktet (pro Tick-Wechsel mind. einmal aufgerufen).
    assert pacer.tick_count >= 2


async def test_runner_run_ingestion_backfill(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    # Der testbare Runner-Kern (run_ingestion) fährt einen Backfill durch.
    adapter = SimulationAdapter(load_scenario_by_name("minimal_steady"), seed=2)
    stats = await run_ingestion(
        db_session,
        adapter,
        mode="backfill",
        pseudonymizer=pseudonymizer,
        redactor=fake_redactor,
    )
    assert stats.readings_written > 0
    assert await raw_conn.fetchval("SELECT count(*) FROM readings") == stats.readings_written
