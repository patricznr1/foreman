# ============================================================
#  FOREMAN — tests/unit/test_drift_detector.py
#  Zweck: Pflicht-Test-Block für den ADWIN-Drift-Detektor (F4, Research §6.2).
#  Prüft: injizierte step/ramp/variance-Drift wird nach t* erkannt; stationäres
#  Signal löst keinen Drift aus (Fehlalarm-Test); Warm-up unterdrückt frühe
#  Signale; State-Gating füttert den Detektor außerhalb des stationären Betriebs
#  nicht; der Reasoner hält je data_point einen unabhängigen Zustand.
#  Architektur-Einordnung: Quality Gate §10.3 (Reasoner, ADWIN §6).
# ============================================================
from __future__ import annotations

import random

from foreman.reasoners.drift.detector import (
    WARMUP_MIN_SAMPLES,
    DataPointDriftState,
    DriftReasoner,
)


def _first_detection(values: list[float]) -> int | None:
    """Speist die Werte (alle steady) in einen frischen Detektor und liefert den
    Index der ersten Drift-Meldung — oder None, wenn nie gemeldet wird."""
    state = DataPointDriftState()
    for i, v in enumerate(values):
        if state.update(v, in_steady_state=True):
            return i
    return None


def _noise(rng: random.Random, sigma: float) -> float:
    return rng.gauss(0.0, sigma)


# --------------------------------------------------------------------------- #
#  Drift-Typen werden erkannt (ab t*)
# --------------------------------------------------------------------------- #
def test_step_drift_wird_nach_t_star_erkannt() -> None:
    rng = random.Random(1)
    t_star = 150
    values = [10.0 + _noise(rng, 0.05) for _ in range(t_star)]
    values += [15.0 + _noise(rng, 0.05) for _ in range(150)]  # abrupter Niveausprung
    detected = _first_detection(values)
    assert detected is not None
    assert detected >= t_star  # nicht vor dem Sprung


def test_ramp_drift_wird_erkannt() -> None:
    rng = random.Random(2)
    t_star = 150
    values = [10.0 + _noise(rng, 0.05) for _ in range(t_star)]
    values += [10.0 + 0.1 * i + _noise(rng, 0.05) for i in range(200)]  # gradueller Ramp
    detected = _first_detection(values)
    assert detected is not None
    assert detected >= t_star


def test_varianz_drift_unter_last_wird_erkannt() -> None:
    # variance-Drift, wie er real auftritt (tool_wear spindle_speed_act): die
    # Ist-Drehzahl "zittert" unter Verschleiß-Last zunehmend UND bricht im Mittel
    # leicht ein. ADWIN erkennt den Mittelwert-Anteil. (Reine, symmetrische Varianz
    # OHNE Mittelwertshift erkennt ADWIN bauartbedingt schwach — Research §2.1;
    # dafür wäre der KSWIN-Zweitpfad gedacht, der bewusst NICHT in F4 ist.)
    rng = random.Random(3)
    t_star = 150
    values = [10.0 + _noise(rng, 0.05) for _ in range(t_star)]
    for i in range(300):
        sigma = 0.05 + 0.02 * i   # wachsende Streuung (Regelabweichung)
        dip = -0.01 * i           # leichter Lasteinbruch im Mittel
        values.append(10.0 + dip + _noise(rng, sigma))
    detected = _first_detection(values)
    assert detected is not None
    assert detected >= t_star


def test_reine_symmetrische_varianz_ist_dokumentierte_adwin_grenze() -> None:
    # Ehrliche Abgrenzung: eine reine, symmetrische Varianz-Erhöhung OHNE
    # Mittelwertshift wird von ADWIN über mehrere Seeds NICHT zuverlässig erkannt.
    # Das ist die bekannte ADWIN-Grenze (Research §2.1) und der Grund für den
    # späteren KSWIN-Zweitpfad (§8) — nicht ein Fehler des Detektors.
    detections = 0
    for seed in range(8):
        rng = random.Random(seed)
        values = [10.0 + _noise(rng, 0.05) for _ in range(150)]
        values += [10.0 + _noise(rng, 2.0) for _ in range(300)]  # nur Varianz, Mittel = 10
        if _first_detection(values) is not None:
            detections += 1
    assert detections < 8  # nicht zuverlässig (mind. ein Seed bleibt still)


