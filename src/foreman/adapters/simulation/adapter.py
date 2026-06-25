# ============================================================
#  FOREMAN — adapters/simulation/adapter.py
#  Zweck: SimulationAdapter (F3) — konkreter SourceAdapter. Übersetzt ein
#         validiertes Szenario über die Signal-Generatoren in normalisierte
#         Readings/Events und seedet vorher idempotent die Topologie.
#  Architektur-Einordnung: Datenakquise (Schicht 2). Oberhalb dieses Adapters
#         existiert kein Simulationswissen — der IngestionService sieht nur das
#         SourceAdapter-Interface (NormalizedReading/NormalizedEvent).
# ============================================================
from __future__ import annotations

import math
import random
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, tzinfo
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from foreman.adapters.simulation.scenario import (
    DataPointSpec,
    DriftConfig,
    QualityConfig,
    Scenario,
    clock_to_minutes,
    load_scenario_by_name,
    load_scenario_file,
    parse_duration,
)
from foreman.adapters.simulation.seed import TopologyMap, seed_topology
from foreman.adapters.simulation.signals import (
    DriftSpec,
    QualitySpec,
    SeasonalitySpec,
    ShiftWindow,
    SignalProfile,
    machine_state_value,
    sample_quality,
    sample_value,
)
from foreman.ingestion.adapter import SourceAdapter
from foreman.ingestion.normalized import (
    AlarmEvent,
    MaintenanceRecord,
    NormalizedEvent,
    NormalizedReading,
    ProductionRunRecord,
    WorkerNoteRecord,
)
from foreman.ingestion.registry import register_adapter

# Default-Seed, wenn keiner übergeben wird — macht Backfills reproduzierbar
# (wichtig für F4-Validierung gegen bekannte Wahrheit und für Tests).
DEFAULT_SEED = 1234


@dataclass
class _DataPointPlan:
    """Vorberechneter Erzeugungsplan je Datenpunkt (ohne RNG/IDs — die kommen
    erst beim Streamen, damit readings() reproduzierbar wiederholbar ist)."""

    key: str
    is_state: bool
    profile: SignalProfile | None
    quality: QualitySpec | None


def _build_drift(cfg: DriftConfig | None) -> DriftSpec | None:
    if cfg is None:
        return None
    end_s = parse_duration(cfg.end).total_seconds() if cfg.end is not None else None
    return DriftSpec(
        kind=cfg.type,
        start_s=parse_duration(cfg.start).total_seconds(),
        end_s=end_s,
        target_delta=cfg.target_delta or 0.0,
        std_multiplier=cfg.std_multiplier or 1.0,
        progressive=cfg.shape == "progressive",
    )


def _build_quality(cfg: QualityConfig | None) -> QualitySpec | None:
    if cfg is None:
        return None
    return QualitySpec(
        bad_probability=cfg.bad_probability,
        missing_probability=cfg.missing_probability,
    )


def _build_profile(dp: DataPointSpec) -> SignalProfile | None:
    baseline = dp.baseline
    if baseline is None or baseline.mean is None:
        return None
    return SignalProfile(
        mean=baseline.mean,
        noise_std=baseline.noise_std or 0.0,
        idle_value=dp.normal_min if dp.normal_min is not None else 0.0,
        gated=baseline.gated_by is not None,
        drift=_build_drift(dp.drift),
    )


