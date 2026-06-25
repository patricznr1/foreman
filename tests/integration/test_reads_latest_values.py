# ============================================================
#  FOREMAN — tests/integration/test_reads_latest_values.py
#  Zweck: Read-Core Latest-Value (F5 — lebende Maschinenkarte). Der jüngste Wert
#         JE DATENPUNKT (last_value des neuesten readings_1m-Buckets) + dessen
#         Zeitstempel — günstig über die Minuten-Aggregat-Sicht, kein Full-Scan.
#         Speist last_value/last_value_at der kanonischen Karte.
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from foreman.db.models import DataPoint, Machine
from foreman.ingestion.service import copy_readings
from foreman.reads.queries import latest_values_for_data_points, machines_for_data_points

pytestmark = pytest.mark.integration


async def _analog_point(session: object, *, name: str) -> DataPoint:
    machine = Machine(label=f"M-{name}")
    session.add(machine)  # type: ignore[attr-defined]
    await session.flush()  # type: ignore[attr-defined]
    data_point = DataPoint(machine_id=machine.id, name=name, kind="analog", unit="A")
    session.add(data_point)  # type: ignore[attr-defined]
    await session.flush()  # type: ignore[attr-defined]
    return data_point


async def test_latest_value_returns_newest_bucket_per_data_point(db_session: object) -> None:
    dp = await _analog_point(db_session, name="motor_current")
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    older = now - timedelta(minutes=2)
    # Zwei Minuten-Buckets — der jüngste (now, 26.2) gewinnt.
    await copy_readings(db_session, [(older, dp.id, 10.0, None)])  # type: ignore[arg-type]
    await copy_readings(db_session, [(now, dp.id, 26.2, None)])  # type: ignore[arg-type]
    await db_session.commit()  # type: ignore[attr-defined]

    latest = await latest_values_for_data_points(db_session, [dp.id])  # type: ignore[arg-type]

    assert dp.id in latest
    assert latest[dp.id].value == 26.2
    assert latest[dp.id].at == now


async def test_latest_value_omits_data_points_without_readings(db_session: object) -> None:
    dp = await _analog_point(db_session, name="silent")

    latest = await latest_values_for_data_points(db_session, [dp.id])  # type: ignore[arg-type]

    # Ehrlich leer — kein erfundener Wert für einen Datenpunkt ohne Readings.
    assert dp.id not in latest


async def test_latest_value_empty_input_returns_empty(db_session: object) -> None:
    latest = await latest_values_for_data_points(db_session, [])  # type: ignore[arg-type]
    assert latest == {}


async def test_machines_for_data_points_resolves_all_owning_machines(db_session: object) -> None:
    # Die NOTIFY-Anreicherung muss bei Readings über mehrere Maschinen ALLE
    # betroffenen Maschinen auflösen (sonst rückt eine Karte nicht live nach).
    dp_a = await _analog_point(db_session, name="a")
    dp_b = await _analog_point(db_session, name="b")

    machines = await machines_for_data_points(db_session, [dp_a.id, dp_b.id])  # type: ignore[arg-type]

    assert machines == {dp_a.machine_id, dp_b.machine_id}


async def test_machines_for_data_points_empty_input_returns_empty(db_session: object) -> None:
    assert await machines_for_data_points(db_session, []) == set()  # type: ignore[arg-type]
