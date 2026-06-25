# ============================================================
#  FOREMAN — tests/integration/test_reads_card.py
#  Zweck: Read-Core Maschinenkarte (F5 — kanonische lebende Maschinenkarte). Der
#         Builder assembliert pro Maschine Steckbrief + Komponenten + Datenpunkte
#         MIT aktuellem Wert (last_value/last_value_at) und ehrlichem Status, plus
#         den Maschinen-Status (FCSM-mappbar) und den Eingangs-Stream-Status. EINE
#         Quelle für Grid-Erstbild, Detail-Erstbild und WS-Snapshot machine:{id}.
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime

import pytest

from foreman.db.models import Alarm, Component, DataPoint, DriftProfile, Machine
from foreman.ingestion.service import copy_readings
from foreman.reads.card import build_fleet_cards, build_machine_card
from foreman.reasoners.drift.service import DRIFT_ALARM_CODE

pytestmark = pytest.mark.integration


async def _machine(session: object, **kwargs: object) -> Machine:
    machine = Machine(label="PR-02", machine_class="servo_press", **kwargs)  # type: ignore[arg-type]
    session.add(machine)  # type: ignore[attr-defined]
    await session.flush()  # type: ignore[attr-defined]
    return machine


async def _data_point(session: object, machine: Machine, **kwargs: object) -> DataPoint:
    defaults: dict[str, object] = {"name": "press_force", "kind": "analog", "unit": "kN"}
    defaults.update(kwargs)
    dp = DataPoint(machine_id=machine.id, **defaults)  # type: ignore[arg-type]
    session.add(dp)  # type: ignore[attr-defined]
    await session.flush()  # type: ignore[attr-defined]
    return dp


async def _reading(session: object, dp: DataPoint, *, value: float, at: datetime) -> None:
    await copy_readings(session, [(at, dp.id, value, None)])  # type: ignore[arg-type]
    await session.commit()  # type: ignore[attr-defined]


async def _drift_profile(
    session: object,
    dp: DataPoint,
    *,
    hour: int,
    median: float,
    noise_sigma: float = 1.0,
    effect_size_k: float = 3.0,
) -> None:
    profile = DriftProfile(
        data_point_id=dp.id,
        machine_id=dp.machine_id,
        state_medians={str(hour): {"median": median, "sample_count": 50}},
        noise_sigma=noise_sigma,
        effect_size_k=effect_size_k,
        window_samples=1440,
        warmup_samples=100,
        total_samples=500,
        computed_at=datetime.now(UTC),
    )
    session.add(profile)  # type: ignore[attr-defined]
    await session.flush()  # type: ignore[attr-defined]


async def _drift_alarm(session: object, dp: DataPoint) -> None:
    session.add(  # type: ignore[attr-defined]
        Alarm(
            machine_id=dp.machine_id,
            data_point_id=dp.id,
            code=DRIFT_ALARM_CODE,
            severity="warning",
            category="process",
            raised_at=datetime.now(UTC),
        )
    )
    await session.flush()  # type: ignore[attr-defined]


async def test_card_carries_steifbrief_components_and_datapoints(db_session: object) -> None:
    machine = await _machine(
        db_session, manufacturer="Bosch Rexroth", external_id="PR-02", location="Halle West"
    )
    component = Component(machine_id=machine.id, label="Werkzeug", component_type="tool")
    db_session.add(component)  # type: ignore[attr-defined]
    await db_session.flush()  # type: ignore[attr-defined]
    await _data_point(db_session, machine, name="press_force", unit="kN")

    card = await build_machine_card(db_session, machine.id)  # type: ignore[arg-type]

    assert card is not None
    assert card.label == "PR-02"
    assert card.machine_class == "servo_press"
    assert card.manufacturer == "Bosch Rexroth"
    assert card.external_id == "PR-02"
    assert card.location == "Halle West"
    assert [c.label for c in card.components] == ["Werkzeug"]
    assert [dp.name for dp in card.data_points] == ["press_force"]
    assert card.data_points[0].unit == "kN"


async def test_datapoint_carries_latest_value_and_timestamp(db_session: object) -> None:
    machine = await _machine(db_session)
    dp = await _data_point(db_session, machine, name="motor_current", unit="A")
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    await _reading(db_session, dp, value=26.2, at=now)

    card = await build_machine_card(db_session, machine.id)  # type: ignore[arg-type]

    assert card is not None
    point = card.data_points[0]
    assert point.last_value == 26.2
    assert point.last_value_at == now


