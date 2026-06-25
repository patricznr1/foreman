# ============================================================
#  FOREMAN — tests/integration/test_realtime_authz.py
#  Zweck: Abo-Autorisierung (F5, Vorgabe 2) — default-deny + Rollenmatrix 3.1 +
#         Per-User-Scope. manager/technician unrestricted, shift_lead an seine
#         Linien gebunden, worker an seine Maschinen; overview nur manager/
#         shift_lead; unbekannte Rolle/Topic → deny. Das ist der PII-Strich:
#         ein authentifizierter Client darf NICHT jedes Maschinen-Thema mithören.
# ============================================================
from __future__ import annotations

import pytest

from foreman.db.models import DataPoint, Line, Machine, User
from foreman.realtime.authz import can_subscribe, visible_machine_scope
from foreman.realtime.topics import OVERVIEW_TOPIC, machine_topic, trend_topic
from foreman.realtime.ws import _authorized_payload

pytestmark = pytest.mark.integration


async def _line(session: object, label: str = "L") -> Line:
    line = Line(label=label)
    session.add(line)  # type: ignore[attr-defined]
    await session.flush()  # type: ignore[attr-defined]
    return line


async def _machine(session: object, *, line: Line | None = None, label: str = "M") -> Machine:
    machine = Machine(label=label, line_id=line.id if line else None)
    session.add(machine)  # type: ignore[attr-defined]
    await session.flush()  # type: ignore[attr-defined]
    return machine


async def _data_point(session: object, machine: Machine, *, name: str = "vib") -> DataPoint:
    data_point = DataPoint(machine_id=machine.id, name=name, kind="analog")
    session.add(data_point)  # type: ignore[attr-defined]
    await session.flush()  # type: ignore[attr-defined]
    return data_point


async def _user(
    session: object,
    *,
    email: str,
    role: str,
    lines: tuple[int, ...] = (),
    machines: tuple[int, ...] = (),
) -> User:
    user = User(
        email=email,
        password_hash="x",
        role=role,
        assigned_line_ids=list(lines),
        assigned_machine_ids=list(machines),
    )
    session.add(user)  # type: ignore[attr-defined]
    await session.flush()  # type: ignore[attr-defined]
    return user


async def test_manager_sees_overview_machines_and_trends(db_session: object) -> None:
    line = await _line(db_session)
    machine = await _machine(db_session, line=line)
    data_point = await _data_point(db_session, machine)
    user = await _user(db_session, email="mgr@x.de", role="manager")

    assert await can_subscribe(db_session, user, OVERVIEW_TOPIC)  # type: ignore[arg-type]
    assert await can_subscribe(db_session, user, machine_topic(machine.id))  # type: ignore[arg-type]
    assert await can_subscribe(db_session, user, trend_topic(data_point.id))  # type: ignore[arg-type]


async def test_technician_sees_machines_but_not_overview(db_session: object) -> None:
    line = await _line(db_session)
    machine = await _machine(db_session, line=line)
    data_point = await _data_point(db_session, machine)
    user = await _user(db_session, email="tech@x.de", role="technician")

    assert not await can_subscribe(db_session, user, OVERVIEW_TOPIC)  # type: ignore[arg-type]
    assert await can_subscribe(db_session, user, machine_topic(machine.id))  # type: ignore[arg-type]
    assert await can_subscribe(db_session, user, trend_topic(data_point.id))  # type: ignore[arg-type]


async def test_worker_scoped_to_assigned_machines(db_session: object) -> None:
    line = await _line(db_session)
    mine = await _machine(db_session, line=line, label="mine")
    foreign = await _machine(db_session, line=line, label="foreign")
    my_dp = await _data_point(db_session, mine)
    user = await _user(db_session, email="wrk@x.de", role="worker", machines=(mine.id,))

    assert await can_subscribe(db_session, user, machine_topic(mine.id))  # type: ignore[arg-type]
    assert not await can_subscribe(db_session, user, machine_topic(foreign.id))  # type: ignore[arg-type]
    assert await can_subscribe(db_session, user, trend_topic(my_dp.id))  # type: ignore[arg-type]
    assert not await can_subscribe(db_session, user, OVERVIEW_TOPIC)  # type: ignore[arg-type]


async def test_shift_lead_scoped_to_assigned_lines(db_session: object) -> None:
    my_line = await _line(db_session, label="L1")
    other_line = await _line(db_session, label="L2")
    mine = await _machine(db_session, line=my_line, label="mine")
    foreign = await _machine(db_session, line=other_line, label="foreign")
    my_dp = await _data_point(db_session, mine)
    user = await _user(db_session, email="sl@x.de", role="shift_lead", lines=(my_line.id,))

    assert await can_subscribe(db_session, user, OVERVIEW_TOPIC)  # type: ignore[arg-type]
    assert await can_subscribe(db_session, user, machine_topic(mine.id))  # type: ignore[arg-type]
    assert not await can_subscribe(db_session, user, machine_topic(foreign.id))  # type: ignore[arg-type]
    assert await can_subscribe(db_session, user, trend_topic(my_dp.id))  # type: ignore[arg-type]


