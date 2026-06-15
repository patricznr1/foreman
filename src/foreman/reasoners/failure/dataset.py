# ============================================================
#  FOREMAN — reasoners/failure/dataset.py
#  Zweck: Trainingsdatensatz des Ausfallvorhersage-Reasoners (F-PRED) aus den
#         Simulations-Szenarien — rein/netzfrei. Je (Szenario/Seed) ein „Lauf":
#         erzeugt die Mess-Reihen in-memory über die signals.py-Primitive
#         (gleiche Wahrheit wie der Ingestion-Adapter, aber ohne DB), leitet
#         Drift-Events über die F4-Pipeline ab (Drift-Output als Feature),
#         tastet Bezugszeitpunkte ab und labelt: positiv = Vorlauf-Fenster vor
#         `ground_truth.failure` (Ausfall im Horizont H), negativ sonst.
#  Architektur-Einordnung: Reasoning-Schicht (F-PRED), Offline-Trainingspfad.
#  Anti-Leakage (verbindlich): Features stammen ausschließlich aus features.py
#         (strikt < reference_time); der Train/Eval-Split trennt DISJUNKTE LÄUFE
#         (kein zeilenweises Mischen von Fenstern desselben Laufs).
#
#  SIM-GRENZE (§16): Diese Daten sind synthetisch. Trainiert ein Modell auf den
#         Simulationsszenarien, lernt es den Simulator zurück — kein realer
#         Ausfall-Vorhersagewert. Begründung: docs/models/failure_prediction_model_card.md.
# ============================================================
from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import floor

# Wiederverwendung der Szenario→SignalProfile-Übersetzung (eine Quelle der Wahrheit,
# identisch zum Ingestion-Adapter) — der Offline-Trainingspfad erzeugt die Reihen
# in-memory statt über die DB.
from foreman.adapters.simulation.adapter import _build_profile
from foreman.adapters.simulation.scenario import (
    Scenario,
    clock_to_minutes,
    load_scenario_by_name,
    parse_duration,
)
from foreman.adapters.simulation.signals import (
    SeasonalitySpec,
    ShiftWindow,
    machine_state_value,
    sample_value,
)
from foreman.reasoners.drift.service import (
    MACHINE_RUNNING_NAME,
    MachineSample,
    detect_drift_in_stream,
)
from foreman.reasoners.failure.features import (
    BucketPoint,
    DataPointSeries,
    DriftEvent,
    FeatureWindow,
    extract_features,
    to_vector,
)

# Defaults des Trainingsdatensatz-Baus (für die reale Datenlage zu schärfen).
DEFAULT_LOOKBACK = timedelta(hours=72)
DEFAULT_STEP = timedelta(hours=12)
DEFAULT_WARMUP = timedelta(hours=24)


@dataclass(frozen=True)
class Sample:
    """Ein gelabeltes Trainings-Sample = ein Bezugszeitpunkt eines Laufs."""

    scenario: str
    seed: int
    reference_time: datetime
    features: dict[str, float]
    label: int

    @property
    def run_id(self) -> str:
        """Eindeutige Lauf-Kennung (Szenario/Seed) — die Split-Einheit (Anti-Leakage)."""
        return f"{self.scenario}:seed{self.seed}"


@dataclass(frozen=True)
class TrainingDataset:
    """Gelabelter Datensatz mit fixem Feature-Schema (Union über alle Samples)."""

    samples: tuple[Sample, ...]
    horizon: timedelta
    feature_names: tuple[str, ...]
    # Vorlauf-Fenster der Feature-Extraktion — im Artefakt verankert, damit die
    # Inferenz exakt dasselbe Fenster nutzt (Feature-Verteilungs-Konsistenz).
    lookback: timedelta = DEFAULT_LOOKBACK

    def class_balance(self) -> tuple[int, int]:
        """(#negativ, #positiv) — Klassenbalance, dokumentiert im Trainings-Log."""
        pos = sum(s.label for s in self.samples)
        return len(self.samples) - pos, pos

    def matrix(self) -> tuple[list[list[float]], list[int], list[str]]:
        """Feature-Matrix X, Labels y und Lauf-Gruppen (für gruppen-bewusste Splits)."""
        x = [to_vector(s.features, self.feature_names) for s in self.samples]
        y = [s.label for s in self.samples]
        groups = [s.run_id for s in self.samples]
        return x, y, groups


