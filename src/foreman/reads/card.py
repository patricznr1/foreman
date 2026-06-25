# ============================================================
#  FOREMAN — reads/card.py
#  Zweck: Die kanonische lebende Maschinenkarte des Read-Cores (F5). Assembliert
#         pro Maschine den Steckbrief (Klasse/Standort/Kennung/Hersteller) +
#         Komponenten + Datenpunkte MIT aktuellem Wert (last_value/last_value_at,
#         readings_1m) und ehrlichem Status je Datenpunkt (reads.datapoint_status,
#         kein neu erfundener Schwellwert) sowie dem Maschinen-Status (FCSM-mappbar)
#         und dem Eingangs-Stream-Status (für ehrliche Live/Stale-Anzeige).
#  EINE Quelle der Wahrheit: Grid-Erstbild (build_fleet_cards), Detail-Erstbild und
#         WS-Snapshot machine:{id} (build_machine_card) lesen denselben Builder —
#         kein Doppel-Code, kein driftender Zweit-Vertrag.
#  Architektur-Einordnung: Read-Core (Schicht 2). Transport-neutral, gibt reine
#         dataclasses zurück; HTTP/WS mappen sie auf ihren Pydantic-Vertrag.
#  Invariante: ausschließlich SELECT — keine Aktorik, kein Write. Batched
#         (eine Abfrage je Entität über die Flotte) — kein N+1.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import Alarm, Component, DataPoint, DriftProfile, Machine
from foreman.reads.datapoint_status import DataPointStatus, derive_datapoint_status
from foreman.reads.queries import (
    LatestValue,
    latest_values_for_data_points,
    load_drift_profiles_for_data_points,
    open_alarms_for_machines,
)
from foreman.reads.status import MachineStatus, compose_status
from foreman.reads.stream import StreamStatus, build_stream_status
from foreman.reasoners.drift.baseline import corridor_at
from foreman.reasoners.drift.service import DRIFT_ALARM_CODE


@dataclass(frozen=True)
class ComponentCard:
    """Eine Komponente im Steckbrief der Karte."""

    id: int
    label: str
    component_type: str | None


@dataclass(frozen=True)
class DataPointCard:
    """Ein Datenpunkt der Karte: Stammdaten + aktueller Wert + ehrlicher Status.

    `last_value`/`last_value_at` aus dem neuesten readings_1m-Bucket; null, wenn der
    Datenpunkt (noch) keine Readings hat (kein erfundener Wert). `status` stammt aus
    bestehenden Signalen (Alarm-Verdikt / Eigenprofil-Korridor / Normalband), nie aus
    einem neu erfundenen Schwellwert.
    """

    id: int
    component_id: int | None
    name: str
    kind: str
    measurement_type: str | None
    unit: str | None
    normal_min: float | None
    normal_max: float | None
    last_value: float | None
    last_value_at: datetime | None
    status: DataPointStatus


@dataclass(frozen=True)
class MachineCard:
    """Die lebende Maschinenkarte: Steckbrief + Status-Badge + Datenpunkte mit Werten.

    `status`/`open_alarm_count`/`open_by_severity`/`last_alarm_at` sind der Maschinen-
    Status (kanonische Komposition, FCSM-mappbar wie im Cockpit). `stream` trägt den
    Eingangs-Stream-Status, damit die Karte ehrlich „live" vs. „Stand vor X" zeigen
    kann statt statische Historie als frisch auszugeben.
    """

    id: int
    label: str
    line_id: int | None
    machine_class: str | None
    manufacturer: str | None
    external_id: str | None
    location: str | None
    status: MachineStatus
    open_alarm_count: int
    open_by_severity: dict[str, int]
    last_alarm_at: datetime | None
    components: tuple[ComponentCard, ...]
    data_points: tuple[DataPointCard, ...]
    stream: StreamStatus


def _data_point_card(
    data_point: DataPoint,
    latest: LatestValue | None,
    profile: DriftProfile | None,
    dp_alarms: Sequence[Alarm],
) -> DataPointCard:
    """Baut einen Datenpunkt-Karteneintrag aus Stammdaten + Wert + Status (rein)."""
    last_value = latest.value if latest is not None else None
    last_value_at = latest.at if latest is not None else None
    # Detektor-Band für den Zeitpunkt des letzten Werts (geteilte Korridor-Quelle).
    corridor = None
    if profile is not None and last_value_at is not None:
        corridor = corridor_at(
            profile.state_medians, profile.noise_sigma, profile.effect_size_k, last_value_at
        )
    has_open_drift_alarm = any(
        alarm.code == DRIFT_ALARM_CODE and alarm.acknowledged_at is None for alarm in dp_alarms
    )
    status = derive_datapoint_status(
        last_value=last_value,
        normal_min=data_point.normal_min,
        normal_max=data_point.normal_max,
        corridor=corridor,
        has_open_drift_alarm=has_open_drift_alarm,
        has_open_alarm=bool(dp_alarms),
    )
    return DataPointCard(
        id=data_point.id,
        component_id=data_point.component_id,
        name=data_point.name,
        kind=data_point.kind,
        measurement_type=data_point.measurement_type,
        unit=data_point.unit,
        normal_min=data_point.normal_min,
        normal_max=data_point.normal_max,
        last_value=last_value,
        last_value_at=last_value_at,
        status=status,
    )


