# ============================================================
#  FOREMAN — tests/unit/test_adapter_contract.py
#  Zweck: Pflicht-Test-Block: SimulationAdapter erfüllt das SourceAdapter-
#  Interface und erzeugt korrektes Normalformat (ohne DB — Fake-Topologie).
#  Prüft: Interface, Registry, Drift im Signal (drift vs. steady), Event-Strom,
#  Quality-„missing"-Auslassung, zeitlich sortierter stream().
#  Architektur-Einordnung: Quality Gate §10.3.
# ============================================================
from __future__ import annotations

import statistics

from foreman.adapters.simulation.adapter import SimulationAdapter
from foreman.adapters.simulation.scenario import Scenario, load_scenario_by_name
from foreman.adapters.simulation.seed import TopologyMap
from foreman.ingestion.adapter import SourceAdapter, stream_item_time
from foreman.ingestion.normalized import (
    AlarmEvent,
    MaintenanceRecord,
    NormalizedReading,
    ProductionRunRecord,
    WorkerNoteRecord,
)
from foreman.ingestion.registry import available_adapters, create_adapter


def _fake_seed(adapter: SimulationAdapter) -> None:
    """Setzt eine künstliche Topologie (statt echter DB) für reine Generierungs-Tests."""
    scenario = adapter.scenario
    component_ids = {c.key: i + 1 for i, c in enumerate(scenario.components)}
    data_point_ids = {d.key: i + 1 for i, d in enumerate(scenario.data_points)}
    adapter._topology = TopologyMap(
        line_id=1,
        machine_id=1,
        component_ids=component_ids,
        data_point_ids=data_point_ids,
    )


def _running_vib(adapter: SimulationAdapter) -> list[float]:
    vib_id = adapter.topology.data_point_ids["vib_rms"]
    return [r.value for r in adapter.readings() if r.data_point_id == vib_id and r.value > 0.5]


# --------------------------------------------------------------------------- #
#  Interface + Registry
# --------------------------------------------------------------------------- #
def test_simulation_adapter_erfuellt_source_adapter_interface() -> None:
    adapter = SimulationAdapter(load_scenario_by_name("minimal_bearing_drift"))
    assert isinstance(adapter, SourceAdapter)
    assert adapter.name == "simulation"
    # Pflicht-Methoden vorhanden + aufrufbar.
    assert hasattr(adapter, "seed_topology")
    assert callable(adapter.readings)
    assert callable(adapter.events)
    assert callable(adapter.stream)


def test_registry_kennt_simulation_und_baut_adapter() -> None:
    assert "simulation" in available_adapters()
    adapter = create_adapter("simulation", scenario_name="minimal_steady")
    assert isinstance(adapter, SimulationAdapter)
    assert adapter.scenario.scenario.name == "minimal_steady"


def test_topology_zugriff_vor_seed_wirft() -> None:
    adapter = SimulationAdapter(load_scenario_by_name("minimal_steady"))
    try:
        _ = adapter.topology
    except RuntimeError as exc:
        assert "seed_topology" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Zugriff auf topology vor seed_topology muss werfen.")


# --------------------------------------------------------------------------- #
#  Readings: Drift im Signal nachweisbar (gegen bekannte Wahrheit)
# --------------------------------------------------------------------------- #
def test_readings_sind_utc_und_tragen_data_point_id() -> None:
    adapter = SimulationAdapter(load_scenario_by_name("minimal_bearing_drift"))
    _fake_seed(adapter)
    first = next(iter(adapter.readings()))
    assert isinstance(first, NormalizedReading)
    assert first.time.utcoffset() is not None
    assert first.time.utcoffset().total_seconds() == 0  # type: ignore[union-attr]
    assert first.data_point_id in adapter.topology.data_point_ids.values()


