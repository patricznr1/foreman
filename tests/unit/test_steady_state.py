# ============================================================
#  FOREMAN — tests/unit/test_steady_state.py
#  Zweck: Pflicht-Test-Block für die Steady-State-Ableitung (F4).
#  Prüft: Roh-Stationarität (Lauf + Maschine läuft + kein Rüsten), Lauf-
#  Zugehörigkeit, digitaler Schwellwert, Grace-Period nach Zustandswechsel
#  (Rüsten/Stillstand/Anlauf -> Detektor pausiert).
#  Architektur-Einordnung: Quality Gate §10.3 (Reasoner, State-Gating §3).
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from foreman.reasoners.drift.steady_state import (
    GRACE_PERIOD,
    OperatingState,
    SteadyStateGate,
    digital_state,
    in_any_run,
    is_raw_steady,
)


def _t(minute: int) -> datetime:
    return datetime(2026, 5, 4, 6, 0, tzinfo=UTC) + timedelta(minutes=minute)


# --------------------------------------------------------------------------- #
#  Roh-Stationarität
# --------------------------------------------------------------------------- #
def test_is_raw_steady_alle_bedingungen_erfuellt() -> None:
    state = OperatingState(in_production_run=True, machine_running=True, setup_active=False)
    assert is_raw_steady(state) is True


def test_is_raw_steady_ruesten_aktiv_ist_nicht_steady() -> None:
    state = OperatingState(in_production_run=True, machine_running=True, setup_active=True)
    assert is_raw_steady(state) is False


def test_is_raw_steady_maschine_steht_ist_nicht_steady() -> None:
    state = OperatingState(in_production_run=True, machine_running=False, setup_active=False)
    assert is_raw_steady(state) is False


def test_is_raw_steady_kein_lauf_ist_nicht_steady() -> None:
    state = OperatingState(in_production_run=False, machine_running=True, setup_active=False)
    assert is_raw_steady(state) is False


# --------------------------------------------------------------------------- #
#  Lauf-Zugehörigkeit
# --------------------------------------------------------------------------- #
def test_in_any_run_offener_lauf() -> None:
    runs = [(_t(0), None)]
    assert in_any_run(_t(30), runs) is True


def test_in_any_run_geschlossener_lauf() -> None:
    runs = [(_t(0), _t(60))]
    assert in_any_run(_t(30), runs) is True


def test_in_any_run_ausserhalb() -> None:
    runs = [(_t(0), _t(60))]
    assert in_any_run(_t(90), runs) is False


def test_in_any_run_grenzen_start_inklusiv_ende_exklusiv() -> None:
    runs = [(_t(0), _t(60))]
    assert in_any_run(_t(0), runs) is True   # Start inklusiv
    assert in_any_run(_t(60), runs) is False  # Ende exklusiv


# --------------------------------------------------------------------------- #
#  Digitaler Zustand aus Schwellwert
# --------------------------------------------------------------------------- #
def test_digital_state_schwellwert() -> None:
    assert digital_state(1.0) is True
    assert digital_state(0.0) is False
    assert digital_state(None) is False
    assert digital_state(0.5) is True   # Schwelle inklusiv
    assert digital_state(0.49) is False


# --------------------------------------------------------------------------- #
#  Grace-Period nach Zustandswechsel
# --------------------------------------------------------------------------- #
def _steady() -> OperatingState:
    return OperatingState(in_production_run=True, machine_running=True, setup_active=False)


def _stillstand() -> OperatingState:
    return OperatingState(in_production_run=True, machine_running=False, setup_active=False)


def test_gate_pausiert_in_grace_period_nach_anlauf() -> None:
    gate = SteadyStateGate(grace_period=timedelta(minutes=5))
    # Anlauf bei Minute 0: die ersten 5 Minuten gelten NICHT als steady.
    assert gate.update(_t(0), _steady()) is False
    assert gate.update(_t(4), _steady()) is False
    assert gate.update(_t(5), _steady()) is True   # Grace abgelaufen
    assert gate.update(_t(10), _steady()) is True


def test_gate_grace_period_setzt_nach_stillstand_neu_auf() -> None:
    gate = SteadyStateGate(grace_period=timedelta(minutes=5))
    gate.update(_t(0), _steady())
    assert gate.update(_t(6), _steady()) is True   # längst steady
    # Stillstand bei Minute 7 -> nicht steady, Grace-Period wird zurückgesetzt.
    assert gate.update(_t(7), _stillstand()) is False
    # Wiederanlauf bei Minute 8: erneut Grace-Period.
    assert gate.update(_t(8), _steady()) is False
    assert gate.update(_t(12), _steady()) is False
    assert gate.update(_t(13), _steady()) is True


def test_gate_default_grace_period_ist_fuenf_minuten() -> None:
    gate = SteadyStateGate()
    assert gate.grace_period == GRACE_PERIOD == timedelta(minutes=5)
