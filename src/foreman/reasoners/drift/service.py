# ============================================================
#  FOREMAN — reasoners/drift/service.py
#  Zweck: Orchestrierung des Drift-Reasoners (F4, Baustein 5). Verbindet die
#         Pipeline readings_1m -> State-Gating -> Residuum/Deseasonalisierung ->
#         ADWIN-Detektion -> Relevanz-Filter und persistiert erkannte, relevante
#         Drift als Ereignis (semantic_event + best-effort Substrat-Dual-Write,
#         §9-Fallback) zuzüglich einer operatorseitigen alarms-Warnung
#         (category=process, severity=warning). KEINE Aktorik (§8) — der
#         Reasoner warnt, schaltet nie.
#  Architektur-Einordnung: Reasoning-Schicht (F4). Die zeitkritische Pipeline
#         (`detect_drift_in_stream`) ist eine reine, seedbare Funktion ohne DB;
#         `DriftService` ist die dünne DB-Anbindung darum herum (§6 DI/Testbarkeit).
# ============================================================
from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from time import perf_counter

from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import Alarm, DataPoint, Machine, ProductionRun
from foreman.ingestion.semantic import record_semantic_event
from foreman.logging_setup import ALERT, ERROR, REASON, get_logger
from foreman.observability.metrics import observe_reasoner_run, record_drift_event
from foreman.reasoners.drift.detector import DriftReasoner
from foreman.reasoners.drift.relevance import (
    DEFAULT_MIN_EFFECT_SIZE,
    DEFAULT_PERSISTENCE_INTERVALS,
    RelevanceFilter,
)
from foreman.reasoners.drift.steady_state import (
    OperatingState,
    SteadyStateGate,
    digital_state,
    in_any_run,
)
from foreman.substrate.client import SubstrateClient

logger = get_logger("foreman.reasoners.drift")

# Namens-Konvention der digitalen Gating-Datenpunkte (Szenario-/SPS-Seite).
MACHINE_RUNNING_NAME = "machine_running"
SETUP_ACTIVE_NAME = "setup_active"

# Kennzeichnung der Drift-Warnung im alarms-Schema (§5).
DRIFT_ALARM_CATEGORY = "process"
DRIFT_ALARM_SEVERITY = "warning"
DRIFT_ALARM_CODE = "DRIFT"
DRIFT_EVENT_TYPE = "drift_detected"


@dataclass(frozen=True)
class MachineSample:
    """Ein 1-Minuten-Bucket einer Maschine aus `readings_1m`.

    `machine_running`/`setup_active` sind die digitalen Gating-Werte (last_value);
    `analog_values` bildet je überwachtem analogem data_point den `avg_value` ab.
    """

    bucket: datetime
    machine_running: float | None
    setup_active: float | None
    analog_values: dict[int, float]


@dataclass(frozen=True)
class DriftFinding:
    """Eine erkannte, relevante Drift (vor der Persistierung)."""

    data_point_id: int
    detected_at: datetime
    effect_size: float


@dataclass(frozen=True)
class MachineTopology:
    """Aufgelöste Topologie einer Maschine für das Gating + die Überwachung."""

    machine_id: int
    line_id: int | None
    analog_ids: tuple[int, ...]
    machine_running_id: int
    setup_active_id: int | None


