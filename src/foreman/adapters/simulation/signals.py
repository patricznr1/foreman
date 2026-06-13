# ============================================================
#  FOREMAN — adapters/simulation/signals.py
#  Zweck: Signal-Generatoren des Simulations-Adapters (F3): Baseline +
#         Schicht-Saisonalität + Gauss-Rauschen, dazu injizierbare Drift
#         (step | ramp | variance) ab einem bekannten t* sowie ein optionales
#         Quality-Flag (good/bad/missing).
#  Architektur-Einordnung: Datenakquise (Schicht 2), Simulations-Adapter.
#  Verbindliche Referenz: docs/research/drift-erkennung-verfahren.md §3
#         (State-Gating/Saisonalität) und §7 (synthetische Drift bei bekanntem t*).
#  Design: reine, deterministisch seedbare Funktionen ohne YAML-Wissen — der
#         Adapter übersetzt das Szenario in diese Parameter. So bleibt die
#         Drift-/Saison-/Rausch-Logik isoliert testbar (gegen bekannte Wahrheit).
# ============================================================
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

# OPC-UA-nahe Quality-Codes (smallint). None = nicht bewertet (Default, schlank).
QUALITY_GOOD = 192  # 0xC0 — Good
QUALITY_BAD = 0  # 0x00 — Bad
# Rauschanteil im Stillstand (Ruhewert ist ruhiger als der Lauf).
IDLE_NOISE_FRACTION = 0.3

DriftKind = Literal["step", "ramp", "variance"]
WeekendMode = Literal["idle", "reduced"]


@dataclass(frozen=True)
class DriftSpec:
    """Injizierte Drift ab t* (in Sekunden seit Szenario-Start).

    - `step`:     abrupter Mittelwertsprung um `target_delta` ab `start_s`.
    - `ramp`:     linearer (oder progressiver) Anstieg von 0 auf `target_delta`
                  über [`start_s`, `end_s`] — Verschleiß-Analogon.
    - `variance`: Streuungs-Erhöhung (noise_std * `std_multiplier`) ab `start_s`,
                  ohne Mittelwertshift.
    """

    kind: DriftKind
    start_s: float
    end_s: float | None = None
    target_delta: float = 0.0
    std_multiplier: float = 1.0
    progressive: bool = False


def drift_offset(spec: DriftSpec | None, elapsed_s: float) -> float:
    """Additiver Mittelwert-Offset zum Zeitpunkt `elapsed_s` (step/ramp; variance → 0)."""
    if spec is None or spec.kind == "variance" or elapsed_s < spec.start_s:
        return 0.0
    if spec.kind == "step":
        return spec.target_delta
    # ramp: linear (oder progressiv) zwischen start_s und end_s, danach Plateau.
    end_s = spec.end_s if spec.end_s is not None else spec.start_s
    if end_s <= spec.start_s or elapsed_s >= end_s:
        return spec.target_delta
    frac = (elapsed_s - spec.start_s) / (end_s - spec.start_s)
    if spec.progressive:
        frac = frac * frac  # beschleunigt gegen Ende (VB-Knick)
    return frac * spec.target_delta


def variance_factor(spec: DriftSpec | None, elapsed_s: float) -> float:
    """Multiplikator auf noise_std zum Zeitpunkt `elapsed_s` (nur für `variance`)."""
    if spec is None or spec.kind != "variance" or elapsed_s < spec.start_s:
        return 1.0
    return spec.std_multiplier


@dataclass(frozen=True)
class ShiftWindow:
    """Eine Schicht als Minuten-ab-Mitternacht-Fenster mit Lastfaktor."""

    name: str
    start_min: int
    end_min: int
    load_factor: float

    def contains(self, minute_of_day: int) -> bool:
        """True, wenn `minute_of_day` in dieses (ggf. über Mitternacht laufende) Fenster fällt."""
        if self.start_min <= self.end_min:
            return self.start_min <= minute_of_day < self.end_min
        # Nachtschicht ueber Mitternacht (z. B. 22:00-06:00)
        return minute_of_day >= self.start_min or minute_of_day < self.end_min


