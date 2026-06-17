// ============================================================
//  FOREMAN Frontend — lib/machine/trend-series.ts
//  Zweck: Transport-agnostische Trend-Logik der Maschinen-Detail-Sicht (Sektion B).
//         (1) Verschmilzt den stabilen historischen Pull (`/machines/{id}/trend`) mit
//             dem Live-1h-Fenster (WS-Thema `trend:{data_point_id}`, das bei jedem
//             Reading das GANZE Fenster neu pusht) auf dem `bucket`-Schlüssel — der
//             Rand atmet, ohne dass ältere Punkte oder die Achse springen.
//         (2) Leitet aus dem Normalband die Drift-Segmente ab (Differenzfläche,
//             Akzent — nicht Alarm-Rot; Studie §4B/§5.5).
//  Architektur-Einordnung: View-State (Schicht 2, rein, ohne UI/Transport testbar).
//  Quelle: GROUND_TRUTH §20.3/§20.5, realtime/ws.py (Live = voller Snapshot).
// ============================================================
import type { MachineTrendOut, TrendPointOut } from "@/lib/api/contracts";

import type { DriftDirection, DriftSegment, TrendSample, TrendSeries } from "./types";

/** Rohpunkte zu Samples (Bucket einmal zu Epoche geparst), aufsteigend nach Zeit. */
export function toTrendSamples(points: TrendPointOut[]): TrendSample[] {
  return points
    .map((p) => ({
      bucket: p.bucket,
      t: Date.parse(p.bucket),
      avg: p.avg,
      min: p.min,
      max: p.max,
      last: p.last,
    }))
    .sort((a, b) => a.t - b.t);
}

/**
 * Verschmilzt historisches Fenster + Live-Fenster zu EINER Reihe. Der Merge läuft
 * über eine Bucket-Map (historisch zuerst, Live überschreibt überlappende Buckets —
 * der Live-Snapshot ist frischer), danach aufsteigend sortiert. So gewinnt am Rand
 * der Live-Wert, ältere Punkte bleiben stabil, kein Bucket doppelt → kein Sprung.
 * Metadaten kommen aus dem Live-Fenster, wenn vorhanden (frischer), sonst historisch.
 */
export function mergeTrendSeries(
  historical: MachineTrendOut | null,
  live: MachineTrendOut | null,
): TrendSeries | null {
  const meta = live ?? historical;
  if (meta === null) {
    return null;
  }

  const byBucket = new Map<string, TrendSample>();
  if (historical !== null) {
    for (const sample of toTrendSamples(historical.points)) {
      byBucket.set(sample.bucket, sample);
    }
  }
  if (live !== null) {
    for (const sample of toTrendSamples(live.points)) {
      byBucket.set(sample.bucket, sample);
    }
  }
  const samples = [...byBucket.values()].sort((a, b) => a.t - b.t);

  return {
    dataPointId: meta.data_point_id,
    dataPointName: meta.data_point_name,
    unit: meta.unit,
    measurementType: meta.measurement_type,
    normalMin: meta.normal_min,
    normalMax: meta.normal_max,
    // Graceful: das F4-Eigenprofil ist Backend-seitig reserviert/null — wir tragen
    // null durch und erfinden keinen Strich (Studie §4B, GROUND_TRUTH §20.5).
    profileBand: null,
    samples,
    truncated: (historical?.truncated ?? false) || (live?.truncated ?? false),
  };
}

/**
 * Leitet die zusammenhängenden Abschnitte ab, in denen der Trend (Mittelwert) das
 * statische Normalband verlässt. Ohne Normalband (`normalMin`/`normalMax` beide
 * null) gibt es keine Drift-Aussage → leere Liste (kein erfundenes Band).
 */
export function deriveDriftSegments(series: TrendSeries): DriftSegment[] {
  const { normalMin, normalMax, samples } = series;
  if (normalMin === null && normalMax === null) {
    return [];
  }

  const classify = (avg: number): DriftDirection | null => {
    if (normalMax !== null && avg > normalMax) {
      return "over";
    }
    if (normalMin !== null && avg < normalMin) {
      return "under";
    }
    return null;
  };

  const segments: DriftSegment[] = [];
  let run: { direction: DriftDirection; samples: TrendSample[] } | null = null;
  const flush = (): void => {
    if (run !== null) {
      const first = run.samples[0]!;
      const last = run.samples[run.samples.length - 1]!;
      segments.push({ direction: run.direction, fromT: first.t, toT: last.t, samples: run.samples });
      run = null;
    }
  };

  for (const sample of samples) {
    const direction = classify(sample.avg);
    if (direction === null) {
      flush();
      continue;
    }
    if (run !== null && run.direction === direction) {
      run.samples.push(sample);
    } else {
      flush();
      run = { direction, samples: [sample] };
    }
  }
  flush();
  return segments;
}
