# ============================================================
#  FOREMAN — tests/integration/test_live_worker.py
#  Zweck: Pflicht-Test (braucht DB): der Live-Daten-Stream-Worker setzt am
#         Historien-Ende an und tickt mit WALL-CLOCK-Stempeln weiter —
#         lückenlos, überlappungsfrei, neustart-fest, Historie unangetastet,
#         und das NOTIFY/WS-Push feuert je Commit.
#  Architektur-Einordnung: Quality Gate §10.3 (Integration, braucht DB).
# ============================================================
from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.adapters.simulation.live_worker import park_scenarios, run_live_worker
from foreman.adapters.simulation.park import park_scenario_paths
from foreman.adapters.simulation.scenario import Scenario, load_scenario_file
from foreman.adapters.simulation.seed import seed_topology
from foreman.core.pseudonymize import Pseudonymizer
from foreman.core.redact import Redactor
from foreman.ingestion.service import copy_readings
from foreman.realtime.channels import DASHBOARD_CHANNEL, decode_change

pytestmark = pytest.mark.integration

# Fester Historien-Anker in der Vergangenheit + Live-Takt (10-min-Gitter wie der Park).
_ANCHOR = datetime(2026, 6, 21, 6, 0, 0, tzinfo=UTC)
_INTERVAL_S = 600.0
_INTERVAL = timedelta(seconds=_INTERVAL_S)
# Wall-Clock weit in der Zukunft → alle Test-Ticks liegen in der „Vergangenheit",
# der RealTimePacer wartet also nie real (Aufhol-Pfad, deterministisch schnell).
_FAR_FUTURE = datetime(2030, 1, 1, 0, 0, 0, tzinfo=UTC)


def _scenario(stem: str) -> Scenario:
    for path in park_scenario_paths():
        if path.stem == stem:
            return load_scenario_file(path)
    raise AssertionError(f"Park-Szenario {stem} nicht gefunden")


async def _seed_history(session: AsyncSession, scenario: Scenario, *, at: datetime) -> list[int]:
    """Seedet die Topologie und legt EINEN Historien-Reading je Datenpunkt bei `at` an.

    Liefert die Datenpunkt-IDs (der Live-Anker muss exakt auf `at` fallen)."""
    topology = await seed_topology(session, scenario)
    dp_ids = list(topology.data_point_ids.values())
    await copy_readings(session, [(at, dp_id, 1.0, None) for dp_id in dp_ids])
    await session.commit()
    return dp_ids


async def test_park_scenarios_default_laedt_alle_zwoelf() -> None:
    # Der Default-Lauf (ohne Injektion) deckt den ganzen Park ab.
    scenarios = park_scenarios()
    assert len(scenarios) == 12
    assert all(isinstance(s, Scenario) for s in scenarios)


async def test_worker_setzt_lueckenlos_und_ueberlappungsfrei_am_ende_an(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    scenario = _scenario("park_ax01")
    dp_ids = await _seed_history(db_session, scenario, at=_ANCHOR)

    stats = await run_live_worker(
        db_session,
        scenarios=[scenario],
        interval_seconds=_INTERVAL_S,
        seed=7,
        max_ticks=3,
        pseudonymizer=pseudonymizer,
        redactor=fake_redactor,
        now=lambda: _FAR_FUTURE,
    )
    assert stats.readings_written > 0

    # Neue Stempel = anchor + k·interval (k=1..3): strikt nach dem Anker (kein Overlap),
    # lückenlos im 10-min-Takt (kein Gap), Wall-Clock-Achse fortgesetzt.
    new_times = await raw_conn.fetch(
        "SELECT DISTINCT time FROM readings r WHERE r.data_point_id = ANY($1::int[]) "
        "AND r.time > $2 ORDER BY time",
        dp_ids,
        _ANCHOR,
    )
    got = [row["time"] for row in new_times]
    expected = [_ANCHOR + k * _INTERVAL for k in (1, 2, 3)]
    assert got == expected

    # Historie unangetastet: der Anker-Stempel existiert weiter, genau einmal je Datenpunkt.
    history_count = await raw_conn.fetchval(
        "SELECT count(*) FROM readings WHERE data_point_id = ANY($1::int[]) AND time = $2",
        dp_ids,
        _ANCHOR,
    )
    assert history_count == len(dp_ids)


async def test_worker_neustart_fest_ohne_doppeln(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    scenario = _scenario("park_ax01")
    dp_ids = await _seed_history(db_session, scenario, at=_ANCHOR)

    async def _run(max_ticks: int) -> None:
        await run_live_worker(
            db_session,
            scenarios=[scenario],
            interval_seconds=_INTERVAL_S,
            seed=7,
            max_ticks=max_ticks,
            pseudonymizer=pseudonymizer,
            redactor=fake_redactor,
            now=lambda: _FAR_FUTURE,
        )

    await _run(3)  # → anchor+10/20/30m
    await _run(2)  # Neustart: Anker neu aus DB = anchor+30m → +40/50m, kein Doppel

    # Genau ein Reading je (Datenpunkt, Zeit) — kein Overlap/keine Dublette (PK-Beweis).
    dup = await raw_conn.fetchval(
        "SELECT count(*) FROM (SELECT data_point_id, time FROM readings "
        "WHERE data_point_id = ANY($1::int[]) GROUP BY data_point_id, time "
        "HAVING count(*) > 1) d",
        dp_ids,
    )
    assert dup == 0

    # Lückenlose, monotone Fortsetzung über beide Läufe: anchor .. anchor+50m.
    distinct_times = await raw_conn.fetch(
        "SELECT DISTINCT time FROM readings WHERE data_point_id = ANY($1::int[]) ORDER BY time",
        dp_ids,
    )
    times = [row["time"] for row in distinct_times]
    assert times == [_ANCHOR + k * _INTERVAL for k in range(0, 6)]


async def test_worker_feuert_ws_push_notify(
    db_session: AsyncSession,
    raw_conn: asyncpg.Connection,
    pseudonymizer: Pseudonymizer,
    fake_redactor: Redactor,
) -> None:
    scenario = _scenario("park_ax01")
    await _seed_history(db_session, scenario, at=_ANCHOR)

    received: list[str] = []

    def _on_notify(_conn: object, _pid: int, _channel: str, payload: str) -> None:
        received.append(payload)

    await raw_conn.add_listener(DASHBOARD_CHANNEL, _on_notify)
    try:
        await run_live_worker(
            db_session,
            scenarios=[scenario],
            interval_seconds=_INTERVAL_S,
            seed=7,
            max_ticks=2,
            pseudonymizer=pseudonymizer,
            redactor=fake_redactor,
            now=lambda: _FAR_FUTURE,
        )
        # NOTIFY wird beim Commit zugestellt — der Listener-Verbindung Zeit geben,
        # beide erwarteten Benachrichtigungen (ein NOTIFY je committetem Tick) zu sehen.
        for _ in range(40):
            if len(received) >= 2:
                break
            await raw_conn.execute("SELECT 1")
            await asyncio.sleep(0.05)
    finally:
        await raw_conn.remove_listener(DASHBOARD_CHANNEL, _on_notify)

    # Genau EIN gebündeltes NOTIFY je Commit/Tick (Vorgabe 4) — nicht eines je Zeile.
    assert len(received) == 2, f"erwartet 2 NOTIFYs (1 je Tick), erhalten {len(received)}"
    changes = [decode_change(p) for p in received]
    assert all("reading" in c.kinds or c.data_points or c.broad for c in changes)
