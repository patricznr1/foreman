# ============================================================
#  FOREMAN — tests/reasoners/failure/test_features.py
#  Zweck: Pflicht-Test-Block der Feature-Extraktion (F-PRED, rein/netzfrei).
#  Prüft: readings_1m-Aggregate (Mittel/Std/Min/Max/Trend/RMS/RoC), Drift-/
#         Wartungs-/Alarm-Features, STRIKT kein Zeit-Leakage (Daten ab dem
#         Bezugszeitpunkt fließen nicht ein), Vorlauf-Fenster-Begrenzung,
#         PII-Freiheit, deterministische Vektorisierung.
#  Architektur-Einordnung: Quality Gate §10.3 (reine Funktion, ohne DB).
# ============================================================
from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta

import pytest

from foreman.reasoners.failure.features import (
    BucketPoint,
    DataPointSeries,
    DriftEvent,
    FeatureWindow,
    extract_features,
    to_vector,
)

_REF = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)
_LOOKBACK = timedelta(hours=72)


def _point(hours_before: float, avg: float, lo: float, hi: float) -> BucketPoint:
    return BucketPoint(bucket=_REF - timedelta(hours=hours_before), avg=avg, min=lo, max=hi)


def _series(name: str, points: list[BucketPoint], mt: str | None = "signal") -> DataPointSeries:
    return DataPointSeries(name=name, measurement_type=mt, points=tuple(points))


def _window(
    *,
    series: list[DataPointSeries] | None = None,
    drift_events: list[DriftEvent] | None = None,
    maintenance_times: list[datetime] | None = None,
    alarm_times: list[datetime] | None = None,
) -> FeatureWindow:
    return FeatureWindow(
        reference_time=_REF,
        lookback=_LOOKBACK,
        series=tuple(series or []),
        drift_events=tuple(drift_events or []),
        maintenance_times=tuple(maintenance_times or []),
        alarm_times=tuple(alarm_times or []),
    )


# --------------------------------------------------------------------------- #
#  Aggregate je Datenpunkt
# --------------------------------------------------------------------------- #
def test_aggregate_features_je_datenpunkt() -> None:
    # avg=[1,2,3] bei t = -2h,-1h,0.5h vor Ref (steigend), min/max je Bucket gesetzt.
    series = _series(
        "vib",
        [
            _point(2.0, avg=1.0, lo=0.5, hi=1.5),
            _point(1.0, avg=2.0, lo=1.5, hi=2.5),
            _point(0.5, avg=3.0, lo=2.5, hi=3.5),
        ],
    )
    feats = extract_features(_window(series=[series]))
    assert feats["vib__mean"] == pytest.approx(2.0)
    assert feats["vib__min"] == pytest.approx(0.5)
    assert feats["vib__max"] == pytest.approx(3.5)
    assert feats["vib__range"] == pytest.approx(3.0)
    assert feats["vib__last"] == pytest.approx(3.0)
    assert feats["vib__n"] == pytest.approx(3.0)
    assert feats["vib__std"] == pytest.approx(math.sqrt(2.0 / 3.0))
    assert feats["vib__rms"] == pytest.approx(math.sqrt(14.0 / 3.0))


def test_slope_positiv_bei_steigender_reihe() -> None:
    series = _series(
        "vib",
        [
            _point(3.0, avg=1.0, lo=1.0, hi=1.0),
            _point(2.0, avg=2.0, lo=2.0, hi=2.0),
            _point(1.0, avg=3.0, lo=3.0, hi=3.0),
        ],
    )
    feats = extract_features(_window(series=[series]))
    # +1.0 pro Stunde (avg steigt um 1 je Stunde).
    assert feats["vib__slope"] == pytest.approx(1.0)
    assert feats["vib__roc"] == pytest.approx(1.0)


# --------------------------------------------------------------------------- #
#  KEIN Zeit-Leakage — der Kern
# --------------------------------------------------------------------------- #
def test_kein_leakage_punkte_ab_bezugszeitpunkt_ignoriert() -> None:
    # Ein riesiger Spike GENAU am und NACH dem Bezugszeitpunkt darf nichts ändern.
    series = _series(
        "vib",
        [
            _point(2.0, avg=1.0, lo=1.0, hi=1.0),
            _point(1.0, avg=2.0, lo=2.0, hi=2.0),
            _point(0.0, avg=999.0, lo=999.0, hi=999.0),  # == Ref → ausgeschlossen
            _point(-1.0, avg=999.0, lo=999.0, hi=999.0),  # nach Ref → ausgeschlossen
        ],
    )
    feats = extract_features(_window(series=[series]))
    assert feats["vib__max"] == pytest.approx(2.0)
    assert feats["vib__mean"] == pytest.approx(1.5)
    assert feats["vib__n"] == pytest.approx(2.0)


def test_kein_leakage_drift_ab_bezugszeitpunkt_ignoriert() -> None:
    drift = [
        DriftEvent(occurred_at=_REF - timedelta(hours=10), effect_size=3.0),
        DriftEvent(occurred_at=_REF + timedelta(hours=1), effect_size=9.0),  # nach Ref
    ]
    feats = extract_features(_window(drift_events=drift))
    assert feats["drift__count"] == pytest.approx(1.0)
    assert feats["drift__max_effect"] == pytest.approx(3.0)


