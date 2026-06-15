# ============================================================
#  FOREMAN — reasoners/failure/features.py
#  Zweck: Reine, netzfreie Feature-Extraktion des Ausfallvorhersage-Reasoners
#         (F-PRED). Aus einem Vorlauf-Fenster VOR einem Bezugszeitpunkt baut sie
#         einen Feature-Vektor: readings_1m-Aggregate je Datenpunkt (Mittel/Std/
#         Min/Max/Range/RMS/Trend/RoC/Last), Drift-Output als Feature (Anzahl/
#         Stärke/Zeit-seit), Wartung (Zeit seit letzter Wartung) und Alarm-
#         Historie (Anzahl im Fenster).
#  Architektur-Einordnung: Reasoning-Schicht (F-PRED), reiner Kern. DB-Zugriff
#         ist INJIZIERT (alle Reihen/Events werden übergeben) — ohne Netz testbar.
#  Sicherheit/Datenschutz (§8): PII-frei. Features sind Zahlen, verschlüsselt über
#         technische Datenpunkt-NAMEN (= data_points.name, stabil Training↔
#         Inferenz) — keine Klartext-Identitäten, keine Werker-Freitexte.
#  KEIN ZEIT-LEAKAGE (verbindlich): Es fließen ausschließlich Daten mit
#         Zeitstempel < reference_time ein; Aggregate zusätzlich nur aus dem
#         Vorlauf-Fenster [reference_time - lookback, reference_time).
# ============================================================
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class BucketPoint:
    """Ein aggregierter Zeit-Bucket eines Datenpunkts (entspricht einer readings_1m-Zeile).

    `avg`/`min`/`max` spiegeln `avg_value`/`min_value`/`max_value` aus dem
    Continuous Aggregate (§5). Im Trainings-Pfad (dataset.py, 1 Reading je Bucket)
    gilt min == max == avg; in der Inferenz tragen sie die echte Bucket-Streuung.
    """

    bucket: datetime
    avg: float
    min: float
    max: float


@dataclass(frozen=True)
class DataPointSeries:
    """Die Bucket-Reihe EINES Datenpunkts, identifiziert über den stabilen Namen.

    `name` ist `data_points.name` (= Szenario-Datenpunkt-Name) — der einzige
    Schlüssel, der Training (Szenario) und Inferenz (DB) konsistent verbindet.
    """

    name: str
    measurement_type: str | None
    points: tuple[BucketPoint, ...]


@dataclass(frozen=True)
class DriftEvent:
    """Ein Drift-Output-Ereignis des F4-Reasoners (Drift-Output als Feature).

    Im Training aus `detect_drift_in_stream`, in der Inferenz aus den DRIFT-Alarmen
    + `semantic_events`-Payload — beide tragen Zeitpunkt + Effektstärke.
    """

    occurred_at: datetime
    effect_size: float


@dataclass(frozen=True)
class FeatureWindow:
    """Vollständiger, netzfreier Eingang der Feature-Extraktion (DB injiziert).

    Die Extraktion filtert STRIKT auf `< reference_time` (kein Leakage) und —
    für Aggregate/Drift/Alarme — auf das Vorlauf-Fenster
    [reference_time - lookback, reference_time). `maintenance_times` ist bewusst
    NICHT fenster-begrenzt (»Zeit seit letzter Wartung« ist kumulativ).
    """

    reference_time: datetime
    lookback: timedelta
    series: tuple[DataPointSeries, ...]
    drift_events: tuple[DriftEvent, ...]
    maintenance_times: tuple[datetime, ...]
    alarm_times: tuple[datetime, ...]


