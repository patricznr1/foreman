// ============================================================
//  FOREMAN Frontend — lib/machine/trend-series.test.ts
//  Zweck: Sichert die transport-agnostische Trend-Logik — den sprungfreien Merge
//         von historischem Pull + Live-1h-Fenster (auf bucket-Schlüssel) und die
//         Drift-Segment-Ableitung (Über-/Unterschreitung des Normalbands).
// ============================================================
import { describe, expect, it } from "vitest";

import type { MachineTrendOut, TrendPointOut } from "@/lib/api/contracts";

import { deriveDriftSegments, mergeTrendSeries, toTrendSamples } from "./trend-series";

function point(bucket: string, avg: number, extra: Partial<TrendPointOut> = {}): TrendPointOut {
  return { bucket, avg, min: extra.min ?? avg, max: extra.max ?? avg, last: extra.last ?? avg };
}

function trend(points: TrendPointOut[], over: Partial<MachineTrendOut> = {}): MachineTrendOut {
  return {
    machine_id: 7,
    data_point_id: 42,
    data_point_name: "spindle_temp",
    unit: "°C",
    measurement_type: "temperature",
    normal_min: 10,
    normal_max: 20,
    points,
    truncated: false,
    profile_band: null,
    ...over,
  };
}

describe("toTrendSamples", () => {
  it("parst Buckets zu Epochen und sortiert aufsteigend", () => {
    const samples = toTrendSamples([
      point("2026-06-17T10:02:00Z", 2),
      point("2026-06-17T10:00:00Z", 1),
      point("2026-06-17T10:01:00Z", 3),
    ]);
    expect(samples.map((s) => s.avg)).toEqual([1, 3, 2]);
    expect(samples[0]?.t).toBe(Date.parse("2026-06-17T10:00:00Z"));
    expect(samples[0]?.t).toBeLessThan(samples[1]!.t);
  });
});

