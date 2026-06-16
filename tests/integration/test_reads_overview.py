# ============================================================
#  FOREMAN — tests/integration/test_reads_overview.py
#  Zweck: Read-Core Flotten-Overview (F5) — die Status-Aggregation über
#         Maschinen/Linien für globale Statusleiste + Cockpit. Komponierter
#         FCSM-Status + offene Alarme nach Severity + Rollup, scope-filterbar.
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from foreman.db.models import Alarm, Line, Machine
from foreman.reads.overview import build_fleet_overview
from foreman.reasoners.drift.service import DRIFT_ALARM_CODE

pytestmark = pytest.mark.integration

_NOW = datetime(2026, 6, 16, 12, 0, tzinfo=UTC)


async def _line(session: object, label: str = "Linie 1") -> Line:
    line = Line(label=label)
    session.add(line)  # type: ignore[attr-defined]
    await session.flush()  # type: ignore[attr-defined]
    return line


async def _machine(
    session: object, *, line: Line | None = None, label: str = "M1", machine_class: str = "cnc"
) -> Machine:
    machine = Machine(label=label, machine_class=machine_class, line_id=line.id if line else None)
    session.add(machine)  # type: ignore[attr-defined]
    await session.flush()  # type: ignore[attr-defined]
    return machine


async def _alarm(
    session: object,
    machine: Machine,
    *,
    severity: str = "critical",
    category: str = "hardware",
    code: str | None = None,
    raised_at: datetime = _NOW,
    cleared: bool = False,
    acknowledged: bool = False,
) -> Alarm:
    alarm = Alarm(
        machine_id=machine.id,
        severity=severity,
        category=category,
        code=code,
        raised_at=raised_at,
        cleared_at=_NOW if cleared else None,
        acknowledged_at=_NOW if acknowledged else None,
    )
    session.add(alarm)  # type: ignore[attr-defined]
    await session.flush()  # type: ignore[attr-defined]
    return alarm


async def test_empty_fleet_yields_empty_overview(db_session: object) -> None:
    overview = await build_fleet_overview(db_session)  # type: ignore[arg-type]
    assert overview.machines == ()
    assert overview.open_alarm_total == 0
    assert overview.by_status == {}


async def test_machine_without_open_alarms_is_healthy(db_session: object) -> None:
    machine = await _machine(db_session)
    # Ein zurückgesetzter Alarm zählt NICHT als offen.
    await _alarm(db_session, machine, cleared=True)

    overview = await build_fleet_overview(db_session)  # type: ignore[arg-type]

    assert len(overview.machines) == 1
    entry = overview.machines[0]
    assert entry.id == machine.id
    assert entry.status == "healthy"
    assert entry.open_alarm_count == 0
    assert entry.open_by_severity == {}


async def test_open_non_drift_alarm_is_open_warning_with_severity_breakdown(
    db_session: object,
) -> None:
    machine = await _machine(db_session)
    await _alarm(db_session, machine, severity="critical", category="hardware")
    await _alarm(db_session, machine, severity="warning", category="process")

    overview = await build_fleet_overview(db_session)  # type: ignore[arg-type]

    entry = overview.machines[0]
    assert entry.status == "open_warning"
    assert entry.open_alarm_count == 2
    assert entry.open_by_severity == {"critical": 1, "warning": 1}


async def test_open_unacknowledged_drift_alarm_is_drift_active(db_session: object) -> None:
    machine = await _machine(db_session)
    await _alarm(db_session, machine, code=DRIFT_ALARM_CODE, severity="warning", category="process")

    overview = await build_fleet_overview(db_session)  # type: ignore[arg-type]

    assert overview.machines[0].status == "drift_active"


async def test_acknowledged_drift_falls_back_to_open_warning(db_session: object) -> None:
    machine = await _machine(db_session)
    await _alarm(
        db_session,
        machine,
        code=DRIFT_ALARM_CODE,
        severity="warning",
        category="process",
        acknowledged=True,
    )

    overview = await build_fleet_overview(db_session)  # type: ignore[arg-type]

    # Quittierte Drift ist kein drift_active mehr, aber der Alarm bleibt offen.
    assert overview.machines[0].status == "open_warning"


async def test_fleet_rollup_counts_by_status_and_total(db_session: object) -> None:
    line = await _line(db_session)
    healthy = await _machine(db_session, line=line, label="healthy")
    warned = await _machine(db_session, line=line, label="warned")
    drifting = await _machine(db_session, line=line, label="drifting")
    await _alarm(db_session, warned, severity="alarm", category="hardware")
    await _alarm(
        db_session, drifting, code=DRIFT_ALARM_CODE, severity="warning", category="process"
    )

    overview = await build_fleet_overview(db_session)  # type: ignore[arg-type]

    assert overview.by_status == {"healthy": 1, "open_warning": 1, "drift_active": 1}
    assert overview.open_alarm_total == 2
    assert {m.id for m in overview.machines} == {healthy.id, warned.id, drifting.id}


async def test_last_alarm_at_is_most_recent_open_alarm(db_session: object) -> None:
    machine = await _machine(db_session)
    await _alarm(db_session, machine, raised_at=_NOW - timedelta(hours=2))
    await _alarm(db_session, machine, raised_at=_NOW)

    overview = await build_fleet_overview(db_session)  # type: ignore[arg-type]

    assert overview.machines[0].last_alarm_at == _NOW


async def test_scope_filter_limits_to_given_machines(db_session: object) -> None:
    visible = await _machine(db_session, label="visible")
    hidden = await _machine(db_session, label="hidden")
    await _alarm(db_session, hidden, severity="critical", category="hardware")

    overview = await build_fleet_overview(db_session, machine_ids=[visible.id])  # type: ignore[arg-type]

    assert {m.id for m in overview.machines} == {visible.id}
    assert overview.open_alarm_total == 0