def _machine_card(
    machine: Machine,
    components: Sequence[Component],
    data_points: Sequence[DataPoint],
    latest_map: dict[int, LatestValue],
    profile_map: dict[int, DriftProfile],
    open_alarm_list: Sequence[Alarm],
    stream: StreamStatus,
) -> MachineCard:
    """Setzt eine Maschinenkarte aus Stammdaten + Komponenten + Datenpunkten zusammen."""
    status, count = compose_status(open_alarm_list)
    by_severity = Counter(alarm.severity for alarm in open_alarm_list)
    last_alarm_at = max((alarm.raised_at for alarm in open_alarm_list), default=None)
    # Offene Alarme je Datenpunkt (nur die, die einen Datenpunkt referenzieren).
    alarms_by_dp: dict[int, list[Alarm]] = {}
    for alarm in open_alarm_list:
        if alarm.data_point_id is not None:
            alarms_by_dp.setdefault(alarm.data_point_id, []).append(alarm)
    return MachineCard(
        id=machine.id,
        label=machine.label,
        line_id=machine.line_id,
        machine_class=machine.machine_class,
        manufacturer=machine.manufacturer,
        external_id=machine.external_id,
        location=machine.location,
        status=status,
        open_alarm_count=count,
        open_by_severity=dict(by_severity),
        last_alarm_at=last_alarm_at,
        components=tuple(
            ComponentCard(id=c.id, label=c.label, component_type=c.component_type)
            for c in components
        ),
        data_points=tuple(
            _data_point_card(
                dp, latest_map.get(dp.id), profile_map.get(dp.id), alarms_by_dp.get(dp.id, [])
            )
            for dp in data_points
        ),
        stream=stream,
    )


async def build_fleet_cards(
    session: AsyncSession,
    *,
    machine_ids: Sequence[int] | None = None,
    now: datetime | None = None,
) -> tuple[MachineCard, ...]:
    """Baut die lebenden Karten über alle (oder die scope-begrenzten) Maschinen.

    Batched (kein N+1): je eine Abfrage für Maschinen, Komponenten, Datenpunkte,
    jüngste Werte (readings_1m), Eigenprofile und offene Alarme. `machine_ids`
    begrenzt den Scope (die Autorisierungs-Schicht reicht die sichtbaren Maschinen
    durch); `now` ist injizierbar (Tests) und misst den Eingangs-Stream.
    """
    resolved_now = now if now is not None else datetime.now(UTC)
    machine_stmt = select(Machine).order_by(Machine.id)
    if machine_ids is not None:
        machine_stmt = machine_stmt.where(Machine.id.in_(machine_ids))
    machines = (await session.scalars(machine_stmt)).all()
    if not machines:
        return ()
    loaded_ids = [machine.id for machine in machines]

    components = (
        await session.scalars(
            select(Component).where(Component.machine_id.in_(loaded_ids)).order_by(Component.id)
        )
    ).all()
    comps_by_machine: dict[int, list[Component]] = {}
    for component in components:
        comps_by_machine.setdefault(component.machine_id, []).append(component)

    data_points = (
        await session.scalars(
            select(DataPoint).where(DataPoint.machine_id.in_(loaded_ids)).order_by(DataPoint.id)
        )
    ).all()
    dps_by_machine: dict[int, list[DataPoint]] = {}
    for data_point in data_points:
        dps_by_machine.setdefault(data_point.machine_id, []).append(data_point)

    all_dp_ids = [data_point.id for data_point in data_points]
    latest_map = await latest_values_for_data_points(session, all_dp_ids)
    profile_map = await load_drift_profiles_for_data_points(session, all_dp_ids)
    open_map = await open_alarms_for_machines(session, loaded_ids)
    stream = await build_stream_status(session, now=resolved_now)

    return tuple(
        _machine_card(
            machine,
            comps_by_machine.get(machine.id, []),
            dps_by_machine.get(machine.id, []),
            latest_map,
            profile_map,
            open_map.get(machine.id, []),
            stream,
        )
        for machine in machines
    )


async def build_machine_card(
    session: AsyncSession, machine_id: int, *, now: datetime | None = None
) -> MachineCard | None:
    """Baut die lebende Karte EINER Maschine (Detail-Erstbild + WS machine:{id}).

    Greift auf denselben Builder zu (Scope = die eine Maschine) — eine Quelle der
    Wahrheit mit dem Grid. None, wenn die Maschine nicht existiert.
    """
    cards = await build_fleet_cards(session, machine_ids=[machine_id], now=now)
    return cards[0] if cards else None