# --------------------------------------------------------------------------- #
#  Fehlalarm-Test: stationäres Signal feuert nicht
# --------------------------------------------------------------------------- #
def test_stationaeres_signal_loest_keinen_drift_aus() -> None:
    rng = random.Random(4)
    values = [10.0 + _noise(rng, 0.1) for _ in range(800)]
    assert _first_detection(values) is None


# --------------------------------------------------------------------------- #
#  Warm-up + Gating
# --------------------------------------------------------------------------- #
def test_warmup_unterdrueckt_signal_vor_min_samples() -> None:
    # Ein sehr früher Sprung (innerhalb der Warm-up-Phase) darf NICHT gemeldet
    # werden, solange < WARMUP_MIN_SAMPLES gesehen wurden.
    rng = random.Random(5)
    values = [10.0 + _noise(rng, 0.05) for _ in range(10)]
    values += [99.0 + _noise(rng, 0.05) for _ in range(WARMUP_MIN_SAMPLES - 30)]
    detected = _first_detection(values)
    assert detected is None or detected >= WARMUP_MIN_SAMPLES


def test_nicht_steady_wird_nicht_gefuettert() -> None:
    state = DataPointDriftState()
    # Außerhalb des stationären Betriebs: kein Update, kein Drift, kein Verbrauch.
    for _ in range(500):
        assert state.update(99.0, in_steady_state=False) is False
    assert state.seen == 0
    assert state.baseline.count == 0


def test_effect_size_ist_standardisierter_z_score() -> None:
    # Die Effektgröße ist das Residuum normiert auf die Rausch-Streuung (z-Score) —
    # damit messgrößen-übergreifend (mm/s, Nm, °C) eine einheitliche Schwelle greift.
    rng = random.Random(11)
    state = DataPointDriftState()
    for _ in range(WARMUP_MIN_SAMPLES + 5):
        state.update(10.0 + _noise(rng, 1.0), in_steady_state=True)  # Rausch-sigma ~ 1
    state.update(15.0, in_steady_state=True)  # ~5sigma vom Profil entfernt
    assert state.effect_size > 3.5


def test_effect_size_ist_messgroessen_invariant() -> None:
    # Gleiche relative Abweichung bei verschiedener Skala -> vergleichbarer z-Score.
    rng = random.Random(12)
    small = DataPointDriftState()
    large = DataPointDriftState()
    for _ in range(WARMUP_MIN_SAMPLES + 5):
        n = rng.gauss(0.0, 1.0)
        small.update(10.0 + 0.1 * n, in_steady_state=True)      # Skala 0.1
        large.update(1000.0 + 50.0 * n, in_steady_state=True)   # Skala 50
    small.update(10.0 + 0.1 * 5, in_steady_state=True)          # +5sigma
    large.update(1000.0 + 50.0 * 5, in_steady_state=True)       # +5sigma
    assert abs(small.effect_size - large.effect_size) < 2.0


def test_effect_size_null_vor_warmup() -> None:
    state = DataPointDriftState()
    state.update(10.0, in_steady_state=True)
    assert state.effect_size == 0.0


def test_last_residual_wird_fuer_effektgroesse_exponiert() -> None:
    # Der Service braucht das letzte Residuum als Effektgrößen-Maß (Relevanz-Filter).
    state = DataPointDriftState()
    state.update(10.0, in_steady_state=True)  # Baseline leer -> Residuum 0
    assert state.last_residual == 0.0
    state.update(13.0, in_steady_state=True)  # median([10]) = 10 -> Residuum 3
    assert state.last_residual == 3.0


def test_reasoner_haelt_zustand_je_data_point_getrennt() -> None:
    reasoner = DriftReasoner()
    rng = random.Random(6)
    # data_point 1 driftet, data_point 2 bleibt stationär — unabhängige Zustände.
    drift_1 = False
    for i in range(400):
        v1 = (10.0 if i < 150 else 20.0) + _noise(rng, 0.05)
        v2 = 10.0 + _noise(rng, 0.05)
        if reasoner.observe(1, v1, in_steady_state=True):
            drift_1 = True
        assert reasoner.observe(2, v2, in_steady_state=True) is False
    assert drift_1 is True
