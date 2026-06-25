# ============================================================
#  FOREMAN — reasoners/drift/baseline.py
#  Zweck: Residuumbildung / Deseasonalisierung für den Drift-Reasoner
#         (Research §3 + §6.1, Baustein 2).
#  Architektur-Einordnung: Reasoning-Schicht (F4). Statt des Rohwerts füttert
#         der Detektor ein RESIDUUM gegen ein erwartetes Profil: den gleitenden
#         Median der zuletzt gesehenen Werte JE BETRIEBSZUSTAND (Research §3 —
#         "Median des gleichen Zustands"). Der Zustands-Schlüssel (z.B. die
#         Tagesstunde) trennt die zyklische Schicht-Last: jede Schicht hat ihren
#         eigenen Median, sodass die betriebliche Saisonalität herausfällt und nur
#         das Verschleißsignal übrig bleibt. Ohne Zustands-Schlüssel (state_key
#         None) verhält sich die Baseline wie ein globaler gleitender Median.
#  Reine, seedbare Logik (ohne DB testbar).
# ============================================================
from __future__ import annotations

from collections import deque
from collections.abc import Hashable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from statistics import median
from typing import Any, Final

# Gleitendes Baseline-Fenster: 1440 Min = 24 h bei 1 Sample/Minute (Research §6.1).
BASELINE_WINDOW: Final = 1440


def state_key_for(moment: datetime) -> int:
    """Zustands-Schlüssel der Deseasonalisierung: die Tagesstunde (0-23).

    Trennt die zyklische Schicht-Last, sodass je Schicht ein eigener Median greift
    (Research §3). EINE Quelle für den Detektor-Lauf (`detect_drift_in_stream`) UND
    die Read-Expansion des Eigenprofil-Bands — würde sie dupliziert, zeigte das Band
    den Korridor des falschen Zustands.
    """
    return moment.hour


def corridor_at(
    state_medians: Mapping[str, Any],
    noise_sigma: float,
    effect_size_k: float,
    moment: datetime,
) -> tuple[float, float, float] | None:
    """Korridor `(lower, mid, upper)` des zum Zeitpunkt `moment` geltenden Zustands.

    `mid` ist der gleitende Zustands-Median, die Halbbreite `effect_size_k *
    noise_sigma` ist genau die Schwelle, ab der der Detektor das Residuum als relevant
    wertet — die ECHTE Detektor-Bewertungsbasis, kein neu erfundener Schwellwert. Der
    Zustand wird über `state_key_for(moment)` bestimmt (DIESELBE Funktion wie der
    Detektor-Lauf). None, wenn der Zustand kein Profil hat (zu wenig Samples) → dann
    ist keine ehrliche Korridor-Aussage möglich. EINE Quelle für das Trend-Band-Overlay
    (`reads.trend.expand_profile_band`) UND die Datenpunkt-Status-Ableitung
    (`reads.datapoint_status`) — nie zweimal getrennt berechnet.
    """
    entry = state_medians.get(str(state_key_for(moment)))
    if entry is None:
        return None
    median_value = float(entry["median"])
    half = effect_size_k * noise_sigma
    return (median_value - half, median_value, median_value + half)


@dataclass
class RollingResidualBaseline:
    """Gleitender Median je Betriebszustand als Deseasonalisierungs-Baseline.

    `observe(value, state_key)` liefert das Residuum gegen den Median der ZUVOR im
    selben Zustand gesehenen Werte und pflegt den Wert anschließend in das Fenster
    dieses Zustands ein. Solange ein Zustand noch keinen Wert hat, ist das Residuum
    0 (kein Profil -> kein Drift-Signal vertrauen).
    """

    window: int = BASELINE_WINDOW
    _by_state: dict[Hashable, deque[float]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._by_state = {}

    def _window_for(self, state_key: Hashable) -> deque[float]:
        dq = self._by_state.get(state_key)
        if dq is None:
            dq = deque(maxlen=self.window)
            self._by_state[state_key] = dq
        return dq

    def current_median(self, state_key: Hashable = None) -> float | None:
        """Median des Fensters eines Zustands, oder None bei leerem Fenster."""
        dq = self._by_state.get(state_key)
        if not dq:
            return None
        return median(dq)

    def observe(self, value: float, state_key: Hashable = None) -> float:
        """Residuum gegen den Zustands-Median ZUVOR; danach den Wert einpflegen.

        Reihenfolge ist bewusst: Das Residuum misst die Abweichung gegen das im
        selben Zustand bis dahin etablierte Profil — der aktuelle Wert verschiebt
        das Profil erst für die nachfolgenden Samples.
        """
        dq = self._window_for(state_key)
        reference = median(dq) if dq else None
        residual = 0.0 if reference is None else value - reference
        dq.append(value)
        return residual

    def state_profiles(self) -> dict[Hashable, tuple[float, int]]:
        """Je Betriebszustand `(median, sample_count)` — die Profil-Basis der Persistenz.

        Nur Zustände mit mindestens einem Wert; leere Fenster fehlen (ehrlich leer,
        nicht geraten). Der Median ist exakt der, gegen den `observe` das nächste
        Residuum bildet — die echte Detektor-Bewertungsbasis je Zustand.
        """
        return {
            state_key: (median(window), len(window))
            for state_key, window in self._by_state.items()
            if window
        }

    @property
    def count(self) -> int:
        """Gesamtanzahl der Werte über alle Zustands-Fenster."""
        return sum(len(dq) for dq in self._by_state.values())