async def test_unknown_role_is_default_deny(db_session: object) -> None:
    line = await _line(db_session)
    machine = await _machine(db_session, line=line)
    user = await _user(db_session, email="ghost@x.de", role="ghost")

    assert not await can_subscribe(db_session, user, OVERVIEW_TOPIC)  # type: ignore[arg-type]
    assert not await can_subscribe(db_session, user, machine_topic(machine.id))  # type: ignore[arg-type]


async def test_unknown_topic_is_default_deny(db_session: object) -> None:
    user = await _user(db_session, email="mgr2@x.de", role="manager")
    assert not await can_subscribe(db_session, user, "garbage")  # type: ignore[arg-type]


async def test_trend_for_unknown_data_point_is_denied(db_session: object) -> None:
    user = await _user(db_session, email="mgr3@x.de", role="manager")
    assert not await can_subscribe(db_session, user, trend_topic(999999))  # type: ignore[arg-type]


async def test_push_reauthorization_reflects_revoked_scope(db_session: object) -> None:
    """Review-Fix: der WS-Push lädt den Nutzer pro Push FRISCH und re-autorisiert —
    ein mid-session entzogener Scope verweigert beim nächsten Re-Check (kein
    eingefrorener Stand, der bis Reconnect PII weiterstreamt)."""
    line = await _line(db_session)
    machine = await _machine(db_session, line=line)
    user = await _user(db_session, email="reauth-wrk@x.de", role="worker", machines=(machine.id,))

    allowed, _payload = await _authorized_payload(
        db_session,  # type: ignore[arg-type]
        user.id,
        machine_topic(machine.id),
    )
    assert allowed is True

    # Scope mid-session entzogen (DB-Zustand ändert sich).
    user.assigned_machine_ids = []
    await db_session.flush()  # type: ignore[attr-defined]

    allowed_after, _payload_after = await _authorized_payload(
        db_session,  # type: ignore[arg-type]
        user.id,
        machine_topic(machine.id),
    )
    assert allowed_after is False


# --------------------------------------------------------------------------- #
#  visible_machine_scope — rollenweiter Scope für das Karten-Grid (GET /cards)
# --------------------------------------------------------------------------- #
async def test_visible_scope_manager_and_technician_unrestricted(db_session: object) -> None:
    manager = await _user(db_session, email="vs-mgr@x.de", role="manager")
    technician = await _user(db_session, email="vs-tech@x.de", role="technician")
    assert await visible_machine_scope(db_session, manager) is None  # type: ignore[arg-type]
    assert await visible_machine_scope(db_session, technician) is None  # type: ignore[arg-type]


async def test_visible_scope_worker_sees_only_assigned_machines(db_session: object) -> None:
    mine = await _machine(db_session, label="mine")
    await _machine(db_session, label="foreign")
    worker = await _user(db_session, email="vs-wrk@x.de", role="worker", machines=(mine.id,))
    assert await visible_machine_scope(db_session, worker) == [mine.id]  # type: ignore[arg-type]


async def test_visible_scope_shift_lead_sees_only_his_line_machines(db_session: object) -> None:
    my_line = await _line(db_session, label="mine")
    other_line = await _line(db_session, label="other")
    a = await _machine(db_session, line=my_line, label="a")
    b = await _machine(db_session, line=my_line, label="b")
    await _machine(db_session, line=other_line, label="foreign")
    shift_lead = await _user(db_session, email="vs-sl@x.de", role="shift_lead", lines=(my_line.id,))

    scope = await visible_machine_scope(db_session, shift_lead)  # type: ignore[arg-type]

    assert scope is not None
    assert set(scope) == {a.id, b.id}


async def test_visible_scope_shift_lead_without_lines_is_empty(db_session: object) -> None:
    await _machine(db_session, line=await _line(db_session))
    shift_lead = await _user(db_session, email="vs-sl0@x.de", role="shift_lead")
    assert await visible_machine_scope(db_session, shift_lead) == []  # type: ignore[arg-type]


async def test_visible_scope_unknown_role_is_empty(db_session: object) -> None:
    ghost = await _user(db_session, email="vs-ghost@x.de", role="ghost")
    assert await visible_machine_scope(db_session, ghost) == []  # type: ignore[arg-type]
