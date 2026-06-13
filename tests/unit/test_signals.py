# ============================================================
#  FOREMAN — tests/unit/test_signals.py
#  Zweck: Pflicht-Test-Block für die Signal-Generatoren (F3).
#  Prüft gegen bekannte Wahrheit: Drift-Injektion (step/ramp/variance) erzeugt
#  die erwartete Abweichung ab t*; Schicht-Saisonalität; Rauschen; Determinismus.
#  Architektur-Einordnung: Quality Gate §10.3 (Happy/Edge/Validierung).
# ============================================================
from __future__ import annotations

import random
import statistics
from datetime import UTC, datetime

import pytest

from foreman.adapters.simulation.signals import (
    QUALITY_BAD,
    QUALITY_GOOD,
    DriftSpec,
    QualitySpec,
    SeasonalitySpec,
    ShiftWindow,
    SignalProfile,
    current_load_factor,
    drift_offset,
    machine_running,
    machine_state_value,
    sample_quality,
    sample_value,
    variance_factor,
)

# Eine Maschine, die werktags rund um die Uhr in drei Schichten läuft.
_THREE_SHIFT = SeasonalitySpec(
    shifts=(
        ShiftWindow("frueh", 6 * 60, 14 * 60, 1.00),
        ShiftWindow("spaet", 14 * 60, 22 * 60, 1.20),
        ShiftWindow("nacht", 22 * 60, 6 * 60, 0.80),
    ),
    weekend="idle",
)

# Ein Werktag-Mittwoch, fixe Schicht-Zeitpunkte (UTC genügt — wir testen Logik).
_WED = datetime(2026, 3, 4, tzinfo=UTC)  # Mittwoch


def _frueh() -> datetime:
    return _WED.replace(hour=8)


def _ungated() -> SignalProfile:
    # Nicht gegated → Saison-Gating spielt keine Rolle (immer aktiv).
    return SignalProfile(mean=10.0, noise_std=1.0, gated=False)


# --------------------------------------------------------------------------- #
#  Drift-Offset (reine Funktion, gegen bekannte Wahrheit)
# --------------------------------------------------------------------------- #
def test_step_drift_springt_genau_ab_t_star() -> None:
    spec = DriftSpec(kind="step", start_s=100.0, target_delta=5.0)
    assert drift_offset(spec, 99.0) == 0.0
    assert drift_offset(spec, 100.0) == 5.0
    assert drift_offset(spec, 10_000.0) == 5.0


def test_ramp_drift_linear_zwischen_start_und_ende() -> None:
    spec = DriftSpec(kind="ramp", start_s=0.0, end_s=100.0, target_delta=10.0)
    assert drift_offset(spec, 0.0) == 0.0
    assert drift_offset(spec, 50.0) == pytest.approx(5.0)  # Mitte → halbe Magnitude
    assert drift_offset(spec, 100.0) == pytest.approx(10.0)
    assert drift_offset(spec, 200.0) == pytest.approx(10.0)  # Plateau danach


def test_ramp_progressive_liegt_unter_linear_in_der_mitte() -> None:
    linear = DriftSpec(kind="ramp", start_s=0.0, end_s=100.0, target_delta=10.0)
    progressive = DriftSpec(
        kind="ramp", start_s=0.0, end_s=100.0, target_delta=10.0, progressive=True
    )
    # progressiv (frac^2) ist in der Mitte kleiner und beschleunigt zum Ende.
    assert drift_offset(progressive, 50.0) < drift_offset(linear, 50.0)
    assert drift_offset(progressive, 50.0) == pytest.approx(2.5)  # 0.5^2 * 10


def test_variance_drift_erhoeht_nur_streuung_nicht_mittel() -> None:
    spec = DriftSpec(kind="variance", start_s=100.0, std_multiplier=4.0)
    assert drift_offset(spec, 200.0) == 0.0  # kein Mittelwert-Offset
    assert variance_factor(spec, 99.0) == 1.0
    assert variance_factor(spec, 100.0) == 4.0


# --------------------------------------------------------------------------- #
#  sample_value — Drift im erzeugten Signal nachweisbar (gegen bekannte Wahrheit)
# --------------------------------------------------------------------------- #
def test_ramp_drift_im_signal_ab_t_star_messbar() -> None:
    rng = random.Random(42)
    profile = SignalProfile(
        mean=1.8,
        noise_std=0.15,
        gated=False,
        drift=DriftSpec(kind="ramp", start_s=0.0, end_s=1000.0, target_delta=5.0),
    )
    # Vor t* (elapsed<0 nicht möglich) → bei elapsed=0 ~ baseline.
    before = [sample_value(profile, _THREE_SHIFT, _frueh(), 0.0, rng) for _ in range(400)]
    after = [
        sample_value(profile, _THREE_SHIFT, _frueh(), 2000.0, rng) for _ in range(400)
    ]
    assert statistics.mean(before) == pytest.approx(1.8, abs=0.1)
    # Nach end (Plateau) ~ baseline + target_delta = 6.8.
    assert statistics.mean(after) == pytest.approx(6.8, abs=0.1)