class SimulationAdapter(SourceAdapter):
    """Szenario-getriebener Generator realistischer Sensordaten mit Drift bei t*."""

    def __init__(
        self,
        scenario: Scenario,
        *,
        seed: int | None = None,
        end_anchor: datetime | None = None,
    ) -> None:
        self._scenario = scenario
        self._seed = seed if seed is not None else DEFAULT_SEED
        # --anchor-now: verschiebt das GESAMTE Zeitfenster, sodass das Szenario-Ende auf
        # `end_anchor` fällt (Demo-Frische, damit die Daten nicht veralten). Die relative
        # Struktur (Degradations-Offsets, Saisonalität) bleibt unverändert — nur das
        # absolute Fenster wandert. end_anchor=None → kein Versatz (feste YAML-Zeit,
        # reproduzierbar für Tests/F4-Validierung).
        self._time_shift: timedelta = (
            end_anchor - (scenario.start_utc + scenario.duration_delta)
            if end_anchor is not None
            else timedelta(0)
        )
        self._topology: TopologyMap | None = None
        self._seasonality = SeasonalitySpec(
            shifts=tuple(
                ShiftWindow(
                    name=name,
                    start_min=clock_to_minutes(shift.from_),
                    end_min=clock_to_minutes(shift.to),
                    load_factor=shift.load_factor,
                )
                for name, shift in scenario.seasonality.shifts.items()
            ),
            weekend=scenario.seasonality.weekend,
            weekend_load_factor=scenario.seasonality.weekend_load_factor,
        )
        self._plans: list[_DataPointPlan] = []
        for dp in scenario.data_points:
            is_state = dp.baseline is not None and dp.baseline.driven_by == "shift_schedule"
            profile = _build_profile(dp)
            if not is_state and profile is None:
                raise ValueError(
                    f"data_point '{dp.key}' hat weder ein Lauf-Signal (driven_by) "
                    "noch eine analoge Baseline (mean) — nicht erzeugbar."
                )
            self._plans.append(
                _DataPointPlan(
                    key=dp.key,
                    is_state=is_state,
                    profile=profile,
                    quality=_build_quality(dp.quality),
                )
            )

    # --- Factory für die Registry ---
    @classmethod
    def from_config(
        cls,
        *,
        scenario: Scenario | None = None,
        scenario_name: str | None = None,
        scenario_path: str | Path | None = None,
        seed: int | None = None,
        end_anchor: datetime | None = None,
    ) -> SimulationAdapter:
        """Baut den Adapter aus Szenario-Objekt, -Name oder -Pfad (Registry-Eintrag)."""
        if scenario is not None:
            resolved = scenario
        elif scenario_path is not None:
            resolved = load_scenario_file(scenario_path)
        elif scenario_name is not None:
            resolved = load_scenario_by_name(scenario_name)
        else:
            raise ValueError(
                "SimulationAdapter braucht 'scenario', 'scenario_name' oder 'scenario_path'."
            )
        return cls(resolved, seed=seed, end_anchor=end_anchor)

    @property
    def name(self) -> str:
        return "simulation"

    @property
    def scenario(self) -> Scenario:
        return self._scenario

    @property
    def topology(self) -> TopologyMap:
        if self._topology is None:
            raise RuntimeError("seed_topology() muss vor dem Streamen laufen.")
        return self._topology

    async def seed_topology(self, session: AsyncSession) -> None:
        """Legt die Topologie idempotent an und merkt sich die ID-Auflösung."""
        self._topology = await seed_topology(session, self._scenario)

    # --- Zeitachse ---
    def _tick_count(self) -> int:
        interval_s = self._scenario.interval_delta.total_seconds()
        if interval_s <= 0:
            raise ValueError("sample_interval muss > 0 sein.")
        return math.floor(self._scenario.duration_delta.total_seconds() / interval_s)

    def _offset_to_utc(self, offset: str) -> datetime:
        return self._scenario.start_utc + self._time_shift + parse_duration(offset)

    # --- wiederverwendbare Erzeugungs-Nähte (Backfill UND Live-Worker) ---
    def new_rngs(self) -> dict[str, random.Random]:
        """Frische, deterministische RNGs je Datenpunkt für EINEN Erzeugungslauf.

        Einmal pro Lauf bauen und über die Ticks fortschreiben — so bleibt der
        Rauschstrom reproduzierbar (gleicher Seed → gleiche Werte)."""
        return {plan.key: random.Random(f"{self._seed}:{plan.key}") for plan in self._plans}

    @property
    def local_timezone(self) -> tzinfo:
        """Zeitzone der Szenario-Schichtzeit (Wall-Clock-UTC → Lokal für die Saisonalität)."""
        tz = self._scenario.scenario.start.tzinfo
        assert tz is not None  # scenario.start ist per Validator tz-aware
        return tz

    def end_elapsed_s(self) -> float:
        """Verstrichene Sim-Sekunden am LETZTEN Backfill-Tick — der Plateau-Anker.

        Der Live-Worker führt die Drift ab hier als Plateau fort (konstant statt
        weiterlaufend), damit ein kranker Zustand am Ende der Historie gehalten,
        aber nicht ins Absurde getrieben wird."""
        interval_s = self._scenario.interval_delta.total_seconds()
        return max(self._tick_count() - 1, 0) * interval_s

    def tick_readings(
        self,
        *,
        utc_time: datetime,
        local_dt: datetime,
        elapsed_s: float,
        rngs: Mapping[str, random.Random],
        data_point_ids: Mapping[str, int],
    ) -> Iterator[NormalizedReading]:
        """Erzeugt die Readings EINES Ticks (alle Datenpunkte) zum Stempel `utc_time`.

        Der gemeinsame Kern von Backfill und Live-Lauf — der einzige Unterschied
        ist die Zeitquelle (Szenario-Sim-Zeit vs. Wall-Clock) und `elapsed_s`
        (laufend im Backfill, Plateau im Live-Lauf). `utc_time` wird unverändert
        als Stempel getragen."""
        for plan in self._plans:
            data_point_id = data_point_ids[plan.key]
            rng = rngs[plan.key]
            if plan.is_state:
                yield NormalizedReading(
                    time=utc_time,
                    data_point_id=data_point_id,
                    value=machine_state_value(self._seasonality, local_dt),
                    quality=None,
                )
                continue
            assert plan.profile is not None  # durch __init__ garantiert
            quality = sample_quality(plan.quality, rng)
            if quality == "missing":
                continue  # fehlendes Intervall: NICHT als 0 schreiben (ausgelassen)
            value = sample_value(plan.profile, self._seasonality, local_dt, elapsed_s, rng)
            yield NormalizedReading(
                time=utc_time,
                data_point_id=data_point_id,
                value=value,
                quality=quality,
            )

    # --- normalisierte Ausgabe (Backfill) ---
    def readings(self) -> Iterator[NormalizedReading]:
        """Erzeugt die Messwerte tick-für-tick über die Szenario-Zeitachse (sortiert)."""
        rngs = self.new_rngs()
        data_point_ids = self.topology.data_point_ids
        start_local = self._scenario.scenario.start  # tz-aware (lokale Schichtzeit)
        interval_s = self._scenario.interval_delta.total_seconds()

        for i in range(self._tick_count()):
            # local_dt: lokale Schicht-Wandzeit (für Saisonalität/Schichtlogik).
            # utc_dt: derselbe Instant in UTC — der Normalform-Vertrag (§12) emittiert UTC.
            local_dt = start_local + self._time_shift + timedelta(seconds=i * interval_s)
            utc_dt = self._scenario.start_utc + self._time_shift + timedelta(seconds=i * interval_s)
            yield from self.tick_readings(
                utc_time=utc_dt,
                local_dt=local_dt,
                elapsed_s=i * interval_s,
                rngs=rngs,
                data_point_ids=data_point_ids,
            )

    def events(self) -> Iterator[NormalizedEvent]:
        """Erzeugt die diskreten Ereignisse (Alarme/Produktionsläufe/Wartung/Notizen),
        aufsteigend nach Zeit sortiert."""
        topology = self.topology
        comp_ids = topology.component_ids
        events: list[NormalizedEvent] = []

        for run in self._scenario.production_runs:
            events.append(
                ProductionRunRecord(
                    occurred_at=self._offset_to_utc(run.start),
                    line_id=topology.line_id,
                    product_code=run.product_code,
                    order_id=run.order_id,
                    batch=run.batch,
                    started_at=self._offset_to_utc(run.start),
                    ended_at=self._offset_to_utc(run.end) if run.end else None,
                )
            )
        for alarm in self._scenario.alarms:
            events.append(
                AlarmEvent(
                    occurred_at=self._offset_to_utc(alarm.offset),
                    machine_id=topology.machine_id,
                    component_id=comp_ids.get(alarm.component) if alarm.component else None,
                    data_point_id=(
                        topology.data_point_ids.get(alarm.data_point) if alarm.data_point else None
                    ),
                    code=alarm.code,
                    message=alarm.message,
                    severity=alarm.severity,
                    category=alarm.category,
                )
            )
        for maintenance in self._scenario.maintenance_events:
            events.append(
                MaintenanceRecord(
                    occurred_at=self._offset_to_utc(maintenance.offset),
                    machine_id=topology.machine_id,
                    component_id=(
                        comp_ids.get(maintenance.component) if maintenance.component else None
                    ),
                    type=maintenance.type,
                    description=maintenance.description,
                    performed_by_ref=maintenance.performed_by,
                )
            )
        for note in self._scenario.worker_notes:
            events.append(
                WorkerNoteRecord(
                    occurred_at=self._offset_to_utc(note.offset),
                    machine_id=topology.machine_id,
                    shift=note.shift,
                    text=note.text,
                    author_ref=note.author,
                )
            )

        events.sort(key=lambda event: event.occurred_at)
        return iter(events)


# Registrierung in der Ingestion-Registry (Import-Seiteneffekt, siehe __init__).
register_adapter("simulation", SimulationAdapter.from_config)
