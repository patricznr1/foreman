# ============================================================
#  FOREMAN — reasoners/drift/steady_state.py
#  Zweck: Ableitung des stationären Betriebszustands (in_steady_state) für das
#         State-Gating des Drift-Reasoners (Research §3, Baustein 1).
#  Architektur-Einordnung: Reasoning-Schicht (F4). Der Detektor läuft NICHT auf
#         dem Rohsignal, sondern nur auf vergleichbaren, stationären Phasen:
#         laufender production_run + Maschine läuft + kein Rüsten. Nach jedem
#         Zustandswechsel (Anlauf/Rüsten/Stillstand) pausiert der Detektor eine
#         Grace-Period lang, bis der Betrieb wieder eingeschwungen ist.
#  Reine, seedbare Logik (ohne DB testbar); die DB-Anbindung liegt im Service.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final

# Grace-Period nach Zustandswechsel (Research §6.1: ~5 min nach Anlauf/Rüsten).
GRACE_PERIOD: Final = timedelta(minutes=5)

# Schwellwert, ab dem ein (aggregierter) digitaler Messwert als "an" gilt.
_DIGITAL_THRESHOLD: Final = 0.5


@dataclass(frozen=True)
class OperatingState:
    """Roher Betriebszustand zu einem Zeitpunkt.

    Abgeleitet aus `production_runs` (in_production_run) und digitalen
    `data_points` (machine_running, setup_active). Trägt noch KEINE
    Grace-Period — die kommt im `SteadyStateGate` dazu.
    """

    in_production_run: bool
    machine_running: bool
    setup_active: bool


def is_raw_steady(state: OperatingState) -> bool:
    """Roh-stationär: laufender Produktionslauf, Maschine läuft, kein Rüsten.

    Ohne Grace-Period — der erste Sample nach Wiederaufnahme ist hier bereits
    "steady". Das Einschwingen erledigt das `SteadyStateGate`.
    """
    return state.in_production_run and state.machine_running and not state.setup_active


def in_any_run(t: datetime, runs: Sequence[tuple[datetime, datetime | None]]) -> bool:
    """True, wenn `t` in einem Produktionslauf liegt (Start inklusiv, Ende exklusiv).

    Ein offener Lauf (`ended_at is None`) reicht bis in die Gegenwart.
    """
    for started_at, ended_at in runs:
        if t >= started_at and (ended_at is None or t < ended_at):
            return True
    return False


def digital_state(value: float | None, *, threshold: float = _DIGITAL_THRESHOLD) -> bool:
    """Digitaler Zustand aus einem (aggregierten) Wert via Schwellwert.

    Fehlender Wert (None — z. B. kein readings_1m-Bucket) gilt als "aus".
    """
    return value is not None and value >= threshold


@dataclass
class SteadyStateGate:
    """Verarbeitet zeitlich geordnete Betriebszustände und liefert in_steady_state.

    Stateful: merkt sich den Beginn der laufenden stationären Phase, um die
    Grace-Period nach jeder Wiederaufnahme erneut anzuwenden. Außerhalb des
    stationären Betriebs wird der Detektor NICHT gefüttert (nicht "0" einspeisen).
    """

    grace_period: timedelta = GRACE_PERIOD
    _resumed_at: datetime | None = None
    _was_steady: bool = False

    def update(self, t: datetime, state: OperatingState) -> bool:
        """Verarbeitet den Zustand zum Zeitpunkt `t` und liefert in_steady_state.

        Erwartet zeitlich aufsteigende Aufrufe (Replay strikt in zeitlicher Ordnung).
        """
        if not is_raw_steady(state):
            self._was_steady = False
            self._resumed_at = None
            return False

        if not self._was_steady:
            # Übergang nicht-steady -> steady: Grace-Period startet jetzt.
            self._was_steady = True
            self._resumed_at = t

        assert self._resumed_at is not None  # durch obige Zuweisung garantiert
        if t - self._resumed_at < self.grace_period:
            return False
        return True
