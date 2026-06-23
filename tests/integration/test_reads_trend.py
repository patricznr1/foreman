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

from foreman.db.models import DataPoint, DriftProfile, Machine
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


# --------------------------------------------------------------------------- #
#  F4-Eigenprofil-Overlay: Band-Expansion = echte Detektor-Basis je Zustand
# --------------------------------------------------------------------------- #
async def _free_cagg(raw_conn: object) -> None:
    """Befreit readings_1m von Vortest-Materialisierung (Test-Isolation der CAgg)."""
    await raw_conn.execute(  # type: ignore[attr-defined]
        "CALL refresh_continuous_aggregate('readings_1m', "
        "'2000-01-01 00:00:00+00', '2100-01-01 00:00:00+00')"
    )


async def test_trend_traegt_eigenprofil_korridor_je_zustand(
    db_session: object, raw_conn: object
) -> None:
    # Band-Expansion wählt je Bucket den Korridor des KORREKTEN Zustands (state_key =
    # Tagesstunde): Stunde 8 -> Median 10, Stunde 20 -> Median 30; sigma 1.0, k 3.0.
    machine, data_point = await _machine_with_analog_point(db_session)
    db_session.add(  # type: ignore[attr-defined]
        DriftProfile(
            data_point_id=data_point.id,
            machine_id=machine.id,
            state_medians={
                "8": {"median": 10.0, "sample_count": 50},
                "20": {"median": 30.0, "sample_count": 50},
            },
            noise_sigma=1.0,
            effect_size_k=3.0,
            window_samples=1440,
            warmup_samples=100,
            total_samples=200,
            computed_at=datetime(2026, 6, 20, 22, 0, tzinfo=UTC),
        )
    )
    await db_session.flush()  # type: ignore[attr-defined]
    await _free_cagg(raw_conn)
    t8 = datetime(2026, 6, 20, 8, 30, tzinfo=UTC)
    t20 = datetime(2026, 6, 20, 20, 30, tzinfo=UTC)
    await copy_readings(  # type: ignore[arg-type]
        db_session, [(t8, data_point.id, 10.5, None), (t20, data_point.id, 31.0, None)]
    )
    await db_session.commit()  # type: ignore[attr-defined]

    trend = await build_trend(
        db_session,  # type: ignore[arg-type]
        machine.id,
        "vibration",
        start=datetime(2026, 6, 20, 0, 0, tzinfo=UTC),
        end=datetime(2026, 6, 21, 0, 0, tzinfo=UTC),
    )

    assert trend is not None
    band = trend.profile_band
    assert band is not None
    assert band.effect_size_k == 3.0
    assert band.computed_at == datetime(2026, 6, 20, 22, 0, tzinfo=UTC)
    by_hour = {point.bucket.hour: point for point in band.points}
    # Stunde 8 -> Korridor 10 +/- 3*1; Stunde 20 -> 30 +/- 3*1 — KEIN vertauschter Zustand.
    assert (by_hour[8].lower, by_hour[8].mid, by_hour[8].upper) == (7.0, 10.0, 13.0)
    assert (by_hour[20].lower, by_hour[20].mid, by_hour[20].upper) == (27.0, 30.0, 33.0)


async def test_trend_ohne_profil_laesst_profile_band_null(db_session: object) -> None:
    machine, data_point = await _machine_with_analog_point(db_session)
    bucket_time = datetime.now(UTC).replace(second=0, microsecond=0)
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
    assert trend.profile_band is None  # graceful: kein Profil -> kein Band


async def test_trend_profil_ohne_passenden_zustand_laesst_band_null(
    db_session: object, raw_conn: object
) -> None:
    # Profil kennt nur Stunde 8; alle Buckets liegen in Stunde 3 -> kein Korridor -> null.
    machine, data_point = await _machine_with_analog_point(db_session)
    db_session.add(  # type: ignore[attr-defined]
        DriftProfile(
            data_point_id=data_point.id,
            machine_id=machine.id,
            state_medians={"8": {"median": 10.0, "sample_count": 50}},
            noise_sigma=1.0,
            effect_size_k=3.0,
            window_samples=1440,
            warmup_samples=100,
            total_samples=120,
            computed_at=datetime(2026, 6, 20, 9, 0, tzinfo=UTC),
        )
    )
    await db_session.flush()  # type: ignore[attr-defined]
    await _free_cagg(raw_conn)
    t3 = datetime(2026, 6, 20, 3, 15, tzinfo=UTC)
    await copy_readings(db_session, [(t3, data_point.id, 9.0, None)])  # type: ignore[arg-type]
    await db_session.commit()  # type: ignore[attr-defined]

    trend = await build_trend(
        db_session,  # type: ignore[arg-type]
        machine.id,
        "vibration",
        start=datetime(2026, 6, 20, 0, 0, tzinfo=UTC),
        end=datetime(2026, 6, 20, 6, 0, tzinfo=UTC),
    )

    assert trend is not None
    assert trend.profile_band is None  # Profil da, aber kein Bucket im passenden Zustand
