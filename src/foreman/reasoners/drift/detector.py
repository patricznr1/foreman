# ============================================================
#  FOREMAN — reasoners/drift/detector.py
#  Zweck: Drift-Detektor — ADWIN je data_point auf einem state-gated,
#         deseasonalisierten Residuumstrom (Research §6.2, Baustein 3).
#  Architektur-Einordnung: Reasoning-Schicht (F4). Library: river (BSD-3).
#         Substrat bleibt außen vor — dieser Code rechnet ausschließlich auf
#         FOREMANs eigenen readings. ADWIN-Updates sind CPU-billig und blockieren
#         den Event-Loop nicht; der Zustand pro data_point ist winzig (tausende
#         parallel ok).
#  Referenz: docs/research/drift-erkennung-verfahren.md §6.1 (Parameter) / §6.2 (Code).
# ============================================================
from __future__ import annotations

from dataclasses import dataclass, field
from statistics import median, pstdev
from typing import Final

from river import drift

from foreman.reasoners.drift.baseline import RollingResidualBaseline

# Startkalibrierung (Research §6.1).
ADWIN_DELTA: Final = 0.002          # river-Default; -> 0.001 bei zu vielen Fehlalarmen
WARMUP_MIN_SAMPLES: Final = 100     # vor diesem Stand kein Drift-Signal vertrauen


def _robust_sigma(residuals: list[float]) -> float:
    """Robuste Streuungs-Schätzung (MAD x 1.4826) der Warm-up-Residuen.

    Robust gegen die wenigen Null-Residuen der Anlaufphase (Baseline noch leer);
    pstdev als Fallback, falls die MAD entartet (z. B. > 50 % identische Werte).
    """
    if len(residuals) < 2:
        return 0.0
    med = median(residuals)
    mad = median([abs(r - med) for r in residuals])
    sigma = 1.4826 * mad
    if sigma > 0.0:
        return sigma
    fallback = pstdev(residuals)
    return fallback if fallback > 0.0 else 0.0


@dataclass
class DataPointDriftState:
    """Detektor-Zustand für EINEN data_point. Bewusst winzig -> tausende parallel ok.

    Kombiniert die zustandsspezifische Residuum-Baseline (Deseasonalisierung)
    mit einem ADWIN-Detektor auf dem Residuumstrom.
    """

    adwin: drift.ADWIN = field(default_factory=lambda: drift.ADWIN(delta=ADWIN_DELTA))
    baseline: RollingResidualBaseline = field(default_factory=RollingResidualBaseline)
    seen: int = 0
    # Letztes Residuum (Wert minus Profil-Median).
    last_residual: float = 0.0
    # Während Warm-up gesammelte Residuen -> robuste Rausch-Streuung (eingefroren).
    _warmup_residuals: list[float] = field(default_factory=list, repr=False)
    _sigma: float | None = field(default=None, repr=False)

    def update(
        self, value: float, *, in_steady_state: bool, state_key: object = None
    ) -> bool:
        """Verarbeitet einen (aggregierten) Messwert. Gibt True NUR bei echter Drift.

        `in_steady_state` kommt aus production_runs + digitalen data_points. Fällt
        es weg (Rüsten/Stillstand/Anlauf), wird der Detektor NICHT gefüttert — kein
        Fehlalarm, kein Verbrauch von Warm-up/Baseline. `state_key` wählt das
        zustandsspezifische Baseline-Fenster (Deseasonalisierung, Research §3).
        Während der ersten `WARMUP_MIN_SAMPLES` Residuum-Samples wird keinem Signal
        vertraut (Profil noch nicht etabliert) und die Rausch-Streuung geschätzt.
        """
        if not in_steady_state:
            return False
        residual = self.baseline.observe(value, state_key)
        self.last_residual = residual
        self.seen += 1
        self.adwin.update(residual)
        if self.seen <= WARMUP_MIN_SAMPLES:
            self._warmup_residuals.append(residual)
            if self.seen == WARMUP_MIN_SAMPLES:
                self._sigma = _robust_sigma(self._warmup_residuals)
                self._warmup_residuals = []  # Speicher freigeben
            return False
        return bool(self.adwin.drift_detected)

    @property
    def effect_size(self) -> float:
        """Standardisierte Effektgröße: |Residuum| / Rausch-Streuung (z-Score).

        Messgrößen-invariant — eine einheitliche Relevanz-Schwelle greift über
        mm/s, Nm, °C hinweg. 0, solange die Streuung noch nicht etabliert ist.
        """
        if self._sigma is None or self._sigma <= 0.0:
            return 0.0
        return abs(self.last_residual) / self._sigma


class DriftReasoner:
    """Hält je data_point einen Detektor. Stateful, in-memory, prozesslokal.

    Multi-Worker-Strategie (Pinning / Rehydrieren aus readings_1m) ist ein
    offener Punkt (Research §8) — für den MVP (ein Worker) unkritisch.
    """

    def __init__(self) -> None:
        self._states: dict[int, DataPointDriftState] = {}

    def observe(
        self, data_point_id: int, value: float, *, in_steady_state: bool, state_key: object = None
    ) -> bool:
        """Verarbeitet einen Messwert für `data_point_id` und meldet Drift (bool)."""
        state = self._states.setdefault(data_point_id, DataPointDriftState())
        return state.update(value, in_steady_state=in_steady_state, state_key=state_key)

    def state_for(self, data_point_id: int) -> DataPointDriftState | None:
        """Detektor-Zustand eines data_point (oder None, falls noch nie gesehen)."""
        return self._states.get(data_point_id)
