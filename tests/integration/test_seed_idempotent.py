# ============================================================
#  FOREMAN — tests/integration/test_seed_idempotent.py
#  Zweck: Pflicht-Test: Topologie-Seeding ist idempotent (zweiter Lauf legt
#  nichts doppelt an) und löst stabile DB-IDs auf.
#  Architektur-Einordnung: Quality Gate §10.3 (Integration, braucht DB).
# ============================================================
from __future__ import annotations

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.adapters.simulation.scenario import load_scenario_by_name
from foreman.adapters.simulation.seed import seed_topology

pytestmark = pytest.mark.integration


async def _counts(conn: asyncpg.Connection) -> dict[str, int]:
    return {
        table: await conn.fetchval(f"SELECT count(*) FROM {table}")
        for table in ("lines", "machines", "components", "data_points")
    }


async def test_seed_topology_ist_idempotent(
    db_session: AsyncSession, raw_conn: asyncpg.Connection
) -> None:
    scenario = load_scenario_by_name("minimal_bearing_drift")

    first = await seed_topology(db_session, scenario)
    await db_session.commit()
    counts_after_first = await _counts(raw_conn)

    second = await seed_topology(db_session, scenario)
    await db_session.commit()
    counts_after_second = await _counts(raw_conn)

    # Zweiter Lauf legt nichts doppelt an.
    assert counts_after_first == counts_after_second
    # Eine Linie, eine Maschine, zwei Komponenten, drei Datenpunkte.
    assert counts_after_first == {"lines": 1, "machines": 1, "components": 2, "data_points": 3}
    # Gleiche IDs aufgelöst (stabile natürliche Schlüssel).
    assert first.data_point_ids == second.data_point_ids
    assert first.machine_id == second.machine_id


async def test_seed_teilt_linie_und_maschine_ueber_szenarien(
    db_session: AsyncSession, raw_conn: asyncpg.Connection
) -> None:
    # bearing_drift und healthy_baseline teilen Linie ("Zerspanung Linie 1")
    # und Maschine (external_id SIM-CNC-001) → keine Duplikate.
    bearing = await seed_topology(db_session, load_scenario_by_name("bearing_drift"))
    await db_session.commit()
    healthy = await seed_topology(db_session, load_scenario_by_name("healthy_baseline"))
    await db_session.commit()

    assert bearing.machine_id == healthy.machine_id  # geteilte Maschine
    assert await raw_conn.fetchval("SELECT count(*) FROM machines") == 1
    assert await raw_conn.fetchval("SELECT count(*) FROM lines") == 1