def test_drift_szenario_zeigt_anstieg_ab_t_star() -> None:
    adapter = SimulationAdapter(load_scenario_by_name("minimal_bearing_drift"), seed=1)
    _fake_seed(adapter)
    running = _running_vib(adapter)
    assert len(running) > 60
    early = statistics.mean(running[:30])
    late = statistics.mean(running[-30:])
    assert early < 2.5  # nahe Baseline 1.8
    assert late > early + 1.5  # Drift sichtbar gestiegen


def test_steady_szenario_zeigt_keinen_drift() -> None:
    adapter = SimulationAdapter(load_scenario_by_name("minimal_steady"), seed=1)
    _fake_seed(adapter)
    running = _running_vib(adapter)
    early = statistics.mean(running[:30])
    late = statistics.mean(running[-30:])
    assert abs(late - early) < 0.5  # driftfrei: kein systematischer Anstieg


def test_readings_wiederholbar_bei_gleichem_seed() -> None:
    adapter = SimulationAdapter(load_scenario_by_name("minimal_steady"), seed=7)
    _fake_seed(adapter)
    first = [r.value for r in adapter.readings()]
    second = [r.value for r in adapter.readings()]
    assert first == second


# --------------------------------------------------------------------------- #
#  Events: Strom enthält Alarme/Produktionsläufe/Wartung/Notizen, zeitsortiert
# --------------------------------------------------------------------------- #
def test_event_strom_enthaelt_alle_arten_zeitsortiert() -> None:
    adapter = SimulationAdapter(load_scenario_by_name("minimal_bearing_drift"))
    _fake_seed(adapter)
    events = list(adapter.events())
    kinds = {type(e) for e in events}
    assert AlarmEvent in kinds
    assert ProductionRunRecord in kinds
    assert MaintenanceRecord in kinds
    assert WorkerNoteRecord in kinds
    times = [e.occurred_at for e in events]
    assert times == sorted(times)


def test_maintenance_event_traegt_rohe_performed_by_ref() -> None:
    adapter = SimulationAdapter(load_scenario_by_name("minimal_bearing_drift"))
    _fake_seed(adapter)
    maintenance = [e for e in adapter.events() if isinstance(e, MaintenanceRecord)]
    assert maintenance
    assert maintenance[0].performed_by_ref == "U-1"  # roh, Service tokenisiert


def test_stream_ist_zeitlich_sortiert() -> None:
    adapter = SimulationAdapter(load_scenario_by_name("minimal_bearing_drift"))
    _fake_seed(adapter)
    times = [stream_item_time(item) for item in adapter.stream()]
    assert times == sorted(times)


# --------------------------------------------------------------------------- #
#  Quality „missing" → Intervall wird ausgelassen (nicht als 0 geschrieben)
# --------------------------------------------------------------------------- #
def test_quality_missing_laesst_intervalle_aus() -> None:
    data = {
        "schema_version": 1,
        "scenario": {
            "name": "miss",
            "start": "2026-05-04T06:00:00+02:00",
            "duration": "8h",
            "sample_interval": "30m",
        },
        "line": {"label": "L"},
        "machine": {"external_id": "Q-1", "label": "M"},
        "components": [],
        "seasonality": {"shifts": {"frueh": {"from": "06:00", "to": "22:00"}}},
        "data_points": [
            {
                "key": "state",
                "name": "machine_running",
                "machine_level": True,
                "kind": "digital",
                "unit": "bool",
                "source": "simulation",
                "baseline": {"driven_by": "shift_schedule"},
            },
            {
                "key": "always_missing",
                "name": "ghost",
                "kind": "analog",
                "measurement_type": "signal",
                "unit": "mm/s",
                "source": "simulation",
                "baseline": {"mean": 1.0, "noise_std": 0.1, "gated_by": "state"},
                "quality": {"missing_probability": 1.0},
            },
        ],
    }
    adapter = SimulationAdapter(Scenario.model_validate(data))
    _fake_seed(adapter)
    ghost_id = adapter.topology.data_point_ids["always_missing"]
    ghost_readings = [r for r in adapter.readings() if r.data_point_id == ghost_id]
    assert ghost_readings == []  # alle Intervalle ausgelassen, keine 0-Werte
