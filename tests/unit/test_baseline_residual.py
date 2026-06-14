# ============================================================
#  FOREMAN — tests/unit/test_baseline_residual.py
#  Zweck: Pflicht-Test-Block für die Residuumbildung/Deseasonalisierung (F4).
#  Prüft: gleitender Median je data_point, Residuum gegen das aktuelle Profil,
#  Fenster-Begrenzung, und dass ein saisonales Rohsignal zu einem um 0
#  zentrierten (driftfreien) Residuum wird — die betriebliche Schicht-Schwankung
#  fällt heraus, das Niveau verschwindet.
#  Architektur-Einordnung: Quality Gate §10.3 (Reasoner, Deseasonalisierung §3).
# ============================================================
from __future__ import annotations

import math
from statistics import mean

from foreman.reasoners.drift.baseline import BASELINE_WINDOW, RollingResidualBaseline


def test_baseline_window_default_ist_24h_bei_1min() -> None:
    assert BASELINE_WINDOW == 1440  # 24 h * 60 min
    assert RollingResidualBaseline().window == BASELINE_WINDOW


def test_erster_wert_residuum_ist_null() -> None:
    base = RollingResidualBaseline()
    # Ohne etabliertes Profil ist das Residuum 0 (kein Drift-Signal vertrauen).
    assert base.observe(5.0) == 0.0


def test_konstantes_signal_residuum_konvergiert_null() -> None:
    base = RollingResidualBaseline()
    for _ in range(100):
        base.observe(10.0)
    assert base.observe(10.0) == 0.0


def test_residuum_reagiert_auf_niveausprung() -> None:
    base = RollingResidualBaseline()
    for _ in range(100):
        base.observe(10.0)  # Median etabliert sich bei 10
    # Echte Drift: ein Niveausprung muss als positives Residuum durchkommen.
    assert base.observe(15.0) == 5.0


def test_fenster_begrenzt_median_auf_letzte_n() -> None:
    base = RollingResidualBaseline(window=3)
    base.observe(1.0)
    base.observe(2.0)
    base.observe(3.0)  # Fenster jetzt [1,2,3], Median 2
    # Der älteste Wert (1) fällt beim nächsten Sample heraus -> Fenster [2,3,100].
    assert base.observe(100.0) == 98.0  # 100 - median([1,2,3]) = 100 - 2
    assert base.current_median() == 3.0  # median([2,3,100])
    assert base.count == 3


def test_zustandsspezifischer_median_trennt_betriebszustaende() -> None:
    # Research §3: Median JE Betriebszustand. Zwei Zustände mit verschiedenem
    # Last-Niveau (Schicht) dürfen sich nicht zu einem Mischwert vermengen.
    base = RollingResidualBaseline()
    for _ in range(50):
        base.observe(10.0, state_key="frueh")
        base.observe(20.0, state_key="nacht")
    # Residuum gegen den EIGENEN Zustands-Median (~0), nicht gegen den globalen 15.
    assert base.observe(10.0, state_key="frueh") == 0.0
    assert base.observe(20.0, state_key="nacht") == 0.0
    # Eine echte Abweichung im Zustand bleibt sichtbar.
    assert base.observe(13.0, state_key="frueh") == 3.0


def test_saisonales_rohsignal_wird_zu_driftfreiem_residuum() -> None:
    # Rohsignal: betriebliches Niveau 50 + Schicht-Schwankung ±10 (Periode 60),
    # KEIN Verschleiß-Trend. Erwartung: Residuum um 0 zentriert (Niveau 50 raus),
    # ohne systematische Drift.
    base = RollingResidualBaseline(window=120)  # 2 volle Perioden
    residuals: list[float] = []
    for i in range(600):
        raw = 50.0 + 10.0 * math.sin(2 * math.pi * i / 60)
        residuals.append(base.observe(raw))

    tail = residuals[200:]  # nach Warmup
    # Niveau (50) ist heraus -> Residuen um 0, nicht um 50.
    assert abs(mean(tail)) < 1.0
    # Erste vs. zweite Hälfte des Tails: kein systematischer Drift (driftfrei).
    half = len(tail) // 2
    assert abs(mean(tail[:half]) - mean(tail[half:])) < 1.0