describe("mergeTrendSeries", () => {
  it("liefert null, wenn weder historisch noch live vorliegt", () => {
    expect(mergeTrendSeries(null, null)).toBeNull();
  });

  it("nutzt allein den historischen Pull, wenn kein Live-Fenster da ist", () => {
    const series = mergeTrendSeries(trend([point("2026-06-17T09:00:00Z", 12)]), null);
    expect(series?.samples).toHaveLength(1);
    expect(series?.dataPointId).toBe(42);
    expect(series?.normalMax).toBe(20);
  });

  it("nutzt allein das Live-Fenster, wenn der historische Pull fehlt", () => {
    const series = mergeTrendSeries(null, trend([point("2026-06-17T10:00:00Z", 15)]));
    expect(series?.samples).toHaveLength(1);
    expect(series?.samples[0]?.avg).toBe(15);
  });

  it("verschmilzt auf bucket-Schlüssel: Live überschreibt überlappende Buckets, ohne Sprung", () => {
    // Historisch: zwei Buckets. Live: deckt den jüngeren neu ab (frischerer Wert)
    // und hängt einen neuen Rand-Bucket an. Erwartung: ein durchgehender, aufsteigend
    // sortierter Strom OHNE Duplikat — der Live-Wert gewinnt für 10:00.
    const historical = trend([
      point("2026-06-17T09:59:00Z", 12),
      point("2026-06-17T10:00:00Z", 13),
    ]);
    const live = trend([
      point("2026-06-17T10:00:00Z", 99), // frischer Wert für denselben Bucket
      point("2026-06-17T10:01:00Z", 14), // neuer Rand
    ]);
    const series = mergeTrendSeries(historical, live);
    expect(series?.samples.map((s) => s.bucket)).toEqual([
      "2026-06-17T09:59:00Z",
      "2026-06-17T10:00:00Z",
      "2026-06-17T10:01:00Z",
    ]);
    // Live gewinnt für den überlappenden Bucket.
    expect(series?.samples.find((s) => s.bucket === "2026-06-17T10:00:00Z")?.avg).toBe(99);
  });

  it("bevorzugt die Metadaten des Live-Fensters (frischer), behält truncated", () => {
    const historical = trend([point("2026-06-17T09:00:00Z", 12)], { unit: "alt", truncated: true });
    const live = trend([point("2026-06-17T10:00:00Z", 15)], { unit: "°C", truncated: false });
    const series = mergeTrendSeries(historical, live);
    expect(series?.unit).toBe("°C");
    // truncated ist „irgendwo gekappt" — ODER der beiden Quellen.
    expect(series?.truncated).toBe(true);
  });

  it("trägt profileBand graceful als null, wenn kein Profil vorliegt", () => {
    const series = mergeTrendSeries(trend([point("2026-06-17T09:00:00Z", 12)]), null);
    expect(series?.profileBand).toBeNull();
  });

  it("mappt profile_band auf den zeitaufgelösten profileBand-Korridor", () => {
    const withBand = trend([point("2026-06-17T08:00:00Z", 10)], {
      profile_band: {
        computed_at: "2026-06-17T22:00:00Z",
        effect_size_k: 3.0,
        points: [{ bucket: "2026-06-17T08:00:00Z", lower: 7, mid: 10, upper: 13 }],
      },
    });
    const series = mergeTrendSeries(withBand, null);
    expect(series?.profileBand).not.toBeNull();
    expect(series?.profileBand?.effectSizeK).toBe(3.0);
    expect(series?.profileBand?.computedAt).toBe(Date.parse("2026-06-17T22:00:00Z"));
    expect(series?.profileBand?.points[0]).toEqual({
      t: Date.parse("2026-06-17T08:00:00Z"),
      lower: 7,
      mid: 10,
      upper: 13,
    });
  });

  it("verschmilzt die Band-Punkte beider Fenster auf t (Live gewinnt am Rand)", () => {
    const historical = trend([point("2026-06-17T09:59:00Z", 12)], {
      profile_band: {
        computed_at: "2026-06-17T09:00:00Z",
        effect_size_k: 3.0,
        points: [{ bucket: "2026-06-17T09:59:00Z", lower: 9, mid: 12, upper: 15 }],
      },
    });
    const live = trend([point("2026-06-17T10:00:00Z", 13)], {
      profile_band: {
        computed_at: "2026-06-17T10:00:00Z",
        effect_size_k: 3.0,
        points: [{ bucket: "2026-06-17T10:00:00Z", lower: 10, mid: 13, upper: 16 }],
      },
    });
    const series = mergeTrendSeries(historical, live);
    expect(series?.profileBand?.points.map((p) => p.t)).toEqual([
      Date.parse("2026-06-17T09:59:00Z"),
      Date.parse("2026-06-17T10:00:00Z"),
    ]);
    // Metadaten aus dem frischeren Fenster (Live).
    expect(series?.profileBand?.computedAt).toBe(Date.parse("2026-06-17T10:00:00Z"));
  });
});

describe("deriveDriftSegments", () => {
  it("gibt nichts zurück, wenn kein Normalband definiert ist", () => {
    const series = mergeTrendSeries(
      trend([point("2026-06-17T10:00:00Z", 99)], { normal_min: null, normal_max: null }),
      null,
    );
    expect(deriveDriftSegments(series!)).toEqual([]);
  });

  it("markiert eine zusammenhängende Überschreitung als ein over-Segment", () => {
    const series = mergeTrendSeries(
      trend([
        point("2026-06-17T10:00:00Z", 15), // normal
        point("2026-06-17T10:01:00Z", 22), // über 20
        point("2026-06-17T10:02:00Z", 25), // über 20
        point("2026-06-17T10:03:00Z", 15), // normal
      ]),
      null,
    );
    const segments = deriveDriftSegments(series!);
    expect(segments).toHaveLength(1);
    expect(segments[0]?.direction).toBe("over");
    expect(segments[0]?.samples).toHaveLength(2);
    expect(segments[0]?.fromT).toBe(Date.parse("2026-06-17T10:01:00Z"));
    expect(segments[0]?.toT).toBe(Date.parse("2026-06-17T10:02:00Z"));
  });

  it("trennt Über- und Unterschreitung in getrennte Segmente", () => {
    const series = mergeTrendSeries(
      trend([
        point("2026-06-17T10:00:00Z", 25), // über
        point("2026-06-17T10:01:00Z", 5), // unter
      ]),
      null,
    );
    const segments = deriveDriftSegments(series!);
    expect(segments.map((s) => s.direction)).toEqual(["over", "under"]);
  });
});
