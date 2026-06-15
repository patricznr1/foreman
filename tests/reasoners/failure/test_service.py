# ============================================================
#  FOREMAN — tests/reasoners/failure/test_service.py
#  Zweck: Pflicht-Test-Block der F-PRED-Pipeline E2E gegen die ECHTE TimescaleDB.
#  KERN-AKZEPTANZ (§16): Eine persistierte FailurePrediction trägt IMMER
#         validation_status=simulation_only — strukturell erzwungen, nicht umgehbar.
#  Prüft außerdem: Persistenz, Wahrscheinlichkeit im [0,1], Entscheidung↔Schwellwert,
#         SHAP-Top-Faktoren, 404 bei fehlender Maschine, Default-Bezugszeitpunkt.
#  Architektur-Einordnung: Quality Gate §10.3 (Integration, echte DB).
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import DataPoint, FailurePredictionRecord, Machine
from foreman.ingestion.service import copy_readings
from foreman.reasoners.failure.model import FailureModel
from foreman.reasoners.failure.service import FailureService, MachineNotFoundError

pytestmark = pytest.mark.integration

# Datenpunkt-Namen entsprechen dem bearing_drift-Szenario (Feature-Schema-Treffer).
_DATA_POINTS = [
    ("machine_running", "digital", "signal", 1.0),
    ("vibration_rms_velocity_spindle_bearing", "analog", "signal", 3.4),
    ("bearing_temperature_spindle", "analog", "temperature", 58.0),
    ("spindle_motor_current", "analog", "current", 13.0),
]
_REF = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)


async def _seed(session: AsyncSession, raw_conn: asyncpg.Connection) -> int:
    """Seedet eine CNC-Maschine + Datenpunkte + 120 readings (10h) und refresht das CAgg."""
    machine = Machine(label="BAZ-01", machine_class="cnc_machining_center")
    session.add(machine)
    await session.flush()

    points: list[DataPoint] = []
    for name, kind, mt, _base in _DATA_POINTS:
        dp = DataPoint(
            machine_id=machine.id, name=name, kind=kind, measurement_type=mt, source="simulation"
        )
        session.add(dp)
        points.append(dp)
    await session.flush()

    rows: list[tuple[datetime, int, float, int | None]] = []
    for dp, (_name, _kind, _mt, base) in zip(points, _DATA_POINTS, strict=True):
        for i in range(120):
            bucket = _REF - timedelta(minutes=5 * (120 - i))
            # leicht steigende Vibration (Degradations-Andeutung), Rest stationär.
            value = base + (0.01 * i if dp.name.startswith("vibration") else 0.0)
            rows.append((bucket, dp.id, value, None))
    await copy_readings(session, rows)
    await session.commit()

    # readings_1m breit refreshen (Test-Isolation), über eine eigene Verbindung.
    await raw_conn.execute(
        "CALL refresh_continuous_aggregate('readings_1m', "
        "'2000-01-01 00:00:00+00', '2100-01-01 00:00:00+00')"
    )
    return machine.id


async def test_prediction_traegt_immer_validation_status(
    db_session: AsyncSession, raw_conn: asyncpg.Connection, failure_model: FailureModel
) -> None:
    machine_id = await _seed(db_session, raw_conn)
    service = FailureService(session=db_session, model=failure_model)
    record = await service.predict(machine_id, reference_time=_REF)

    # KERN-AKZEPTANZ: der Sim-Vorbehalt ist nicht abstreifbar.
    assert record.validation_status == "simulation_only"
    assert record.data_regime == "simulation"
    assert record.model_version == failure_model.metadata.model_version
    assert record.id is not None


async def test_prediction_wird_persistiert_und_ist_konsistent(
    db_session: AsyncSession, raw_conn: asyncpg.Connection, failure_model: FailureModel
) -> None:
    machine_id = await _seed(db_session, raw_conn)
    service = FailureService(session=db_session, model=failure_model)
    record = await service.predict(machine_id, reference_time=_REF)

    assert 0.0 <= record.probability <= 1.0
    assert record.horizon_h == failure_model.horizon_h
    expected = "elevated_risk" if record.probability >= record.decision_threshold else "normal"
    assert record.decision == expected
    assert record.reference_time == _REF
    # SHAP-Top-Faktoren als JSONB-Liste mit erwarteten Schlüsseln.
    assert isinstance(record.top_factors, list)
    if record.top_factors:
        first = record.top_factors[0]
        assert set(first) == {"feature", "value", "shap", "direction"}

    # tatsächlich in der DB?
    stored = (
        await db_session.scalars(
            select(FailurePredictionRecord).where(FailurePredictionRecord.machine_id == machine_id)
        )
    ).all()
    assert len(stored) == 1


async def test_db_check_erzwingt_sim_vorbehalt(
    db_session: AsyncSession, raw_conn: asyncpg.Connection, failure_model: FailureModel
) -> None:
    # Defense-in-Depth (§16.1): der Sim-Vorbehalt ist auch an der PERSISTENZGRENZE
    # erzwungen — ein pydantic-umgehender Direkt-Insert mit Fremdwert wird vom
    # DB-CHECK abgewiesen (nicht erst beim API-Lesen).
    machine_id = await _seed(db_session, raw_conn)
    with pytest.raises(asyncpg.exceptions.CheckViolationError):
        await raw_conn.execute(
            "INSERT INTO failure_predictions "
            "(machine_id, reference_time, horizon_h, probability, decision_threshold, "
            "decision, validation_status, data_regime, model_version, top_factors) "
            "VALUES ($1, now(), 336, 0.5, 0.5, 'normal', 'production', 'simulation', 'v', '[]'::jsonb)",
            machine_id,
        )


async def test_predict_unbekannte_maschine_wirft(
    db_session: AsyncSession, failure_model: FailureModel
) -> None:
    service = FailureService(session=db_session, model=failure_model)
    with pytest.raises(MachineNotFoundError):
        await service.predict(999_999, reference_time=_REF)


async def test_predict_ohne_bezugszeitpunkt_nutzt_jetzt(
    db_session: AsyncSession, raw_conn: asyncpg.Connection, failure_model: FailureModel
) -> None:
    # Ohne reference_time → jetzt (UTC); ausserhalb des Datenbereichs → leere Features,
    # aber die Pipeline läuft durch und trägt den Vorbehalt (keine Exception).
    machine_id = await _seed(db_session, raw_conn)
    service = FailureService(session=db_session, model=failure_model)
    record = await service.predict(machine_id)
    assert record.validation_status == "simulation_only"
    assert 0.0 <= record.probability <= 1.0
