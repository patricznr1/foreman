# ============================================================
#  FOREMAN — tests/integration/test_drift_profile_persistence.py
#  Zweck: F4-Eigenprofil-Persistenz (Reasoner #2). Ein echter Replay-Lauf über die
#         F3-Szenario-Readings persistiert je analogem Datenpunkt das Eigenprofil
#         (drift_profiles): Median je Betriebszustand + die eingefrorene Rausch-
#         Streuung + Profil-Stand. Ein zu kurzer Lauf (Warm-up nicht erreicht)
#         persistiert KEIN Profil (ehrlich leer, nicht geraten).
#  Architektur-Einordnung: Quality Gate §10.3 (Integration, echte TimescaleDB).
# ============================================================
from __future__ import annotations

import asyncpg
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.adapters.simulation.adapter import SimulationAdapter
from foreman.adapters.simulation.runner import run_ingestion
from foreman.adapters.simulation.scenario import load_scenario_by_name
from foreman.core.pseudonymize import Pseudonymizer
from foreman.core.redact import Redactor
from foreman.db.models import DriftProfile, Machine
from foreman.reasoners.drift.baseline import BASELINE_WINDOW
from foreman.reasoners.drift.detector import WARMUP_MIN_SAMPLES
from foreman.reasoners.drift.relevance import DEFAULT_MIN_EFFECT_SIZE
from foreman.reasoners.drift.runner import replay_machine

pytestmark = pytest.mark.integration


async def _seed_scenario(
    scenario_name: str,
    session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    redactor: Redactor,
) -> int:
    """Backfillt ein Szenario in readings_1m und gibt die machine_id zurück."""
    scenario = load_scenario_by_name(scenario_name)
    adapter = SimulationAdapter(scenario, seed=1)
    # CAgg von Vortest-Daten befreien (clean_db truncated nur die Basis-Tabelle).
    await raw_conn.execute(
        "CALL refresh_continuous_aggregate('readings_1m', "
        "'2000-01-01 00:00:00+00', '2100-01-01 00:00:00+00')"
    )
    await run_ingestion(
        session, adapter, mode="backfill", pseudonymizer=pseudonymizer, redactor=redactor
    )
    await raw_conn.execute("CALL refresh_continuous_aggregate('readings_1m', NULL, NULL)")
    machine = (await session.scalars(select(Machine))).first()
    assert machine is not None
    return machine.id


async def test_run_machine_persistiert_eigenprofil(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    # healthy_baseline (10 Tage, kein Verschleiß) -> der Detektor etabliert je
    # analogem Datenpunkt eine Streuung + Zustands-Mediane -> ein Profil entsteht.
    machine_id = await _seed_scenario(
        "healthy_baseline", db_session, raw_conn, pseudonymizer, fake_redactor
    )
    scenario = load_scenario_by_name("healthy_baseline")
    start = scenario.start_utc
    end = scenario.start_utc + scenario.duration_delta

    await replay_machine(db_session, machine_id, start, end)
    await db_session.commit()

    profiles = list((await db_session.scalars(select(DriftProfile))).all())
    assert profiles, "Replay muss je analogem Datenpunkt ein Eigenprofil persistieren"
    for profile in profiles:
        assert profile.machine_id == machine_id
        # Die echte Detektor-Basis: etablierte Streuung + Schwellenfaktor des Laufs.
        assert profile.noise_sigma > 0.0
        assert profile.effect_size_k == DEFAULT_MIN_EFFECT_SIZE
        # Profil-Stand = Ende des Replay-Fensters (keine vorgetäuschte Live-Aktualität).
        assert profile.computed_at == end
        assert profile.window_samples == BASELINE_WINDOW
        assert profile.warmup_samples == WARMUP_MIN_SAMPLES
        assert profile.total_samples >= WARMUP_MIN_SAMPLES
        # Mindestens ein Betriebszustand, jeder mit Median + ausreichender Stichprobe.
        assert profile.state_medians
        for entry in profile.state_medians.values():
            assert "median" in entry
            assert entry["sample_count"] >= 10


async def test_kurzer_lauf_persistiert_kein_profil(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    # Ein Fenster unterhalb der Warm-up-Schwelle -> keine etablierte Streuung ->
    # kein Profil (ehrlich leer, nicht geraten).
    from datetime import timedelta

    machine_id = await _seed_scenario(
        "healthy_baseline", db_session, raw_conn, pseudonymizer, fake_redactor
    )
    scenario = load_scenario_by_name("healthy_baseline")
    start = scenario.start_utc

    await replay_machine(db_session, machine_id, start, start + timedelta(minutes=30))
    await db_session.commit()

    profiles = list((await db_session.scalars(select(DriftProfile))).all())
    assert profiles == [], "Unter der Warm-up-Schwelle darf kein Profil entstehen"