def test_variance_drift_im_signal_erhoeht_streuung() -> None:
    rng = random.Random(7)
    profile = SignalProfile(
        mean=8000.0,
        noise_std=8.0,
        gated=False,
        drift=DriftSpec(kind="variance", start_s=100.0, std_multiplier=4.0),
    )
    before = [sample_value(profile, _THREE_SHIFT, _frueh(), 0.0, rng) for _ in range(600)]
    after = [
        sample_value(profile, _THREE_SHIFT, _frueh(), 500.0, rng) for _ in range(600)
    ]
    # Mittel bleibt ~gleich, Streuung vervielfacht sich (~ Faktor 4).
    assert statistics.mean(after) == pytest.approx(8000.0, abs=5.0)
    assert statistics.pstdev(after) > 2.5 * statistics.pstdev(before)


def test_noise_streuung_entspricht_noise_std() -> None:
    rng = random.Random(1)
    profile = _ungated()
    values = [sample_value(profile, _THREE_SHIFT, _frueh(), 0.0, rng) for _ in range(1000)]
    assert statistics.pstdev(values) == pytest.approx(1.0, abs=0.15)


# --------------------------------------------------------------------------- #
#  Saisonalität + State-Gating
# --------------------------------------------------------------------------- #
def test_schicht_saisonalitaet_spaet_lastiger_als_frueh() -> None:
    rng = random.Random(3)
    profile = SignalProfile(mean=10.0, noise_std=0.5, gated=True)
    frueh = [
        sample_value(profile, _THREE_SHIFT, _WED.replace(hour=8), 0.0, rng)
        for _ in range(500)
    ]
    spaet = [
        sample_value(profile, _THREE_SHIFT, _WED.replace(hour=16), 0.0, rng)
        for _ in range(500)
    ]
    # Spätschicht load_factor 1.20 > Frühschicht 1.00.
    assert statistics.mean(spaet) > statistics.mean(frueh)
    assert statistics.mean(spaet) == pytest.approx(12.0, abs=0.2)


def test_gating_im_stillstand_faellt_auf_ruhewert() -> None:
    rng = random.Random(5)
    profile = SignalProfile(mean=12.0, noise_std=0.6, idle_value=0.0, gated=True)
    # Samstag → weekend idle → Maschine steht.
    saturday = datetime(2026, 3, 7, 10, tzinfo=UTC)
    assert not machine_running(_THREE_SHIFT, saturday)
    idle = [sample_value(profile, _THREE_SHIFT, saturday, 0.0, rng) for _ in range(300)]
    assert statistics.mean(idle) == pytest.approx(0.0, abs=0.2)


def test_machine_state_signal_eins_im_lauf_null_am_wochenende() -> None:
    weekday = datetime(2026, 3, 4, 8, tzinfo=UTC)  # Mi Frühschicht
    weekend = datetime(2026, 3, 7, 8, tzinfo=UTC)  # Sa
    night_gap = datetime(2026, 3, 4, 3, tzinfo=UTC)  # Mi 03:00 (in Nachtschicht)
    assert machine_state_value(_THREE_SHIFT, weekday) == 1.0
    assert machine_state_value(_THREE_SHIFT, weekend) == 0.0
    assert machine_state_value(_THREE_SHIFT, night_gap) == 1.0  # Nachtschicht läuft


def test_zwei_schicht_betrieb_steht_nachts() -> None:
    two_shift = SeasonalitySpec(
        shifts=(
            ShiftWindow("frueh", 6 * 60, 14 * 60, 1.0),
            ShiftWindow("spaet", 14 * 60, 22 * 60, 1.0),
        ),
        weekend="idle",
    )
    night = datetime(2026, 3, 4, 2, tzinfo=UTC)  # 02:00, keine Nachtschicht
    assert not machine_running(two_shift, night)
    assert current_load_factor(two_shift, night) == 1.0


def test_wochenende_reduced_laeuft_mit_reduzierter_last() -> None:
    spec = SeasonalitySpec(
        shifts=(ShiftWindow("frueh", 6 * 60, 22 * 60, 1.0),),
        weekend="reduced",
        weekend_load_factor=0.6,
    )
    saturday = datetime(2026, 3, 7, 12, tzinfo=UTC)
    assert machine_running(spec, saturday)
    assert current_load_factor(spec, saturday) == pytest.approx(0.6)


# --------------------------------------------------------------------------- #
#  Determinismus + Quality-Flag
# --------------------------------------------------------------------------- #
def test_gleicher_seed_erzeugt_identische_folge() -> None:
    profile = _ungated()
    # Persistenter RNG je Liste: ein in jeder Iteration neu geseedeter RNG würde
    # immer denselben Startwert ziehen — der Test prüfte dann keine echte Folge.
    rng_a = random.Random(99)
    rng_b = random.Random(99)
    a = [sample_value(profile, _THREE_SHIFT, _frueh(), 0.0, rng_a) for _ in range(50)]
    b = [sample_value(profile, _THREE_SHIFT, _frueh(), 0.0, rng_b) for _ in range(50)]
    assert a == b  # gleicher Seed → identische Folge (Determinismus)
    assert len(set(a)) > 1  # echte fortschreitende Folge, nicht 50-mal derselbe Wert


def test_quality_default_ist_none() -> None:
    assert sample_quality(None, random.Random(1)) is None


def test_quality_missing_und_bad_treten_auf() -> None:
    spec = QualitySpec(bad_probability=0.2, missing_probability=0.1)
    rng = random.Random(2)
    results = [sample_quality(spec, rng) for _ in range(2000)]
    assert results.count("missing") > 0
    assert results.count(QUALITY_BAD) > 0
    assert results.count(QUALITY_GOOD) > 0
    # Grobe Verteilungs-Plausibilität (kein scharfer Test wegen Zufall).
    assert 0.05 < results.count("missing") / len(results) < 0.16
