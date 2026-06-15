# ============================================================
#  FOREMAN — adapters/simulation/seed.py
#  Zweck: Idempotentes Topologie-Seeding (F3) — legt die im Szenario definierten
#         lines/machines/components/data_points über die F2-ORM-Modelle an,
#         BEVOR der Generator streamt, und löst die natürlichen Schlüssel auf
#         echte DB-IDs auf (TopologyMap).
#  Architektur-Einordnung: Datenakquise (Schicht 2), Simulations-Adapter.
#  Idempotenz: natürliche Schlüssel — line.label, machine.external_id,
#         (machine_id, component.label), (machine_id, data_point.name). Ein
#         zweiter Lauf legt nichts doppelt an (SELECT-then-INSERT, seriell).
#         Kein UNIQUE-Constraint nötig; das Seeding läuft als einzelner Runner.
# ============================================================
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.adapters.simulation.scenario import Scenario
from foreman.db.models import Component, DataPoint, Line, Machine


@dataclass
class TopologyMap:
    """Auflösung der Szenario-Schlüssel auf echte DB-IDs (Ergebnis des Seedings)."""

    line_id: int
    machine_id: int
    component_ids: dict[str, int] = field(default_factory=dict)
    data_point_ids: dict[str, int] = field(default_factory=dict)


async def _get_or_create_line(session: AsyncSession, scenario: Scenario) -> Line:
    spec = scenario.line
    stmt = select(Line).where(Line.label == spec.label).limit(1)
    line = (await session.execute(stmt)).scalar_one_or_none()
    if line is None:
        line = Line(label=spec.label, location=spec.location)
        session.add(line)
        await session.flush()  # weist die PK zu, ohne zu committen
    return line


async def _get_or_create_machine(
    session: AsyncSession, scenario: Scenario, line_id: int
) -> Machine:
    spec = scenario.machine
    stmt = select(Machine).where(Machine.external_id == spec.external_id).limit(1)
    machine = (await session.execute(stmt)).scalar_one_or_none()
    if machine is None:
        machine = Machine(
            line_id=line_id,
            external_id=spec.external_id,
            label=spec.label,
            machine_class=spec.machine_class,
            manufacturer=spec.manufacturer,
            location=spec.location,
        )
        session.add(machine)
        await session.flush()
    return machine


async def _get_or_create_component(
    session: AsyncSession, machine_id: int, label: str, component_type: str | None
) -> Component:
    stmt = (
        select(Component)
        .where(Component.machine_id == machine_id, Component.label == label)
        .limit(1)
    )
    component = (await session.execute(stmt)).scalar_one_or_none()
    if component is None:
        component = Component(machine_id=machine_id, label=label, component_type=component_type)
        session.add(component)
        await session.flush()
    return component


async def _get_or_create_data_point(
    session: AsyncSession,
    machine_id: int,
    component_id: int | None,
    spec_name: str,
    spec_kind: str,
    measurement_type: str | None,
    unit: str | None,
    source: str,
    normal_min: float | None,
    normal_max: float | None,
) -> DataPoint:
    stmt = (
        select(DataPoint)
        .where(DataPoint.machine_id == machine_id, DataPoint.name == spec_name)
        .limit(1)
    )
    data_point = (await session.execute(stmt)).scalar_one_or_none()
    if data_point is None:
        data_point = DataPoint(
            machine_id=machine_id,
            component_id=component_id,
            name=spec_name,
            kind=spec_kind,
            measurement_type=measurement_type,
            unit=unit,
            source=source,
            normal_min=normal_min,
            normal_max=normal_max,
        )
        session.add(data_point)
        await session.flush()
    return data_point


async def seed_topology(session: AsyncSession, scenario: Scenario) -> TopologyMap:
    """Legt die Szenario-Topologie idempotent an und liefert die ID-Auflösung."""
    line = await _get_or_create_line(session, scenario)
    machine = await _get_or_create_machine(session, scenario, line.id)

    component_ids: dict[str, int] = {}
    for component_spec in scenario.components:
        component = await _get_or_create_component(
            session, machine.id, component_spec.label, component_spec.component_type
        )
        component_ids[component_spec.key] = component.id

    data_point_ids: dict[str, int] = {}
    for dp in scenario.data_points:
        component_id = component_ids.get(dp.component) if dp.component else None
        data_point = await _get_or_create_data_point(
            session,
            machine.id,
            component_id,
            dp.name,
            dp.kind,
            dp.measurement_type,
            dp.unit,
            dp.source,
            dp.normal_min,
            dp.normal_max,
        )
        data_point_ids[dp.key] = data_point.id

    return TopologyMap(
        line_id=line.id,
        machine_id=machine.id,
        component_ids=component_ids,
        data_point_ids=data_point_ids,
    )
