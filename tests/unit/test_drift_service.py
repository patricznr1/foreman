# ============================================================
#  FOREMAN — tests/unit/test_drift_service.py
#  Zweck: Pflicht-Test-Block für die reine Drift-Pipeline (F4, Baustein 5).
#  Prüft die Orchestrierung ohne DB: Gating -> Residuum -> Detektion -> Relevanz.
#  Drift im stationären Betrieb wird gemeldet; Stillstand/kein Lauf füttern den
#  Detektor nicht; stationäres Signal bleibt still.
#  Architektur-Einordnung: Quality Gate §10.3 (Reasoner-Service, reine Logik).
# ============================================================
from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta

from foreman.reasoners.drift.detector import WARMUP_MIN_SAMPLES, DataPointDriftState
from foreman.reasoners.drift.service import (
    MIN_STATE_PROFILE_SAMPLES,
    DriftFinding,
    MachineSample,
    detect_drift_in_stream,
    extract_profile,
)

_START = datetime(2026, 5, 4, 6, 0, tzinfo=UTC)


def _make_samples(
    analog: list[float], *, running: float = 1.0, dp_id: int = 1
) -> list[MachineSample]:
    return [
        MachineSample(
            bucket=_START + timedelta(minutes=i),
            machine_running=running,
            setup_active=None,
            analog_values={dp_id: v},
        )
        for i, v in enumerate(analog)
    ]


def _noisy(rng: random.Random, level: float, n: int) -> list[float]:
    return [level + rng.gauss(0.0, 0.05) for _ in range(n)]


def test_pipeline_meldet_relevante_drift_im_steady_state() -> None:
    rng = random.Random(1)
    values = _noisy(rng, 10.0, 150) + _noisy(rng, 16.0, 80)  # +6 Niveausprung
    runs = [(_START, None)]
    findings = list(
        detect_drift_in_stream(
            _make_samples(values), runs, min_effect_size=4.0, persistence_intervals=3
        )
    )
    assert len(findings) >= 1
    assert findings[0].data_point_id == 1
    assert findings[0].detected_at >= _START + timedelta(minutes=150)  # nach t*


def test_pipeline_meldet_nichts_wenn_maschine_steht() -> None:
    # machine_running = 0 -> nie steady -> Detektor wird nicht gefüttert.
    values = [10.0] * 100 + [50.0] * 100
    runs = [(_START, None)]
    findings = list(detect_drift_in_stream(_make_samples(values, running=0.0), runs))
    assert findings == []


def test_pipeline_ohne_runs_gatet_per_machine_running() -> None:
    # Fehlen production_runs (häufige Szenario-Datenlage), trägt machine_running
    # das Gating allein: bei laufender Maschine wird die Drift erkannt.
    rng = random.Random(7)
    values = _noisy(rng, 10.0, 150) + _noisy(rng, 16.0, 80)
    findings = list(
        detect_drift_in_stream(
            _make_samples(values), runs=[], min_effect_size=4.0, persistence_intervals=3
        )
    )
    assert len(findings) >= 1


def test_pipeline_runs_grenzen_gaten_wenn_vorhanden() -> None:
    # Sind production_runs vorhanden, gaten ihre Grenzen: ein Sprung AUSSERHALB
    # jedes Laufs wird nicht gefüttert (Detektor pausiert), trotz machine_running=1.
    values = [10.0] * 300 + [50.0] * 100  # konstant im Lauf, Sprung außerhalb
    runs = [(_START, _START + timedelta(minutes=300))]
    findings = list(
        detect_drift_in_stream(
            _make_samples(values), runs, min_effect_size=4.0, persistence_intervals=3
        )
    )
    assert findings == []


def test_pipeline_meldet_nichts_auf_stationaerem_signal() -> None:
    rng = random.Random(2)
    values = [10.0 + rng.gauss(0.0, 0.1) for _ in range(500)]
    runs = [(_START, None)]
    findings = list(
        detect_drift_in_stream(
            _make_samples(values), runs, min_effect_size=4.0, persistence_intervals=5
        )
    )
    assert findings == []


def test_drift_finding_traegt_kennzahlen() -> None:
    rng = random.Random(3)
    values = _noisy(rng, 5.0, 150) + _noisy(rng, 12.0, 80)
    runs = [(_START, None)]
    findings = list(
        detect_drift_in_stream(
            _make_samples(values), runs, min_effect_size=4.0, persistence_intervals=3
        )
    )
    assert findings
    finding = findings[0]
    assert isinstance(finding, DriftFinding)
    assert finding.effect_size >= 4.0  # über der Relevanz-Schwelle


# --------------------------------------------------------------------------- #
#  Profil-Extraktion am Laufende (F4-Eigenprofil): Band = ECHTE Detektor-Basis
# --------------------------------------------------------------------------- #
def test_extract_profile_traegt_detektor_median_und_sigma() -> None:
    # Band = Detektor-Basis: das Profil übernimmt EXAKT current_median(state_key) +
    # die eingefrorene noise_sigma — kein im Read neu gerechneter Wert.
    rng = random.Random(11)
    state = DataPointDriftState()
    for _ in range(WARMUP_MIN_SAMPLES + 30):
        state.update(10.0 + rng.gauss(0.0, 1.0), in_steady_state=True, state_key=8)

    profile = extract_profile(data_point_id=42, machine_id=7, state=state, effect_size_k=3.0)

    assert profile is not None
    assert profile.data_point_id == 42 and profile.machine_id == 7
    assert profile.noise_sigma == state.noise_sigma  # exakt die Detektor-Streuung
    assert profile.effect_size_k == 3.0
    entry = profile.state_medians["8"]
    assert entry["median"] == state.baseline.current_median(8)  # exakt der Zustands-Median
    assert entry["sample_count"] >= WARMUP_MIN_SAMPLES


def test_extract_profile_ueberspringt_zustand_mit_zu_wenig_samples() -> None:
    # Ein Zustand mit zu wenig Stichprobe fehlt im Profil (ehrlich leer, nicht geraten).
    rng = random.Random(5)
    state = DataPointDriftState()
    for _ in range(WARMUP_MIN_SAMPLES + 30):
        state.update(10.0 + rng.gauss(0.0, 1.0), in_steady_state=True, state_key=8)
    for _ in range(MIN_STATE_PROFILE_SAMPLES - 1):
        state.update(10.0 + rng.gauss(0.0, 1.0), in_steady_state=True, state_key=20)

    profile = extract_profile(data_point_id=1, machine_id=1, state=state, effect_size_k=3.0)

    assert profile is not None
    assert "8" in profile.state_medians
    assert "20" not in profile.state_medians  # < MIN_STATE_PROFILE_SAMPLES -> weggelassen


def test_extract_profile_none_ohne_etablierte_streuung() -> None:
    # Vor Warm-up-Ende ist die Streuung nicht etabliert -> kein Profil (nicht geraten).
    state = DataPointDriftState()
    state.update(10.0, in_steady_state=True, state_key=8)
    assert extract_profile(data_point_id=1, machine_id=1, state=state, effect_size_k=3.0) is None