def _seasonality_of(scenario: Scenario) -> SeasonalitySpec:
    """Baut die SeasonalitySpec aus dem Szenario (identisch zum Adapter)."""
    return SeasonalitySpec(
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


def _enforce_bucket_invariants(scenario: Scenario, start_utc: datetime, interval_s: float) -> None:
    """Erzwingt die Bucket-Äquivalenz Training↔Inferenz (readings_1m = 1-Minuten-Buckets).

    Der Trainingspfad floort den Tick-Zeitstempel auf die Minute; die Inferenz nutzt
    `time_bucket('1 minute', time)`. Beide stimmen NUR überein, wenn der Start auf
    voller Minute liegt UND das Intervall ein ganzzahliges Minuten-Vielfaches ist —
    sonst stiller Train/Serve-Skew (Bucket-Kadenz/Anzahl). Außerdem spiegelt der
    Trainingspfad das Quality-Missing-Sampling des Adapters NICHT (er lässt keine
    Buckets aus) → Quality-freie Failure-Szenarien sind Pflicht. Laut scheitern.
    """
    if start_utc.second != 0 or start_utc.microsecond != 0:
        raise ValueError(
            "❌ scenario.start muss auf voller Minute liegen "
            "(readings_1m-Bucket-Konsistenz Training↔Inferenz)."
        )
    if interval_s % 60 != 0:
        raise ValueError(
            "❌ sample_interval muss ein ganzzahliges Minuten-Vielfaches sein "
            "(readings_1m-Bucket-Konsistenz Training↔Inferenz)."
        )
    for dp in scenario.data_points:
        if dp.quality is not None:
            raise ValueError(
                f"❌ Failure-Trainings-Szenario nutzt quality am data_point '{dp.key}' — "
                "der Trainingspfad spiegelt das Quality-Missing-Sampling nicht "
                "(sonst divergieren __n/__slope/__roc Training↔Inferenz). "
                "Quality-freie Failure-Szenarien sind Pflicht."
            )


def _generate_series(scenario: Scenario, seed: int) -> dict[str, DataPointSeries]:
    """Erzeugt die Mess-Reihen eines Laufs in-memory (netzfrei), je Datenpunkt-Name.

    Spiegelt die Adapter-Logik (signals.py-Primitive, deterministisch je Seed), aber
    ohne DB-Topologie — die Reihen werden über den stabilen `name` geschlüsselt. Ein
    Reading je Minuten-Bucket (avg == min == max), passend zur readings_1m-Semantik.
    """
    seasonality = _seasonality_of(scenario)
    start_local = scenario.scenario.start
    start_utc = scenario.start_utc
    interval_s = scenario.interval_delta.total_seconds()
    _enforce_bucket_invariants(scenario, start_utc, interval_s)
    n_ticks = floor(scenario.duration_delta.total_seconds() / interval_s)

    rngs = {dp.key: random.Random(f"{seed}:{dp.key}") for dp in scenario.data_points}
    plans = [
        (
            dp,
            dp.baseline is not None and dp.baseline.driven_by == "shift_schedule",
            _build_profile(dp),
        )
        for dp in scenario.data_points
    ]
    points: dict[str, list[BucketPoint]] = {dp.name: [] for dp in scenario.data_points}

    for i in range(n_ticks):
        local_dt = start_local + timedelta(seconds=i * interval_s)
        bucket = (start_utc + timedelta(seconds=i * interval_s)).replace(second=0, microsecond=0)
        elapsed_s = i * interval_s
        for dp, is_state, profile in plans:
            if is_state:
                value = machine_state_value(seasonality, local_dt)
            elif profile is not None:
                value = sample_value(profile, seasonality, local_dt, elapsed_s, rngs[dp.key])
            else:
                continue  # weder Lauf-Signal noch analoge Baseline → nicht erzeugbar
            points[dp.name].append(BucketPoint(bucket=bucket, avg=value, min=value, max=value))

    mt = {dp.name: dp.measurement_type for dp in scenario.data_points}
    return {
        name: DataPointSeries(name=name, measurement_type=mt[name], points=tuple(pts))
        for name, pts in points.items()
        if pts
    }


def _drift_events_for_run(
    scenario: Scenario, series_by_name: dict[str, DataPointSeries]
) -> list[DriftEvent]:
    """Leitet Drift-Events über die F4-Pipeline ab (Drift-Output als Feature).

    Verwendet synthetische Datenpunkt-IDs (das Feature nutzt nur Anzahl/Stärke/
    Zeit-seit, nicht welcher Datenpunkt). Ein Drift-`detected_at` nutzt definitions-
    gemäß nur Daten bis zu diesem Zeitpunkt — die fensterweise Filterung in
    features.py hält die Leakage-Sperre.

    GATING-ANNAHME: `detect_drift_in_stream(samples, runs=[])` läuft bewusst
    UNGEGATET. Die Inferenz (DriftService) gatet über die `production_runs` der
    Linie. Beide stimmen überein, solange die Ziel-Linie keine `production_runs`
    führt (so bei allen Failure-Szenarien) — sonst gatet die Inferenz enger
    (andere drift__count). Beim Realdaten-Wechsel anzugleichen (Model Card §4/§8).
    """
    analog_dps = [dp for dp in scenario.data_points if dp.kind == "analog"]
    if not analog_dps:
        return []
    synth_id = {dp.name: idx for idx, dp in enumerate(analog_dps, start=1)}
    state_series = series_by_name.get(MACHINE_RUNNING_NAME)
    state_by_bucket = {p.bucket: p.avg for p in state_series.points} if state_series else {}

    analog_by_bucket: dict[datetime, dict[int, float]] = {}
    for dp in analog_dps:
        series = series_by_name.get(dp.name)
        if series is None:
            continue
        sid = synth_id[dp.name]
        for point in series.points:
            analog_by_bucket.setdefault(point.bucket, {})[sid] = point.avg

    samples = [
        MachineSample(
            bucket=bucket,
            machine_running=state_by_bucket.get(bucket),
            setup_active=None,
            analog_values=analog_by_bucket[bucket],
        )
        for bucket in sorted(analog_by_bucket)
    ]
    findings = detect_drift_in_stream(samples, runs=[])
    return [DriftEvent(occurred_at=f.detected_at, effect_size=f.effect_size) for f in findings]


def _failure_time(scenario: Scenario) -> datetime | None:
    """Absolute (tz-aware UTC) Ausfallzeit aus ground_truth.failure, oder None."""
    gt = scenario.ground_truth
    if gt is None or gt.failure is None:
        return None
    return scenario.start_utc + parse_duration(gt.failure.offset)


def build_run_samples(
    scenario: Scenario,
    seed: int,
    *,
    horizon: timedelta,
    lookback: timedelta = DEFAULT_LOOKBACK,
    step: timedelta = DEFAULT_STEP,
    warmup: timedelta = DEFAULT_WARMUP,
) -> list[Sample]:
    """Baut die gelabelten Samples eines einzelnen Laufs (Szenario/Seed)."""
    series_by_name = _generate_series(scenario, seed)
    series = tuple(series_by_name.values())
    drift_events = tuple(_drift_events_for_run(scenario, series_by_name))
    start_utc = scenario.start_utc
    maintenance_times = tuple(
        start_utc + parse_duration(event.offset) for event in scenario.maintenance_events
    )
    # Nur Nicht-Drift-Alarme als Alarm-Historie (Drift fließt über das Drift-Feature).
    alarm_times = tuple(start_utc + parse_duration(alarm.offset) for alarm in scenario.alarms)

    failure_time = _failure_time(scenario)
    # Nach dem Ausfall wird nicht mehr vorhergesagt (last_ref = Ausfallzeitpunkt).
    last_ref = failure_time if failure_time is not None else start_utc + scenario.duration_delta

    samples: list[Sample] = []
    reference_time = start_utc + warmup
    while reference_time <= last_ref:
        window = FeatureWindow(
            reference_time=reference_time,
            lookback=lookback,
            series=series,
            drift_events=drift_events,
            maintenance_times=maintenance_times,
            alarm_times=alarm_times,
        )
        in_horizon = (
            failure_time is not None and reference_time <= failure_time <= reference_time + horizon
        )
        samples.append(
            Sample(
                scenario=scenario.scenario.name,
                seed=seed,
                reference_time=reference_time,
                features=extract_features(window),
                label=1 if in_horizon else 0,
            )
        )
        reference_time = reference_time + step
    return samples


def build_dataset(
    runs: Sequence[tuple[Scenario, int]],
    *,
    horizon: timedelta,
    lookback: timedelta = DEFAULT_LOOKBACK,
    step: timedelta = DEFAULT_STEP,
    warmup: timedelta = DEFAULT_WARMUP,
) -> TrainingDataset:
    """Baut den gesamten Trainingsdatensatz aus mehreren Läufen (Szenario/Seed)."""
    samples: list[Sample] = []
    for scenario, seed in runs:
        samples.extend(
            build_run_samples(
                scenario, seed, horizon=horizon, lookback=lookback, step=step, warmup=warmup
            )
        )
    feature_names = tuple(sorted({key for sample in samples for key in sample.features}))
    return TrainingDataset(
        samples=tuple(samples), horizon=horizon, feature_names=feature_names, lookback=lookback
    )


def split_by_seed(
    dataset: TrainingDataset, *, holdout_seeds: set[int]
) -> tuple[TrainingDataset, TrainingDataset]:
    """Lauf-disjunkter Split: Läufe mit Seed ∈ holdout_seeds bilden den Eval-Satz.

    Trennt ganze LÄUFE (kein zeilenweises Mischen) und behält das gemeinsame
    Feature-Schema in beiden Hälften (konsistente Matrix-Spalten).
    """
    train = tuple(s for s in dataset.samples if s.seed not in holdout_seeds)
    evaluation = tuple(s for s in dataset.samples if s.seed in holdout_seeds)
    return (
        TrainingDataset(
            samples=train,
            horizon=dataset.horizon,
            feature_names=dataset.feature_names,
            lookback=dataset.lookback,
        ),
        TrainingDataset(
            samples=evaluation,
            horizon=dataset.horizon,
            feature_names=dataset.feature_names,
            lookback=dataset.lookback,
        ),
    )


def load_runs(scenario_names: Sequence[str], seeds: Sequence[int]) -> list[tuple[Scenario, int]]:
    """Lädt die Szenarien per Name und kreuzt sie mit den Seeds zu Läufen (CLI-Helfer)."""
    return [(load_scenario_by_name(name), seed) for name in scenario_names for seed in seeds]
