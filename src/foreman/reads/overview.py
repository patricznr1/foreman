# ============================================================
#  FOREMAN — reads/overview.py
#  Zweck: Flotten-Overview des Read-Cores (F5) — die Status-Aggregation über
#         Maschinen/Linien für die globale Statusleiste und das Cockpit. Pro
#         Maschine: komponierter FCSM-Status (reads.status) + offene Alarme nach
#         Severity + jüngster offener Alarm; dazu ein Flotten-Rollup. Optional
#         auf einen Scope (machine_ids) begrenzbar — Grundlage der Abo-/Sicht-
#         Autorisierung (F5, Rollenmatrix 3.1).
#  Architektur-Einordnung: Read-Core (Schicht 2). Transport-neutral, gibt reine
#         dataclasses zurück; HTTP- und WS-Transport mappen sie auf ihren Vertrag.
#  Invariante: ausschließlich SELECT — keine Aktorik, kein Write.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import Alarm, Machine
from foreman.reads.queries import open_alarms_for_machines
from foreman.reads.status import MachineStatus, compose_status


@dataclass(frozen=True)
class MachineOverview:
    """Aggregierter Zustand einer Maschine für Statusleiste/Cockpit (F5)."""

    id: int
    label: str
    line_id: int | None
    machine_class: str | None
    status: MachineStatus
    open_alarm_count: int
    open_by_severity: dict[str, int]
    last_alarm_at: datetime | None


@dataclass(frozen=True)
class FleetOverview:
    """Flotten-Lagebild: je Maschine ein Eintrag plus Status-Rollup."""

    machines: tuple[MachineOverview, ...]
    by_status: dict[MachineStatus, int]
    open_alarm_total: int


async def _load_machines(
    session: AsyncSession, machine_ids: Sequence[int] | None
) -> Sequence[Machine]:
    """Lädt die (optional auf einen Scope begrenzten) Maschinen in stabiler Ordnung."""
    stmt = select(Machine).order_by(Machine.id)
    if machine_ids is not None:
        stmt = stmt.where(Machine.id.in_(machine_ids))
    return (await session.scalars(stmt)).all()


def _machine_overview(machine: Machine, open_alarm_list: Sequence[Alarm]) -> MachineOverview:
    """Baut den Maschinen-Overview aus Stammdaten + ihren offenen Alarmen (rein)."""
    status, count = compose_status(open_alarm_list)
    by_severity = Counter(alarm.severity for alarm in open_alarm_list)
    last_alarm_at = max((alarm.raised_at for alarm in open_alarm_list), default=None)
    return MachineOverview(
        id=machine.id,
        label=machine.label,
        line_id=machine.line_id,
        machine_class=machine.machine_class,
        status=status,
        open_alarm_count=count,
        open_by_severity=dict(by_severity),
        last_alarm_at=last_alarm_at,
    )


async def build_fleet_overview(
    session: AsyncSession, *, machine_ids: Sequence[int] | None = None
) -> FleetOverview:
    """Baut das Flotten-Lagebild über alle (oder die scope-begrenzten) Maschinen.

    EINE Alarm-Abfrage für alle Maschinen (kein N+1, reads.open_alarms_for_machines),
    Status pro Maschine über die kanonische Komposition (reads.status). `machine_ids`
    begrenzt den Scope — die Autorisierungs-Schicht (F5) reicht hier die für die
    Rolle sichtbaren Maschinen durch.
    """
    machines = await _load_machines(session, machine_ids)
    open_map = await open_alarms_for_machines(session, [machine.id for machine in machines])
    entries = tuple(
        _machine_overview(machine, open_map.get(machine.id, [])) for machine in machines
    )
    by_status: Counter[MachineStatus] = Counter(entry.status for entry in entries)
    open_alarm_total = sum(entry.open_alarm_count for entry in entries)
    return FleetOverview(
        machines=entries,
        by_status=dict(by_status),
        open_alarm_total=open_alarm_total,
    )
