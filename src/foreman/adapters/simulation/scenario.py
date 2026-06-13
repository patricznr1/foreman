# ============================================================
#  FOREMAN — adapters/simulation/scenario.py
#  Zweck: Pydantic-v2-Modell des Simulations-Szenarios (F3) — Topologie +
#         Signal-Profile + injizierbare Drift + diskrete Ereignisse (Alarme/
#         Produktionsläufe/Wartung) + optionale Werker-Notizen + F4-Ground-Truth.
#  Architektur-Einordnung: Datenakquise (Schicht 2), Simulations-Adapter.
#  Verbindliches Schema: das aus der Cowork-Vorarbeit abgeleitete, an
#         GROUND_TRUTH §5 angelehnte YAML-Schema (docs/simulation/szenarien.md).
#         Strikt validiert (extra=forbid) — ungültige Szenarien werden abgelehnt.
#  Zeit: scenario.start ist absolut tz-aware; Ereignis-/Drift-Zeiten sind
#         Dauer-Offsets ('7d','16d14h','5m') ab start. Die DB führt UTC.
# ============================================================
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from foreman.schemas.resources import AlarmSeverity, DataPointKind, DataPointSource

# measurement_type: geschlossener Wertebereich aus GROUND_TRUTH §5 (Schwingung ist
# bewusst auf 'signal'/mm/s gemappt — Vorschlag 'vibration' liegt bei F-Revision).
MeasurementType = Literal[
    "voltage",
    "current",
    "dc_bus",
    "temperature",
    "speed",
    "frequency",
    "torque",
    "force",
    "signal",
]

# Verzeichnis der mitgelieferten Szenarien (by-name-Laden).
SCENARIOS_DIR = Path(__file__).parent / "scenarios"

# Dauer-/Offset-Format: Kombination aus Tagen/Stunden/Minuten/Sekunden.
_DURATION_RE = re.compile(r"^(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$")
# Schicht-Zeitfenster "HH:MM".
_CLOCK_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


def parse_duration(value: str) -> timedelta:
    """Parst eine Dauer-/Offset-Angabe ('7d', '16d14h', '5m', '0d') zu timedelta."""
    text = value.strip()
    match = _DURATION_RE.fullmatch(text)
    if match is None or not any(match.groups()):
        raise ValueError(
            f"Ungültige Dauer-/Offset-Angabe: '{value}' "
            "(erwartet z. B. '7d', '16d14h', '5m', '30s')."
        )
    days, hours, minutes, seconds = (int(group or 0) for group in match.groups())
    return timedelta(days=days, hours=hours, minutes=minutes, seconds=seconds)


def clock_to_minutes(value: str) -> int:
    """Parst 'HH:MM' zu Minuten-ab-Mitternacht (Schicht-Grenzen)."""
    match = _CLOCK_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"Ungültige Uhrzeit: '{value}' (erwartet 'HH:MM').")
    return int(match.group(1)) * 60 + int(match.group(2))


def _validate_duration_str(value: str) -> str:
    parse_duration(value)  # wirft bei Ungültigkeit
    return value


