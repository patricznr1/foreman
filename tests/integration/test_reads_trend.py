# ============================================================
#  FOREMAN — tests/integration/test_reads_trend.py
#  Zweck: Read-Core Trend (F5) — aggregierter readings_1m-Trend eines Datenpunkts
#         plus statisches Normalband (normal_min/normal_max). Verifiziert
#         INSBESONDERE die CAGG-Aktualität (Vorgabe 1): der jüngste, noch nicht
#         materialisierte Bucket ist via real-time aggregation sichtbar, OHNE
#         refresh_continuous_aggregate — sonst hinkte die "live"-Kurve hinterher.
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from foreman.db.models import DataPoint, Machine
from foreman.ingestion.service import copy_readings
from foreman.reads.trend import build_trend, build_trend_by_id

pytestmark = pytest.mark.integration


async def _machine_with_analog_point(
    session: object, *, name: str = "vibration"
) -> tuple[Machine, DataPoint]:
    machine = Machine(label="M1")
    session.add(machine)  # type: ignore[attr-defined]
    await session.flush()  # type: ignore[attr-defined]
    data_point = DataPoint(
        machine_id=machine.id,
        name=name,
        kind="analog",
        unit="mm/s",
        measurement_type="speed",
        normal_min=0.0,
        normal_max=5.0,
    )
    session.add(data_point)  # type: ignore[attr-defined]
    await session.flush()  # type: ignore[attr-defined]
    return machine, data_point


async def test_trend_surfaces_current_bucket_without_cagg_refresh(db_session: object) -> None:
    """Vorgabe 1: real-time aggregation zeigt den frischen Bucket ohne Refresh."""
    machine, data_point = await _machine_with_analog_point(db_session)
    bucket_time = datetime.now(UTC).replace(second=0, microsecond=0)
    # Schreiben über den geteilten COPY-Pfad — und BEWUSST KEIN
    # refresh_continuous_aggregate danach.
    await copy_readings(db_session, [(bucket_time, data_point.id, 2.5, None)])  # type: ignore[arg-type]
    await db_session.commit()  # type: ignore[attr-defined]

    trend = await build_trend(
        db_session,  # type: ignore[arg-type]
        machine.id,
        "vibration",
        start=bucket_time - timedelta(hours=1),
        end=bucket_time + timedelta(minutes=1),
    )

    assert trend is not None
    assert len(trend.points) >= 1, "real-time aggregation muss den frischen Bucket zeigen"
    assert trend.points[-1].avg == 2.5


async def test_trend_carries_static_normal_band_and_metadata(db_session: object) -> None:
    machine, _ = await _machine_with_analog_point(db_session)
    bucket_time = datetime.now(UTC).replace(second=0, microsecond=0)
    await copy_readings(db_session, [(bucket_time, _.id, 2.5, None)])  # type: ignore[arg-type]
    await db_session.commit()  # type: ignore[attr-defined]

    trend = await build_trend(
        db_session,  # type: ignore[arg-type]
        machine.id,
        "vibration",
        start=bucket_time - timedelta(hours=1),
        end=bucket_time + timedelta(minutes=1),
    )

    assert trend is not None
    assert trend.data_point_name == "vibration"
    assert trend.unit == "mm/s"
    assert trend.measurement_type == "speed"
    assert trend.normal_min == 0.0
    assert trend.normal_max == 5.0


async def test_trend_unknown_data_point_returns_none(db_session: object) -> None:
    machine, _ = await _machine_with_analog_point(db_session)
    now = datetime.now(UTC)

    trend = await build_trend(
        db_session,  # type: ignore[arg-type]
        machine.id,
        "does_not_exist",
        start=now - timedelta(hours=1),
        end=now + timedelta(minutes=1),
    )

    assert trend is None


async def test_build_trend_by_id_loads_points_and_metadata(db_session: object) -> None:
    machine, data_point = await _machine_with_analog_point(db_session)
    bucket_time = datetime.now(UTC).replace(second=0, microsecond=0)
    await copy_readings(db_session, [(bucket_time, data_point.id, 3.0, None)])  # type: ignore[arg-type]
    await db_session.commit()  # type: ignore[attr-defined]

    trend = await build_trend_by_id(
        db_session,  # type: ignore[arg-type]
        data_point.id,
        start=bucket_time - timedelta(hours=1),
        end=bucket_time + timedelta(minutes=1),
    )

    assert trend is not None
    assert trend.machine_id == machine.id
    assert trend.data_point_name == "vibration"
    assert trend.points[-1].avg == 3.0


async def test_build_trend_by_id_unknown_returns_none(db_session: object) -> None:
    trend = await build_trend_by_id(
        db_session,  # type: ignore[arg-type]
        999999,
        start=datetime.now(UTC) - timedelta(hours=1),
        end=datetime.now(UTC) + timedelta(minutes=1),
    )
    assert trend is None
