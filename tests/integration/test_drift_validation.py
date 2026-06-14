# ============================================================
#  FOREMAN — tests/integration/test_drift_validation.py
#  Zweck: Validierungs-Suite des Drift-Reasoners gegen die F3-Szenarien (F4,
#  Kern der Abnahme). Replay der Szenario-Readings durch den Reasoner; Prüfung,
#  dass injizierte Drift im ground_truth-Fenster nach t* erkannt wird und
#  healthy_baseline KEINEN Fehlalarm auslöst.
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
from foreman.db.models import DataPoint, Machine
from foreman.reasoners.drift.runner import replay_machine
from foreman.reasoners.drift.service import DriftFinding
from foreman.reasoners.drift.validation import (
    DriftMetrics,
    ScenarioTruth,
    compute_metrics,
    load_truth,
)

pytestmark = pytest.mark.integration


async def _seed_replay_evaluate(
    scenario_name: str,
    session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    redactor: Redactor,
) -> tuple[list[DriftFinding], DriftMetrics, ScenarioTruth]:
    scenario = load_scenario_by_name(scenario_name)
    adapter = SimulationAdapter(scenario, seed=1)
    # 0. readings_1m von Daten eines vorherigen Tests befreien: clean_db truncated
    #    nur die Basis-Tabelle readings (RESTART IDENTITY recycelt data_point-IDs),
    #    NICHT die materialisierte CAgg. Ein breiter Refresh auf die jetzt leeren
    #    readings setzt die CAgg zurück (Test-Isolation).
    await raw_conn.execute(
        "CALL refresh_continuous_aggregate('readings_1m', "
        "'2000-01-01 00:00:00+00', '2100-01-01 00:00:00+00')"
    )
    # 1. Backfill: schreibt readings (committet intern).
    await run_ingestion(
        session, adapter, mode="backfill", pseudonymizer=pseudonymizer, redactor=redactor
    )
    # 2. readings_1m aktualisieren (autocommit über die asyncpg-Verbindung).
    await raw_conn.execute("CALL refresh_continuous_aggregate('readings_1m', NULL, NULL)")

    # 3. Topologie auflösen. ground_truth referenziert den Szenario-KEY (z. B.
    #    'vib_rms'); die DB trägt den NAME (z. B. 'vibration_rms_...'). Mappe daher
    #    data_point-DB-ID -> Szenario-KEY über (name -> key) aus dem Szenario.
    machine = (await session.scalars(select(Machine))).first()
    assert machine is not None
    data_points = (
        await session.scalars(select(DataPoint).where(DataPoint.machine_id == machine.id))
    ).all()
    name_to_key = {dp.name: dp.key for dp in scenario.data_points}
    key_by_id = {dp.id: name_to_key.get(dp.name, dp.name) for dp in data_points}

    # 4. Replay über den Szenario-Zeitraum.
    start = scenario.start_utc
    end = scenario.start_utc + scenario.duration_delta
    findings = await replay_machine(session, machine.id, start, end)
    await session.commit()

    truth = load_truth(scenario)
    metrics = compute_metrics(findings, key_by_id, truth)
    return findings, metrics, truth


async def test_bearing_drift_mit_nuetzlichem_vorlauf_erkannt(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    # Vibrations-Drift wird nach t* und VOR dem narrativen Anker (Temperatur-Alarm
    # 17d08h, Werker-Notiz ~16d) erkannt — der Frühwarn-Nutzen ist erfüllt.
    _, metrics, _ = await _seed_replay_evaluate(
        "bearing_drift", db_session, raw_conn, pseudonymizer, fake_redactor
    )
    assert metrics.detected_with_useful_lead, f"bearing_drift ohne Vorlauf: {metrics}"
    assert metrics.control_alarms == 0
    assert metrics.false_alarms == 0


async def test_tool_wear_mit_nuetzlichem_vorlauf_erkannt(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    # Drehmoment-/Last-Drift vor dem Last-Alarm (9d12h) erkannt.
    _, metrics, _ = await _seed_replay_evaluate(
        "tool_wear", db_session, raw_conn, pseudonymizer, fake_redactor
    )
    assert metrics.detected_with_useful_lead, f"tool_wear ohne Vorlauf: {metrics}"
    assert metrics.false_alarms == 0


async def test_lubrication_lager_b_erkannt_kontrolle_still(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    # Lager B (ungeeignetes Ersatzfett) driftet und wird erkannt; Lager A (korrekt
    # geschmiert, Kontrolle) darf NICHT melden.
    _, metrics, _ = await _seed_replay_evaluate(
        "lubrication_correlation", db_session, raw_conn, pseudonymizer, fake_redactor
    )
    assert metrics.detected_with_useful_lead, f"lubrication Lager B nicht erkannt: {metrics}"
    assert metrics.control_alarms == 0


async def test_healthy_baseline_loest_keinen_fehlalarm_aus(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    # Negativkontrolle: Schicht-Saisonalität + Wochenend-Stillstand OHNE Verschleiß
    # → keine einzige Drift-Meldung (Abnahmebedingung für Gating + Deseasonalisierung).
    findings, metrics, _ = await _seed_replay_evaluate(
        "healthy_baseline", db_session, raw_conn, pseudonymizer, fake_redactor
    )
    assert metrics.false_alarms == 0, f"healthy_baseline Fehlalarm: {metrics}"
    assert len(findings) == 0