class _Strict(BaseModel):
    """Basis: strikte Validierung — unbekannte Felder werden abgelehnt."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ScenarioMeta(_Strict):
    """Der `scenario:`-Block: Identität + Zeitachse."""

    name: str = Field(min_length=1)
    title: str | None = None
    description: str | None = None
    start: datetime
    duration: str
    sample_interval: str

    _v_duration = field_validator("duration", "sample_interval")(_validate_duration_str)

    @field_validator("start")
    @classmethod
    def _start_tz_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("scenario.start muss tz-aware sein (mit Zeitzonen-Offset).")
        return value


class LineSpec(_Strict):
    label: str = Field(min_length=1)
    location: str | None = None


class MachineSpec(_Strict):
    external_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    machine_class: str | None = None
    manufacturer: str | None = None
    location: str | None = None


class ComponentSpec(_Strict):
    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    # component_type: offener Wertebereich (spindle/drive/bearing/motor/axis/…).
    component_type: str | None = None


class ShiftSpec(_Strict):
    from_: str = Field(alias="from")
    to: str
    load_factor: float = 1.0

    @field_validator("from_", "to")
    @classmethod
    def _clock(cls, value: str) -> str:
        clock_to_minutes(value)
        return value


class SeasonalityConfig(_Strict):
    shifts: dict[str, ShiftSpec]
    weekend: Literal["idle", "reduced"] = "idle"
    weekend_load_factor: float = 0.6
    note: str | None = None

    @field_validator("shifts")
    @classmethod
    def _at_least_one_shift(cls, value: dict[str, ShiftSpec]) -> dict[str, ShiftSpec]:
        if not value:
            raise ValueError("seasonality.shifts darf nicht leer sein.")
        return value


class BaselineSpec(_Strict):
    """Signal-Baseline. Zwei Varianten:

    - digital (machine_state): `driven_by: shift_schedule`,
    - analog: `mean` (+ `noise_std`, + `gated_by` Datenpunkt-Key).
    """

    driven_by: str | None = None
    mean: float | None = None
    noise_std: float | None = None
    gated_by: str | None = None


class DriftConfig(_Strict):
    """Injizierte Drift bei bekanntem t* (Offset) — Validierung gegen Wahrheit (§7)."""

    type: Literal["ramp", "step", "variance"]
    start: str
    end: str | None = None
    target_delta: float | None = None
    shape: Literal["linear", "progressive"] | None = None
    std_multiplier: float | None = None

    _v_start = field_validator("start")(_validate_duration_str)

    @field_validator("end")
    @classmethod
    def _v_end(cls, value: str | None) -> str | None:
        return _validate_duration_str(value) if value is not None else None

    @model_validator(mode="after")
    def _consistency(self) -> DriftConfig:
        if self.type in ("ramp", "step") and self.target_delta is None:
            raise ValueError(f"Drift-Typ '{self.type}' erfordert 'target_delta'.")
        if self.type == "variance" and self.std_multiplier is None:
            raise ValueError("Drift-Typ 'variance' erfordert 'std_multiplier'.")
        return self


class QualityConfig(_Strict):
    """Optionales Quality-Verhalten (sonst quality=None)."""

    bad_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    missing_probability: float = Field(default=0.0, ge=0.0, le=1.0)


class DataPointSpec(_Strict):
    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    machine_level: bool = False
    component: str | None = None
    kind: DataPointKind
    measurement_type: MeasurementType | None = None
    unit: str | None = None
    source: DataPointSource = "simulation"
    normal_min: float | None = None
    normal_max: float | None = None
    baseline: BaselineSpec | None = None
    drift: DriftConfig | None = None
    quality: QualityConfig | None = None


class ProductionRunSpec(_Strict):
    """Produktionslauf (Linien-Ebene). Zeiten als Offsets ab scenario.start."""

    product_code: str = Field(min_length=1)
    order_id: str | None = None
    batch: str | None = None
    start: str
    end: str | None = None

    _v_start = field_validator("start")(_validate_duration_str)

    @field_validator("end")
    @classmethod
    def _v_end(cls, value: str | None) -> str | None:
        return _validate_duration_str(value) if value is not None else None


class MaintenanceEventSpec(_Strict):
    offset: str
    component: str | None = None
    type: str = Field(min_length=1)
    description: str | None = None
    # Synthetische User-Referenz; wird VOR dem Insert tokenisiert (§8).
    performed_by: str | None = None

    _v_offset = field_validator("offset")(_validate_duration_str)


class WorkerNoteSpec(_Strict):
    offset: str
    shift: str | None = None
    author: str | None = None
    text: str = Field(min_length=1)

    _v_offset = field_validator("offset")(_validate_duration_str)


class AlarmSpec(_Strict):
    offset: str
    component: str | None = None
    data_point: str | None = None
    code: str | None = None
    message: str | None = None
    severity: AlarmSeverity
    category: str = Field(min_length=1)

    _v_offset = field_validator("offset")(_validate_duration_str)


class GroundTruth(BaseModel):
    """F4-Validierungs-Wahrheit. F3 parst/validiert sie nur grob (drift_present);
    die präzise Struktur ist F4-Domäne — daher extra='allow'."""

    model_config = ConfigDict(extra="allow")

    drift_present: bool
    expected_false_alarms: int = 0


class Scenario(_Strict):
    """Vollständiges Simulations-Szenario (eine Linie, eine Maschine)."""

    schema_version: int = 1
    scenario: ScenarioMeta
    line: LineSpec
    machine: MachineSpec
    components: list[ComponentSpec] = Field(default_factory=list)
    seasonality: SeasonalityConfig
    data_points: list[DataPointSpec] = Field(min_length=1)
    production_runs: list[ProductionRunSpec] = Field(default_factory=list)
    maintenance_events: list[MaintenanceEventSpec] = Field(default_factory=list)
    worker_notes: list[WorkerNoteSpec] = Field(default_factory=list)
    alarms: list[AlarmSpec] = Field(default_factory=list)
    ground_truth: GroundTruth | None = None

    @model_validator(mode="after")
    def _referential_integrity(self) -> Scenario:
        comp_keys = [component.key for component in self.components]
        dp_keys = [dp.key for dp in self.data_points]
        if len(set(comp_keys)) != len(comp_keys):
            raise ValueError("components: doppelte 'key'-Werte.")
        if len(set(dp_keys)) != len(dp_keys):
            raise ValueError("data_points: doppelte 'key'-Werte.")
        comp_set, dp_set = set(comp_keys), set(dp_keys)

        for dp in self.data_points:
            if dp.component is not None and dp.component not in comp_set:
                raise ValueError(
                    f"data_point '{dp.key}': unbekannte Komponente '{dp.component}'."
                )
            if dp.baseline and dp.baseline.gated_by and dp.baseline.gated_by not in dp_set:
                raise ValueError(
                    f"data_point '{dp.key}': gated_by '{dp.baseline.gated_by}' "
                    "ist kein bekannter Datenpunkt."
                )
        for alarm in self.alarms:
            if alarm.component is not None and alarm.component not in comp_set:
                raise ValueError(f"alarm: unbekannte Komponente '{alarm.component}'.")
            if alarm.data_point is not None and alarm.data_point not in dp_set:
                raise ValueError(f"alarm: unbekannter Datenpunkt '{alarm.data_point}'.")
        for event in self.maintenance_events:
            if event.component is not None and event.component not in comp_set:
                raise ValueError(
                    f"maintenance_event: unbekannte Komponente '{event.component}'."
                )
        return self

    # --- abgeleitete Zeitachse (vom Adapter genutzt) ---
    @property
    def start_utc(self) -> datetime:
        from foreman.ingestion.normalized import ensure_utc

        return ensure_utc(self.scenario.start)

    @property
    def duration_delta(self) -> timedelta:
        return parse_duration(self.scenario.duration)

    @property
    def interval_delta(self) -> timedelta:
        return parse_duration(self.scenario.sample_interval)


def load_scenario_from_dict(data: dict[str, Any]) -> Scenario:
    """Validiert ein bereits geparstes YAML-Dict zu einem Scenario."""
    return Scenario.model_validate(data)


def load_scenario_file(path: str | Path) -> Scenario:
    """Lädt + validiert ein Szenario aus einer YAML-Datei."""
    raw = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError(f"Szenario-Datei {path} enthält kein YAML-Mapping.")
    return load_scenario_from_dict(data)


def load_scenario_by_name(name: str) -> Scenario:
    """Lädt ein mitgeliefertes Szenario per Name aus dem scenarios/-Verzeichnis."""
    path = SCENARIOS_DIR / f"{name}.yaml"
    if not path.exists():
        available = ", ".join(sorted(p.stem for p in SCENARIOS_DIR.glob("*.yaml")))
        raise FileNotFoundError(
            f"Szenario '{name}' nicht gefunden in {SCENARIOS_DIR}. Verfügbar: {available}."
        )
    return load_scenario_file(path)