async def test_datapoint_without_readings_is_unknown(db_session: object) -> None:
    machine = await _machine(db_session)
    # Kein Reading, kein Profil, kein Normalband → ehrlich unbekannt, kein Wert.
    await _data_point(db_session, machine, name="idle", normal_min=None, normal_max=None)

    card = await build_machine_card(db_session, machine.id)  # type: ignore[arg-type]

    assert card is not None
    point = card.data_points[0]
    assert point.last_value is None
    assert point.last_value_at is None
    assert point.status == "unknown"


async def test_datapoint_status_out_of_spec_from_static_band(db_session: object) -> None:
    machine = await _machine(db_session)
    dp = await _data_point(
        db_session, machine, name="hydraulic_pressure", normal_min=80.0, normal_max=180.0
    )
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    await _reading(db_session, dp, value=210.0, at=now)  # > normal_max, kein Profil

    card = await build_machine_card(db_session, machine.id)  # type: ignore[arg-type]

    assert card is not None
    assert card.data_points[0].status == "out_of_spec"


async def test_datapoint_status_out_of_band_from_drift_profile(db_session: object) -> None:
    machine = await _machine(db_session)
    dp = await _data_point(db_session, machine, name="bearing_vibration", unit="mm/s")
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    # Profil für die aktuelle Stunde: Korridor 2.0 +/- 3*0.5 = [0.5, 3.5]; Wert 9.0 → außerhalb.
    await _drift_profile(db_session, dp, hour=now.hour, median=2.0, noise_sigma=0.5)
    await _reading(db_session, dp, value=9.0, at=now)

    card = await build_machine_card(db_session, machine.id)  # type: ignore[arg-type]

    assert card is not None
    # Detektor-Band gewinnt vor dem statischen Band (hier gar keins gesetzt).
    assert card.data_points[0].status == "out_of_band"


async def test_datapoint_status_drift_alarm_and_machine_drift_active(db_session: object) -> None:
    machine = await _machine(db_session)
    dp = await _data_point(db_session, machine, name="press_force")
    await _drift_alarm(db_session, dp)

    card = await build_machine_card(db_session, machine.id)  # type: ignore[arg-type]

    assert card is not None
    assert card.data_points[0].status == "drift_alarm"
    # Der Datenpunkt-Verdikt deckt sich mit dem Maschinen-Status.
    assert card.status == "drift_active"
    assert card.open_alarm_count == 1


async def test_card_carries_stream_status(db_session: object) -> None:
    machine = await _machine(db_session)
    dp = await _data_point(db_session, machine, name="x", source="simulation")
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    await _reading(db_session, dp, value=1.0, at=now)

    card = await build_machine_card(db_session, machine.id, now=now)  # type: ignore[arg-type]

    assert card is not None
    assert card.stream.active is True
    assert card.stream.last_reading_at is not None


async def test_acknowledged_open_alarm_stays_a_warning_not_ok(db_session: object) -> None:
    # Quittieren ≠ Löschen: ein offener (cleared_at NULL), aber quittierter Drift-Alarm
    # ist KEIN drift_alarm-Verdikt mehr (acknowledged), bleibt aber ein offener Alarm →
    # Datenpunkt-Status „alarm", nie „ok" (deckt sich mit compose_status: open_warning,
    # nicht healthy). Verriegelt die bewusste Semantik gegen ein falsches „ok".
    machine = await _machine(db_session)
    dp = await _data_point(db_session, machine, name="press_force")
    db_session.add(  # type: ignore[attr-defined]
        Alarm(
            machine_id=machine.id,
            data_point_id=dp.id,
            code=DRIFT_ALARM_CODE,
            severity="warning",
            category="process",
            raised_at=datetime.now(UTC),
            acknowledged_at=datetime.now(UTC),  # quittiert, aber NICHT gelöscht
        )
    )
    await db_session.flush()  # type: ignore[attr-defined]

    card = await build_machine_card(db_session, machine.id)  # type: ignore[arg-type]

    assert card is not None
    assert card.data_points[0].status == "alarm"
    # Maschinen-Status bleibt konsistent eine offene Warnung (kein drift_active, kein healthy).
    assert card.status == "open_warning"


async def test_build_machine_card_unknown_machine_returns_none(db_session: object) -> None:
    card = await build_machine_card(db_session, 999_999)  # type: ignore[arg-type]
    assert card is None


async def test_build_fleet_cards_scopes_to_given_machines(db_session: object) -> None:
    visible = await _machine(db_session)
    hidden = await _machine(db_session)
    await _data_point(db_session, visible, name="a")
    await _data_point(db_session, hidden, name="b")

    cards = await build_fleet_cards(db_session, machine_ids=[visible.id])  # type: ignore[arg-type]

    assert {c.id for c in cards} == {visible.id}
