# ============================================================
#  FOREMAN — tests/integration/test_park_seed.py
#  Zweck: Pflicht-Test (braucht DB): der Twin-Park "Montagelinie 1" seedet
#         idempotent zu EINER Linie mit 12 Maschinen; ein Backfill erzeugt fuer
#         kranke und gesunde Schwestern plausible Readings (Drift vs. stabil);
#         maintenance_events landen; die D-Kette ist zeitlich korrekt gestaffelt
#         (Oberlauf vor Unterlauf).
#  Architektur-Einordnung: Quality Gate §10.3 (Integration, braucht DB).
# ============================================================
from __future__ import annotations

from pathlib import Path

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.adapters.simulation.adapter import SimulationAdapter
from foreman.adapters.simulation.park import (
    PARK_LINE_LABEL,
    park_scenario_paths,
    run_park,
)
from foreman.adapters.simulation.scenario import load_scenario_file
from foreman.adapters.simulation.seed import seed_topology
from foreman.core.pseudonymize import Pseudonymizer
from foreman.core.redact import Redactor
from foreman.ingestion.service import IngestionService

pytestmark = pytest.mark.integration


def _scenario_path(stem: str) -> Path:
    for path in park_scenario_paths():
        if path.stem == stem:
            return path
    raise AssertionError(f"Park-Szenario {stem} nicht gefunden")


async def test_park_seed_idempotent_eine_linie_zwoelf_maschinen(
    db_session: AsyncSession, raw_conn: asyncpg.Connection
) -> None:
    # Erstes Seeding aller 12 Park-Topologien (gemeinsame line.label).
    for path in park_scenario_paths():
        await seed_topology(db_session, load_scenario_file(path))
    await db_session.commit()

    line_count = await raw_conn.fetchval("SELECT count(*) FROM lines")
    machine_count = await raw_conn.fetchval("SELECT count(*) FROM machines")
    label = await raw_conn.fetchval("SELECT label FROM lines LIMIT 1")
    assert line_count == 1, "gemeinsame line.label muss genau EINE Linie ergeben"
    assert machine_count == 12
    assert label == PARK_LINE_LABEL

    # Alle 12 haengen an derselben Linie.
    distinct_line_ids = await raw_conn.fetchval("SELECT count(DISTINCT line_id) FROM machines")
    assert distinct_line_ids == 1

    # Zweites Seeding legt nichts doppelt an (Idempotenz ueber natuerliche Schluessel).
    for path in park_scenario_paths():
        await seed_topology(db_session, load_scenario_file(path))
    await db_session.commit()
    assert await raw_conn.fetchval("SELECT count(*) FROM lines") == 1
    assert await raw_conn.fetchval("SELECT count(*) FROM machines") == 12


async def test_backfill_kranke_und_gesunde_schwester(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    # Eine kranke (AX-02, falscher Schmierstoff) und ihre gesunde Kontroll-Schwester
    # (AX-01) durch den Backfill fahren.
    for stem in ("park_ax01", "park_ax02"):
        adapter = SimulationAdapter(load_scenario_file(_scenario_path(stem)), seed=7)
        await IngestionService(
            db_session, pseudonymizer=pseudonymizer, redactor=fake_redactor, batch_size=5000
        ).ingest(adapter)

    # Beide Schwestern haben Readings erzeugt.
    for external_id in ("AX-01", "AX-02"):
        count = await raw_conn.fetchval(
            "SELECT count(*) FROM readings r "
            "JOIN data_points dp ON dp.id = r.data_point_id "
            "JOIN machines m ON m.id = dp.machine_id WHERE m.external_id = $1",
            external_id,
        )
        assert count > 0, f"{external_id}: keine Readings erzeugt"

    # Verhaltensbeleg: die kranke Schwester (AX-02) treibt die Lagerschwingung in
    # Zone D, die gesunde Kontrolle (AX-01) bleibt im Normalband.
    async def _max_vibration(external_id: str) -> float:
        value = await raw_conn.fetchval(
            "SELECT max(r.value) FROM readings r "
            "JOIN data_points dp ON dp.id = r.data_point_id "
            "JOIN machines m ON m.id = dp.machine_id "
            "WHERE m.external_id = $1 AND dp.name = 'axis_bearing_vibration'",
            external_id,
        )
        return float(value)

    max_sick = await _max_vibration("AX-02")
    max_healthy = await _max_vibration("AX-01")
    assert max_sick > 5.0, f"AX-02 sollte deutliche Drift zeigen, max={max_sick}"
    assert max_healthy < 3.5, f"AX-01 (Kontrolle) muss stabil bleiben, max={max_healthy}"

    # maintenance_events beider Schwestern persistiert, performed_by tokenisiert.
    rows = await raw_conn.fetch("SELECT type, performed_by FROM maintenance_events")
    assert len(rows) >= 2
    for row in rows:
        assert row["performed_by"] is not None
        assert not str(row["performed_by"]).startswith("PSEUDO_"), "Klartext-Ref nicht tokenisiert"


async def test_d_kette_zeitlich_gestaffelt_oberlauf_vor_unterlauf(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    # Die drei Kettenglieder fahren (Reihenfolge der Ingestion irrelevant — die
    # zeitliche Folge steckt in den Event-Offsets, nicht in der Lade-Reihenfolge).
    for stem in ("park_vs01", "park_pr02", "park_fd02"):
        adapter = SimulationAdapter(load_scenario_file(_scenario_path(stem)), seed=7)
        await IngestionService(
            db_session, pseudonymizer=pseudonymizer, redactor=fake_redactor
        ).ingest(adapter)

    # Ketten-Kopf: fruehste Werker-Notiz an FD-02.
    fd02_note = await raw_conn.fetchval(
        "SELECT min(wn.created_at) FROM worker_notes wn "
        "JOIN machines m ON m.id = wn.machine_id WHERE m.external_id = 'FD-02'"
    )
    # Ketten-Mitte: Unterfuellungs-Alarm an PR-02.
    pr02_underfill = await raw_conn.fetchval(
        "SELECT raised_at FROM alarms WHERE code = 'PART_UNDERFILL'"
    )
    # Ketten-Endpunkt: Ausschuss-Alarm an VS-01.
    vs01_reject = await raw_conn.fetchval(
        "SELECT raised_at FROM alarms WHERE code = 'REJECT_RATE_HIGH'"
    )

    assert fd02_note is not None and pr02_underfill is not None and vs01_reject is not None
    # Oberlauf vor Unterlauf: FD-02 (Dosis) -> PR-02 (Unterfuellung) -> VS-01 (Ausschuss).
    assert fd02_note < pr02_underfill < vs01_reject


async def test_run_park_faehrt_alle_zwoelf(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    # Der Orchestrator-Kern faehrt den ganzen Park in einer Session.
    results = await run_park(
        db_session,
        mode="backfill",
        seed=7,
        pseudonymizer=pseudonymizer,
        redactor=fake_redactor,
    )
    assert len(results) == 12
    assert all(stats.readings_written > 0 for stats in results.values())
    # Genau eine Linie mit 12 Maschinen, alle Readings auf derselben Linie.
    assert await raw_conn.fetchval("SELECT count(*) FROM lines") == 1
    assert await raw_conn.fetchval("SELECT count(*) FROM machines") == 12