def test_kein_leakage_bei_nicht_minutenausgerichteter_referenz() -> None:
    # reference_time mit Sekunden (z. B. now()): der Bucket der LAUFENDEN Minute
    # (Label = Minuten-Floor von ref) aggregiert Roh-Readings über [bucket, bucket+1min)
    # — inklusive Werten >= ref. Er darf NICHT einfließen (sonst Zukunfts-Leakage).
    ref = datetime(2026, 3, 20, 12, 0, 30, tzinfo=UTC)  # :30 Sekunden, nicht minutenausgerichtet
    series = DataPointSeries(
        name="vib",
        measurement_type="signal",
        points=(
            BucketPoint(
                bucket=datetime(2026, 3, 20, 11, 59, tzinfo=UTC), avg=1.0, min=1.0, max=1.0
            ),
            # Grenz-Bucket der laufenden Minute (Label 12:00:00) — würde Werte bis 12:00:59 tragen:
            BucketPoint(
                bucket=datetime(2026, 3, 20, 12, 0, tzinfo=UTC), avg=999.0, min=999.0, max=999.0
            ),
        ),
    )
    window = FeatureWindow(
        reference_time=ref,
        lookback=timedelta(hours=72),
        series=(series,),
        drift_events=(),
        maintenance_times=(),
        alarm_times=(),
    )
    feats = extract_features(window)
    assert feats["vib__max"] == pytest.approx(1.0)  # 999 (Grenz-Bucket) ausgeschlossen
    assert feats["vib__n"] == pytest.approx(1.0)


def test_vorlauf_fenster_schliesst_alte_punkte_aus() -> None:
    # Punkt älter als lookback (72h) fällt raus.
    series = _series(
        "vib",
        [
            _point(100.0, avg=50.0, lo=50.0, hi=50.0),  # > 72h vor Ref → raus
            _point(10.0, avg=2.0, lo=2.0, hi=2.0),
            _point(5.0, avg=4.0, lo=4.0, hi=4.0),
        ],
    )
    feats = extract_features(_window(series=[series]))
    assert feats["vib__n"] == pytest.approx(2.0)
    assert feats["vib__mean"] == pytest.approx(3.0)


# --------------------------------------------------------------------------- #
#  Drift-/Wartungs-/Alarm-Features
# --------------------------------------------------------------------------- #
def test_drift_features_ohne_events() -> None:
    feats = extract_features(_window())
    assert feats["drift__count"] == pytest.approx(0.0)
    assert feats["drift__max_effect"] == pytest.approx(0.0)
    assert math.isnan(feats["drift__hours_since_last"])


def test_drift_hours_since_last() -> None:
    drift = [DriftEvent(occurred_at=_REF - timedelta(hours=6), effect_size=2.0)]
    feats = extract_features(_window(drift_events=drift))
    assert feats["drift__hours_since_last"] == pytest.approx(6.0)


def test_maintenance_hours_since_last_auch_vor_dem_fenster() -> None:
    # Wartung VOR dem Vorlauf-Fenster zählt: "Zeit seit letzter Wartung" ist kumulativ.
    feats = extract_features(_window(maintenance_times=[_REF - timedelta(hours=200)]))
    assert feats["maint__hours_since_last"] == pytest.approx(200.0)


def test_maintenance_ohne_eintrag_ist_nan() -> None:
    feats = extract_features(_window())
    assert math.isnan(feats["maint__hours_since_last"])


def test_alarm_count_nur_im_fenster_und_vor_ref() -> None:
    alarms = [
        _REF - timedelta(hours=100),  # vor dem Fenster → raus
        _REF - timedelta(hours=10),
        _REF - timedelta(hours=2),
        _REF + timedelta(hours=1),  # nach Ref → raus
    ]
    feats = extract_features(_window(alarm_times=alarms))
    assert feats["alarm__count"] == pytest.approx(2.0)


# --------------------------------------------------------------------------- #
#  PII-Freiheit + Vektorisierung
# --------------------------------------------------------------------------- #
def test_features_sind_rein_numerisch_und_pii_frei() -> None:
    series = _series("vibration_rms_velocity_spindle_bearing", [_point(1.0, 2.0, 2.0, 2.0)])
    feats = extract_features(_window(series=[series]))
    # Alle Werte float, alle Keys technische Tags (Datenpunkt-Name + Stat) — kein Klartext-Bezug.
    assert all(isinstance(v, float) for v in feats.values())
    assert all(isinstance(k, str) for k in feats)
    assert any(k.startswith("vibration_rms_velocity_spindle_bearing__") for k in feats)


def test_to_vector_ordnet_und_fuellt_fehlende_mit_nan() -> None:
    feats = {"a__mean": 1.0, "b__mean": 2.0}
    vec = to_vector(feats, ["b__mean", "a__mean", "c__mean"])
    assert vec[0] == pytest.approx(2.0)
    assert vec[1] == pytest.approx(1.0)
    assert math.isnan(vec[2])


def test_leere_reihe_erzeugt_keine_aggregatfeatures() -> None:
    # Datenpunkt ohne Punkte im Fenster: keine vib__*-Aggregate (Vectorizer füllt NaN).
    series = _series("vib", [_point(500.0, 9.0, 9.0, 9.0)])  # weit vor dem Fenster
    feats = extract_features(_window(series=[series]))
    assert not any(k.startswith("vib__") for k in feats)