def detect_drift_in_stream(
    samples: Iterable[MachineSample],
    runs: Sequence[tuple[datetime, datetime | None]],
    *,
    gate: SteadyStateGate | None = None,
    reasoner: DriftReasoner | None = None,
    relevance: Mapping[int, RelevanceFilter] | None = None,
    min_effect_size: float = DEFAULT_MIN_EFFECT_SIZE,
    persistence_intervals: int = DEFAULT_PERSISTENCE_INTERVALS,
) -> Iterator[DriftFinding]:
    """Reine Drift-Pipeline über einen zeitlich geordneten Sample-Strom.

    Reihenfolge zwingend (Research §3): Steady-State-Gate -> Residuum/ADWIN ->
    Relevanz. Außerhalb des stationären Betriebs wird der Detektor NICHT
    gefüttert. Liefert je relevanter Drift-Episode ein `DriftFinding`.
    """
    gate = gate or SteadyStateGate()
    reasoner = reasoner or DriftReasoner()
    filters: dict[int, RelevanceFilter] = dict(relevance or {})

    # production_runs VERFEINERN das Gating. Fehlen sie ganz (häufige Datenlage:
    # Szenarien/SPS ohne explizites Lauf-Konzept), trägt machine_running das
    # Gating allein — sonst liefe der Reasoner nie an. Sind runs vorhanden, gaten
    # ihre Grenzen wie üblich (außerhalb jedes Laufs -> nicht stationär).
    runs_known = bool(runs)
    for sample in samples:  # strikt zeitlich aufsteigend erwartet
        state = OperatingState(
            in_production_run=in_any_run(sample.bucket, runs) if runs_known else True,
            machine_running=digital_state(sample.machine_running),
            setup_active=digital_state(sample.setup_active),
        )
        in_steady = gate.update(sample.bucket, state)
        # Zustands-Schlüssel für die Deseasonalisierung: die Tagesstunde trennt die
        # zyklische Schicht-Last, sodass je Schicht ein eigener Median greift
        # (Research §3). Damit verschwindet das systematische Schicht-Residuum, das
        # sonst Fehlalarme auf gesunden Maschinen auslöst.
        state_key = sample.bucket.hour

        for data_point_id, value in sorted(sample.analog_values.items()):
            signaled = reasoner.observe(
                data_point_id, value, in_steady_state=in_steady, state_key=state_key
            )
            dp_state = reasoner.state_for(data_point_id)
            effect = dp_state.effect_size if dp_state is not None else 0.0
            flt = filters.setdefault(
                data_point_id,
                RelevanceFilter(
                    min_effect_size=min_effect_size,
                    persistence_intervals=persistence_intervals,
                ),
            )
            if flt.update(effect, drift_signaled=signaled):
                yield DriftFinding(
                    data_point_id=data_point_id,
                    detected_at=sample.bucket,
                    effect_size=effect,
                )


