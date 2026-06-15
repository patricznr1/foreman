# ============================================================
#  FOREMAN — tests/reasoners/failure/test_router.py
#  Zweck: Pflicht-Test-Block der F-PRED-Routen (on-demand POST + GET).
#  Prüft: 201 mit Sim-Vorbehalt in der Antwort, Auth-Pflicht (401), 404 bei
#         fehlender Maschine, Liste/Einzelabruf, KEIN Auto-Predict.
#  Architektur-Einordnung: Quality Gate §10.3 (HTTP, echte DB).
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import asyncpg
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from foreman.config import Settings
from foreman.db.models import DataPoint, Machine
from foreman.ingestion.service import copy_readings

pytestmark = pytest.mark.integration

_PREDICT = "/api/v1/reasoners/failure/predict"
_PREDICTIONS = "/api/v1/reasoners/failure/predictions"
_REF = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)
_DATA_POINTS = [
    ("machine_running", "digital", "signal", 1.0),
    ("vibration_rms_velocity_spindle_bearing", "analog", "signal", 3.4),
    ("bearing_temperature_spindle", "analog", "temperature", 58.0),
    ("spindle_motor_current", "analog", "current", 13.0),
]


async def _seed(test_settings: Settings, raw_conn: asyncpg.Connection) -> int:
    """Seedet eine Maschine + Datenpunkte + readings (committet) und refresht das CAgg."""
    engine = create_async_engine(test_settings.database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with maker() as session:
        machine = Machine(label="BAZ-01", machine_class="cnc_machining_center")
        session.add(machine)
        await session.flush()
        points: list[DataPoint] = []
        for name, kind, mt, _base in _DATA_POINTS:
            dp = DataPoint(
                machine_id=machine.id,
                name=name,
                kind=kind,
                measurement_type=mt,
                source="simulation",
            )
            session.add(dp)
            points.append(dp)
        await session.flush()
        rows: list[tuple[datetime, int, float, int | None]] = []
        for dp, (_n, _k, _m, base) in zip(points, _DATA_POINTS, strict=True):
            for i in range(120):
                bucket = _REF - timedelta(minutes=5 * (120 - i))
                value = base + (0.01 * i if dp.name.startswith("vibration") else 0.0)
                rows.append((bucket, dp.id, value, None))
        await copy_readings(session, rows)
        machine_id = machine.id
        await session.commit()
    await engine.dispose()
    await raw_conn.execute(
        "CALL refresh_continuous_aggregate('readings_1m', "
        "'2000-01-01 00:00:00+00', '2100-01-01 00:00:00+00')"
    )
    return machine_id


async def test_predict_route_liefert_201_mit_vorbehalt(
    auth_client: AsyncClient, test_settings: Settings, raw_conn: asyncpg.Connection
) -> None:
    machine_id = await _seed(test_settings, raw_conn)
    resp = await auth_client.post(
        _PREDICT, json={"machine_id": machine_id, "reference_time": _REF.isoformat()}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["validation_status"] == "simulation_only"
    assert body["data_regime"] == "simulation"
    assert 0.0 <= body["probability"] <= 1.0
    assert body["decision"] in ("elevated_risk", "normal")
    assert isinstance(body["top_factors"], list)


async def test_predict_route_braucht_auth(
    client: AsyncClient, test_settings: Settings, raw_conn: asyncpg.Connection
) -> None:
    machine_id = await _seed(test_settings, raw_conn)
    resp = await client.post(_PREDICT, json={"machine_id": machine_id})
    assert resp.status_code == 401


async def test_predict_route_unbekannte_maschine_404(auth_client: AsyncClient) -> None:
    resp = await auth_client.post(
        _PREDICT, json={"machine_id": 999_999, "reference_time": _REF.isoformat()}
    )
    assert resp.status_code == 404


async def test_kein_auto_predict(
    auth_client: AsyncClient, test_settings: Settings, raw_conn: asyncpg.Connection
) -> None:
    # Eine geseedete Maschine erzeugt KEINE Vorhersage von selbst — erst der POST.
    machine_id = await _seed(test_settings, raw_conn)
    before = await auth_client.get(_PREDICTIONS, params={"machine_id": machine_id})
    assert before.status_code == 200
    assert before.json() == []

    created = await auth_client.post(
        _PREDICT, json={"machine_id": machine_id, "reference_time": _REF.isoformat()}
    )
    assert created.status_code == 201

    after = await auth_client.get(_PREDICTIONS, params={"machine_id": machine_id})
    assert len(after.json()) == 1


async def test_get_einzelne_vorhersage_und_404(
    auth_client: AsyncClient, test_settings: Settings, raw_conn: asyncpg.Connection
) -> None:
    machine_id = await _seed(test_settings, raw_conn)
    created = await auth_client.post(
        _PREDICT, json={"machine_id": machine_id, "reference_time": _REF.isoformat()}
    )
    prediction_id = created.json()["id"]

    found = await auth_client.get(f"{_PREDICTIONS}/{prediction_id}")
    assert found.status_code == 200
    assert found.json()["id"] == prediction_id

    missing = await auth_client.get(f"{_PREDICTIONS}/999999")
    assert missing.status_code == 404