def _ols_slope(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Steigung der Ausgleichsgeraden (Least Squares). 0.0 bei entarteter x-Streuung."""
    n = len(xs)
    if n < 2:
        return 0.0
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    denom = sum((x - mean_x) ** 2 for x in xs)
    if denom == 0.0:
        return 0.0
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    return num / denom


def _series_features(
    name: str, points: Sequence[BucketPoint], reference_time: datetime
) -> dict[str, float]:
    """Aggregate über die avg-Reihe eines Datenpunkts (points zeitlich aufsteigend)."""
    avgs = [p.avg for p in points]
    n = len(avgs)
    mean = sum(avgs) / n
    variance = sum((a - mean) ** 2 for a in avgs) / n
    rms = math.sqrt(sum(a * a for a in avgs) / n)
    low = min(p.min for p in points)
    high = max(p.max for p in points)
    last = avgs[-1]
    first = avgs[0]
    # Stunden relativ zum Bezugszeitpunkt (negativ, da Vergangenheit) — Trend/RoC pro Stunde.
    hours = [(p.bucket - reference_time).total_seconds() / 3600.0 for p in points]
    span = hours[-1] - hours[0]
    roc = (last - first) / span if span > 0.0 else 0.0
    return {
        f"{name}__mean": mean,
        f"{name}__std": math.sqrt(variance),
        f"{name}__min": low,
        f"{name}__max": high,
        f"{name}__range": high - low,
        f"{name}__rms": rms,
        f"{name}__slope": _ols_slope(hours, avgs),
        f"{name}__last": last,
        f"{name}__last_minus_mean": last - mean,
        f"{name}__roc": roc,
        f"{name}__n": float(n),
    }


def _drift_features(
    events: Sequence[DriftEvent], window_start: datetime, reference_time: datetime
) -> dict[str, float]:
    """Drift-Output als Feature: Anzahl/Stärke/Zeit-seit im Vorlauf-Fenster."""
    in_window = [e for e in events if window_start <= e.occurred_at < reference_time]
    count = len(in_window)
    max_effect = max((e.effect_size for e in in_window), default=0.0)
    if in_window:
        last_at = max(e.occurred_at for e in in_window)
        hours_since = (reference_time - last_at).total_seconds() / 3600.0
    else:
        # Kein Drift im Fenster: NaN (LightGBM behandelt fehlende Werte nativ) —
        # ehrlicher als ein Sentinel, der »kein Drift« mit »Drift vor langer Zeit« vermengt.
        hours_since = math.nan
    return {
        "drift__count": float(count),
        "drift__max_effect": float(max_effect),
        "drift__hours_since_last": hours_since,
    }


def _maintenance_features(times: Sequence[datetime], reference_time: datetime) -> dict[str, float]:
    """»Zeit seit letzter Wartung« — kumulativ, NICHT fenster-begrenzt."""
    before = [t for t in times if t < reference_time]
    if before:
        hours_since = (reference_time - max(before)).total_seconds() / 3600.0
    else:
        hours_since = math.nan
    return {"maint__hours_since_last": hours_since}


def _alarm_features(
    times: Sequence[datetime], window_start: datetime, reference_time: datetime
) -> dict[str, float]:
    """Alarm-Historie: Anzahl der (Nicht-Drift-)Alarme im Vorlauf-Fenster."""
    count = sum(1 for t in times if window_start <= t < reference_time)
    return {"alarm__count": float(count)}


def extract_features(window: FeatureWindow) -> dict[str, float]:
    """Baut den Feature-Vektor aus dem Vorlauf-Fenster (rein, netzfrei, kein Leakage).

    `reference_time` wird auf die Minute gefloort, BEVOR gefiltert wird: ein
    readings_1m-Bucket trägt das Label seines Minuten-ANFANGS, aggregiert aber
    Roh-Readings über [bucket, bucket+1min). Ohne Floor würde der Bucket der
    laufenden Minute (bei sekundengenauer/now()-Referenz) durch das strikte
    `< reference_time` durchrutschen und Zukunftsdaten einschleusen. Der Floor
    schließt diesen unfertigen Grenz-Bucket aus und spiegelt zugleich exakt die
    minutenausgerichtete Bucket-Logik des Trainingspfads (dataset.py).
    """
    reference_time = window.reference_time.replace(second=0, microsecond=0)
    window_start = reference_time - window.lookback
    feats: dict[str, float] = {}
    for series in window.series:
        points = sorted(
            (p for p in series.points if window_start <= p.bucket < reference_time),
            key=lambda p: p.bucket,
        )
        if not points:
            # Datenpunkt ohne Werte im Fenster → keine Aggregate (Vectorizer füllt NaN).
            continue
        feats.update(_series_features(series.name, points, reference_time))
    feats.update(_drift_features(window.drift_events, window_start, reference_time))
    feats.update(_maintenance_features(window.maintenance_times, reference_time))
    feats.update(_alarm_features(window.alarm_times, window_start, reference_time))
    return feats


def to_vector(features: dict[str, float], feature_names: Sequence[str]) -> list[float]:
    """Vektorisiert einen Feature-Dict deterministisch gegen ein festes Schema.

    Im Schema fehlende Features → NaN (LightGBM-konform). So bleibt die
    Feature-Reihenfolge identisch zwischen Training (Artefakt-`feature_schema`)
    und Inferenz, auch wenn eine Maschine einen Datenpunkt nicht führt.
    """
    return [features.get(name, math.nan) for name in feature_names]
