// ============================================================
//  FOREMAN Frontend — lib/machine/trend-series.ts
//  Zweck: Transport-agnostische Trend-Logik der Maschinen-Detail-Sicht (Sektion B).
//         (1) Verschmilzt den stabilen historischen Pull (`/machines/{id}/trend`) mit
//             dem Live-1h-Fenster (WS-Thema `trend:{data_point_id}`, das bei jedem
//             Reading das GANZE Fenster neu pusht) auf dem `bucket`-Schlüssel — der
//             Rand atmet, ohne dass ältere Punkte oder die Achse springen.
//         (2) Leitet aus dem Normalband die Drift-Segmente ab (Differenzfläche,
//             Akzent — nicht Alarm-Rot; Studie §4B/§5.5).
//         (3) Bereitet die Reihe für einen stufenlos zoombaren Ausschnitt auf:
//             `visibleSlice` (Zuschnitt + Nachbarpunkt), `splitAtGaps` (die Linie
//             endet dort, wo die Messung endet) und `decimate` (Verdichtung, die
//             die Extreme je Spalte behält). Reihenfolge beim Zeichnen zwingend:
//             visibleSlice → splitAtGaps → decimate je Segment.
//  Architektur-Einordnung: View-State (Schicht 2, rein, ohne UI/Transport testbar).
//  Quelle: GROUND_TRUTH §20.3/§20.5, realtime/ws.py (Live = voller Snapshot).
// ============================================================
import type { MachineTrendOut, TrendPointOut } from "@/lib/api/contracts";

import { BUCKET_MS } from "./time-window";

import type {
  DriftDirection,
  DriftSegment,
  ProfileBand,
  ProfileBandPoint,
  TrendSample,
  TrendSeries,
} from "./types";

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
 * Verschmilzt das F4-Eigenprofil-Band beider Fenster auf dem t-Schlüssel (Live gewinnt
 * am überlappenden Rand, wie bei den Samples). Metadaten (Stand, k) aus dem frischeren
 * Fenster. Kein Band in beiden Fenstern → null (graceful, kein erfundener Strich).
 */
function mergeProfileBands(
  historical: MachineTrendOut | null,
  live: MachineTrendOut | null,
  meta: MachineTrendOut,
): ProfileBand | null {
  const source = meta.profile_band ?? live?.profile_band ?? historical?.profile_band ?? null;
  if (source === null) {
    return null;
  }
  const byT = new Map<number, ProfileBandPoint>();
  for (const raw of [historical?.profile_band ?? null, live?.profile_band ?? null]) {
    if (raw === null) {
      continue;
    }
    for (const bandPoint of raw.points) {
      const t = Date.parse(bandPoint.bucket);
      byT.set(t, { t, lower: bandPoint.lower, mid: bandPoint.mid, upper: bandPoint.upper });
    }
  }
  const points = [...byT.values()].sort((a, b) => a.t - b.t);
  if (points.length === 0) {
    return null;
  }
  return {
    computedAt: Date.parse(source.computed_at),
    effectSizeK: source.effect_size_k,
    points,
  };
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
    // F4-Eigenprofil-Korridor (echte Detektor-Basis), über beide Fenster verschmolzen;
    // null, wenn kein/zu junges Profil vorliegt (graceful, Studie §4B, GROUND_TRUTH §20.5).
    profileBand: mergeProfileBands(historical, live, meta),
    samples,
    truncated: (historical?.truncated ?? false) || (live?.truncated ?? false),
  };
}

/**
 * Größter Abstand zweier Buckets, der noch als lückenlos gilt: anderthalb Bucket-
 * Breiten. Damit ist genau ein fehlender Minuten-Bucket (Abstand: zwei Bucket-Breiten)
 * bereits eine Lücke, während Jitter unterhalb einer halben Bucket-Breite keine ist. Aus
 * `BUCKET_MS` abgeleitet — eine zweite Zahl, die dasselbe meint, liefe auseinander,
 * sobald jemand die Bucket-Breite anfasst.
 */
export const DEFAULT_MAX_GAP_MS = 1.5 * BUCKET_MS;

/**
 * Schneidet die Reihe auf den sichtbaren Ausschnitt zu und nimmt je EINEN Punkt
 * außerhalb beider Ränder mit. Der Nachbarpunkt ist der Grund, warum die Linie den
 * Plotrand erreicht: ohne ihn endet sie sichtbar davor, und der Zwischenraum liest
 * sich als fehlender Messwert — eine erfundene Lücke, ausgerechnet in einer Ansicht,
 * die echte Lücken ausdrücklich als Aussage markiert. Am Reihenanfang bzw. -ende gibt
 * es keinen Nachbarn; dort wird auch keiner erfunden.
 *
 * Ränder gehören zum Ausschnitt: `t === startMs` und `t === endMs` liegen drin.
 * Erwartet aufsteigend sortierte Samples (Vertrag von `TrendSeries`).
 */