@dataclass(frozen=True)
class SeasonalitySpec:
    """Schicht-/Wochenend-Saisonalität — der Reasoner muss sie herausrechnen (§3)."""

    shifts: tuple[ShiftWindow, ...]
    weekend: WeekendMode = "idle"
    weekend_load_factor: float = 0.6


def _active_shift(spec: SeasonalitySpec, local_dt: datetime) -> ShiftWindow | None:
    minute_of_day = local_dt.hour * 60 + local_dt.minute
    for shift in spec.shifts:
        if shift.contains(minute_of_day):
            return shift
    return None


def _is_weekend(local_dt: datetime) -> bool:
    return local_dt.weekday() >= 5  # 5 = Samstag, 6 = Sonntag


def machine_running(spec: SeasonalitySpec, local_dt: datetime) -> bool:
    """Läuft die Maschine zu diesem (lokalen) Zeitpunkt? — Basis fürs State-Gating."""
    if _is_weekend(local_dt):
        return spec.weekend == "reduced"
    return _active_shift(spec, local_dt) is not None


def current_load_factor(spec: SeasonalitySpec, local_dt: datetime) -> float:
    """Lastfaktor zum (lokalen) Zeitpunkt (1.0, wenn Maschine steht)."""
    if _is_weekend(local_dt):
        return spec.weekend_load_factor if spec.weekend == "reduced" else 1.0
    shift = _active_shift(spec, local_dt)
    return shift.load_factor if shift is not None else 1.0


def machine_state_value(spec: SeasonalitySpec, local_dt: datetime) -> float:
    """Digitales Lauf-/Stillstand-Signal (1.0/0.0) für das State-Gating."""
    return 1.0 if machine_running(spec, local_dt) else 0.0


@dataclass(frozen=True)
class SignalProfile:
    """Analog-Signal-Profil: Baseline-Mittel, Rauschen, Ruhewert, Gating, Drift."""

    mean: float
    noise_std: float
    idle_value: float = 0.0
    gated: bool = True
    drift: DriftSpec | None = None


def sample_value(
    profile: SignalProfile,
    seasonality: SeasonalitySpec,
    local_dt: datetime,
    elapsed_s: float,
    rng: random.Random,
) -> float:
    """Ein analoger Messwert: Baseline*Last + Drift-Offset + Gauss-Rauschen.

    Im Stillstand (gated und Maschine steht) fällt das Signal auf seinen
    Ruhewert mit reduziertem Rauschen. Drift manifestiert sich nur im Lauf
    (ein verschlissenes Lager schwingt nur, wenn es dreht). Physischer Boden
    bei 0 (alle simulierten Größen sind nicht-negativ).
    """
    running = machine_running(seasonality, local_dt)
    if profile.gated and not running:
        idle = profile.idle_value + rng.gauss(0.0, profile.noise_std * IDLE_NOISE_FRACTION)
        return max(idle, 0.0)
    load = current_load_factor(seasonality, local_dt) if running else 1.0
    base = profile.mean * load
    offset = drift_offset(profile.drift, elapsed_s)
    std = profile.noise_std * variance_factor(profile.drift, elapsed_s)
    return max(base + offset + rng.gauss(0.0, std), 0.0)


@dataclass(frozen=True)
class QualitySpec:
    """Optionales Quality-Verhalten: Wahrscheinlichkeit für schlechte/fehlende Werte."""

    bad_probability: float = 0.0
    missing_probability: float = 0.0


def sample_quality(spec: QualitySpec | None, rng: random.Random) -> int | None | Literal["missing"]:
    """Liefert ein Quality-Flag für einen Messwert.

    - Kein QualitySpec → None (nicht bewertet; schlanker Default).
    - QualitySpec aktiv → "missing" (Wert auslassen, NICHT als 0 schreiben),
      sonst QUALITY_BAD oder QUALITY_GOOD.
    """
    if spec is None:
        return None
    roll = rng.random()
    if roll < spec.missing_probability:
        return "missing"
    if roll < spec.missing_probability + spec.bad_probability:
        return QUALITY_BAD
    return QUALITY_GOOD