@dataclass
class DriftService:
    """DB-Anbindung des Drift-Reasoners: lädt readings_1m, fährt die Pipeline,
    persistiert Drift-Ereignisse (semantic_event + alarms-Warnung, HITL)."""

    session: AsyncSession
    substrate: SubstrateClient | None = None
    min_effect_size: float = DEFAULT_MIN_EFFECT_SIZE
    persistence_intervals: int = DEFAULT_PERSISTENCE_INTERVALS
    _last_findings: list[DriftFinding] = field(default_factory=list, init=False, repr=False)

    async def run_machine(
        self, machine_id: int, start: datetime, end: datetime
    ) -> list[DriftFinding]:
        """Fährt den Drift-Reasoner für eine Maschine über [start, end) und
        persistiert die erkannten, relevanten Drift-Ereignisse."""
        t0 = perf_counter()
        try:
            topology = await self._load_topology(machine_id)
            runs = await self._load_runs(topology.line_id)
            samples = await self._load_samples(topology, start, end)
            findings = list(
                detect_drift_in_stream(
                    samples,
                    runs,
                    min_effect_size=self.min_effect_size,
                    persistence_intervals=self.persistence_intervals,
                )
            )
            for finding in findings:
                await self._emit_drift_event(finding, machine_id)
        except Exception:
            observe_reasoner_run("drift", perf_counter() - t0, success=False)
            logger.exception(
                "%s Drift-Reasoner-Lauf fehlgeschlagen machine_id=%s", ERROR, machine_id
            )
            raise

        latency_s = perf_counter() - t0
        observe_reasoner_run("drift", latency_s, success=True)
        # Strukturierter Reasoner-Log (§11.1): Latenz/Erfolg/Umfang, keine PII.
        logger.info(
            "%s reasoner=drift machine_id=%s samples=%s findings=%s latency_ms=%.1f",
            REASON,
            machine_id,
            len(samples),
            len(findings),
            latency_s * 1000.0,
        )
        self._last_findings = findings
        return findings

    async def _load_topology(self, machine_id: int) -> MachineTopology:
        machine = await self.session.get(Machine, machine_id)
        if machine is None:
            raise ValueError(f"Maschine {machine_id} nicht gefunden.")
        data_points = (
            await self.session.scalars(select(DataPoint).where(DataPoint.machine_id == machine_id))
        ).all()

        analog_ids: list[int] = []
        machine_running_id: int | None = None
        setup_active_id: int | None = None
        for dp in data_points:
            if dp.name == MACHINE_RUNNING_NAME:
                machine_running_id = dp.id
            elif dp.name == SETUP_ACTIVE_NAME:
                setup_active_id = dp.id
            elif dp.kind == "analog":
                analog_ids.append(dp.id)

        if machine_running_id is None:
            raise ValueError(
                f"Maschine {machine_id} hat kein '{MACHINE_RUNNING_NAME}'-Signal "
                "für das State-Gating."
            )
        return MachineTopology(
            machine_id=machine_id,
            line_id=machine.line_id,
            analog_ids=tuple(sorted(analog_ids)),
            machine_running_id=machine_running_id,
            setup_active_id=setup_active_id,
        )

    async def _load_runs(self, line_id: int | None) -> list[tuple[datetime, datetime | None]]:
        if line_id is None:
            return []
        runs = (
            await self.session.scalars(
                select(ProductionRun).where(ProductionRun.line_id == line_id)
            )
        ).all()
        return [(run.started_at, run.ended_at) for run in runs]

    async def _load_samples(
        self, topology: MachineTopology, start: datetime, end: datetime
    ) -> list[MachineSample]:
        dp_ids = [*topology.analog_ids, topology.machine_running_id]
        if topology.setup_active_id is not None:
            dp_ids.append(topology.setup_active_id)

        # readings_1m ist ein Continuous Aggregate (View) -> Roh-SQL. avg_value für
        # analoge Größen, last_value für digitale Zustände (§5, Detektor-Input 1/min).
        stmt = text(
            "SELECT bucket, data_point_id, avg_value, last_value "
            "FROM readings_1m "
            "WHERE data_point_id IN :dp_ids AND bucket >= :start AND bucket < :end "
            "ORDER BY bucket"
        ).bindparams(bindparam("dp_ids", expanding=True))
        rows = (
            await self.session.execute(stmt, {"dp_ids": dp_ids, "start": start, "end": end})
        ).all()

        analog_set = set(topology.analog_ids)
        buckets: dict[datetime, MachineSample] = {}
        for bucket, data_point_id, avg_value, last_value in rows:
            current = buckets.get(bucket)
            running = current.machine_running if current else None
            setup = current.setup_active if current else None
            analog = dict(current.analog_values) if current else {}
            if data_point_id == topology.machine_running_id:
                running = last_value
            elif data_point_id == topology.setup_active_id:
                setup = last_value
            elif data_point_id in analog_set and avg_value is not None:
                analog[data_point_id] = avg_value
            buckets[bucket] = MachineSample(
                bucket=bucket,
                machine_running=running,
                setup_active=setup,
                analog_values=analog,
            )
        return [buckets[b] for b in sorted(buckets)]

    async def _emit_drift_event(self, finding: DriftFinding, machine_id: int) -> Alarm:
        """Persistiert ein Drift-Ereignis: semantic_event (best-effort Dual-Write)
        + operatorseitige alarms-Warnung. KEINE Aktorik."""
        payload = {
            "reasoner": "drift",
            "machine_id": machine_id,
            "data_point_id": finding.data_point_id,
            "detected_at": finding.detected_at.isoformat(),
            "effect_size": round(finding.effect_size, 4),
        }
        await record_semantic_event(
            self.session,
            machine_id=machine_id,
            event_type=DRIFT_EVENT_TYPE,
            payload=payload,
            content=(
                f"Verhaltens-Drift an Datenpunkt {finding.data_point_id} erkannt "
                f"(Effektgröße {finding.effect_size:.2f})."
            ),
            substrate=self.substrate,
        )
        alarm = Alarm(
            machine_id=machine_id,
            data_point_id=finding.data_point_id,
            code=DRIFT_ALARM_CODE,
            message=(
                f"Verhaltens-Drift an Datenpunkt {finding.data_point_id} erkannt — "
                "Operator-Quittierung erforderlich."
            ),
            severity=DRIFT_ALARM_SEVERITY,
            category=DRIFT_ALARM_CATEGORY,
            raised_at=finding.detected_at,
        )
        self.session.add(alarm)
        record_drift_event()
        logger.info(
            "%s Drift-Warnung erzeugt machine_id=%s data_point_id=%s",
            ALERT,
            machine_id,
            finding.data_point_id,
        )
        return alarm