export function visibleSlice(
  samples: readonly TrendSample[],
  startMs: number,
  endMs: number,
): TrendSample[] {
  // Erster Punkt IM Ausschnitt; −1 heißt: alles liegt links davon.
  const firstInside = samples.findIndex((sample) => sample.t >= startMs);
  const from = firstInside === -1 ? Math.max(0, samples.length - 1) : Math.max(0, firstInside - 1);
  // Erster Punkt RECHTS vom Ausschnitt; −1 heißt: alles liegt links davon.
  const firstAfter = samples.findIndex((sample) => sample.t > endMs);
  const to = firstAfter === -1 ? samples.length : firstAfter + 1;
  return samples.slice(from, to);
}

/**
 * Zerlegt die Reihe an echten Löchern in mehrere zusammenhängende Züge. Getrennt wird
 * erst, wenn der Abstand zum Vorgänger `maxGapMs` ÜBERSCHREITET — genau auf der Grenze
 * bleibt der Zug zusammen. Der Zweck ist die Aussage der gezeichneten Linie: ein Zug
 * verbindet nur Messwerte, zwischen denen gemessen wurde. Eine durchgezogene Gerade
 * über ein Loch behauptet einen Verlauf, den niemand beobachtet hat — und der Zoom
 * macht genau diese Behauptung bildfüllend groß.
 */
export function splitAtGaps(samples: readonly TrendSample[], maxGapMs: number): TrendSample[][] {
  const segments: TrendSample[][] = [];
  let current: TrendSample[] = [];
  let previous: TrendSample | null = null;
  for (const sample of samples) {
    if (previous !== null && sample.t - previous.t > maxGapMs) {
      segments.push(current);
      current = [];
    }
    current.push(sample);
    previous = sample;
  }
  if (current.length > 0) {
    segments.push(current);
  }
  return segments;
}

/**
 * Verdichtet einen lückenlosen Zug auf höchstens `targetColumns` Spalten und behält je
 * Spalte den KLEINSTEN UND den GRÖSSTEN Punkt, ausgegeben in Zeitreihenfolge. Damit
 * überlebt ein einminütiger Ausschlag die Verdichtung mit seinem exakten Wert — und
 * genau wegen solcher Ausschläge sieht jemand auf dieses Diagramm.
 *
 * NIEMALS auf „jeden n-ten Punkt" umbauen. Das ist die naheliegende und billigere
 * Verdichtung, sie löscht aber lautlos genau die Spitzen, um die es geht: das Bild
 * wird glatter und niemand sieht, dass etwas fehlt. Der Test „ein einzelner Ausschlag
 * überlebt die Verdichtung mit exaktem Wert" fordert das ein und wird bei dieser
 * Mutation rot.
 *
 * Erhalten bleiben die Extreme je Spalte, nicht die Form innerhalb einer Spalte:
 * deckt eine Spalte 30 Buckets ab, ist die Reihenfolge der kleineren Schwankungen
 * darin verloren. Bei `samples.length <= targetColumns` bleibt die Reihe unverändert.
 */
export function decimate(samples: readonly TrendSample[], targetColumns: number): TrendSample[] {
  // Nichts zu verdichten — und `targetColumns <= 0` wäre eine Division durch null.
  if (targetColumns <= 0 || samples.length <= targetColumns) {
    return [...samples];
  }
  const kept: TrendSample[] = [];
  for (let column = 0; column < targetColumns; column += 1) {
    const from = Math.floor((column * samples.length) / targetColumns);
    const to = Math.floor(((column + 1) * samples.length) / targetColumns);
    const [head, ...rest] = samples.slice(from, to);
    if (head === undefined) {
      continue;
    }
    let lowest = head;
    let highest = head;
    for (const sample of rest) {
      if (sample.avg < lowest.avg) {
        lowest = sample;
      }
      if (sample.avg > highest.avg) {
        highest = sample;
      }
    }
    if (lowest === highest) {
      kept.push(lowest);
    } else if (lowest.t <= highest.t) {
      kept.push(lowest, highest);
    } else {
      kept.push(highest, lowest);
    }
  }
  return kept;
}

/**
 * Leitet die zusammenhängenden Abschnitte ab, in denen der Trend (Mittelwert) das
 * statische Normalband verlässt. Ohne Normalband (`normalMin`/`normalMax` beide
 * null) gibt es keine Drift-Aussage → leere Liste (kein erfundenes Band).
 *
 * Ein Lauf endet außerdem an einer Lücke: überschreitet der Abstand zum Vorgänger
 * `maxGapMs`, wird abgeschlossen und rechts davon neu begonnen. Die Differenzfläche
 * endet damit dort, wo die Messung endet — sie überspannt keine Zeit, für die kein
 * Messwert vorliegt. Driftflächen fallen dadurch kleiner aus und zerfallen in
 * mehrere Stücke; das ist die Aussage, nicht ein Verlust.
 */
export function deriveDriftSegments(
  series: TrendSeries,
  maxGapMs: number = DEFAULT_MAX_GAP_MS,
): DriftSegment[] {
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

  let previous: TrendSample | null = null;
  for (const sample of samples) {
    // Lücke: der laufende Abschnitt endet beim letzten Messwert, nicht erst beim
    // nächsten — dazwischen liegt keine Beobachtung, über die etwas zu sagen wäre.
    if (previous !== null && sample.t - previous.t > maxGapMs) {
      flush();
    }
    previous = sample;
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
