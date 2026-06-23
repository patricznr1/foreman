// ============================================================
//  FOREMAN Frontend — components/machine/time-series-chart.test.tsx
//  Zweck: Sichert die verbindlichen Designvorgaben des Sensortrends (Studie §4B/§5.5):
//         Normalband als entsättigte Fläche, Eigenprofil graceful (null → kein Strich),
//         Drift als Akzent (diff-over/under + Schraffur, NICHT Alarm-Rot), Mehrkanal-
//         Kodierung, beschreibendes aria-label.
// ============================================================
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { DriftSegment, TrendSeries } from "@/lib/machine/types";

import { TimeSeriesChart } from "./time-series-chart";

const START = Date.parse("2026-06-17T10:00:00Z");
const MID = Date.parse("2026-06-17T10:30:00Z");
const END = Date.parse("2026-06-17T11:00:00Z");

function makeSeries(over: Partial<TrendSeries> = {}): TrendSeries {
  return {
    dataPointId: 42,
    dataPointName: "spindle_temp",
    unit: "°C",
    measurementType: "temperature",
    normalMin: 10,
    normalMax: 20,
    profileBand: null,
    truncated: false,
    samples: [
      { bucket: "2026-06-17T10:00:00Z", t: START, avg: 15, min: 14, max: 16, last: 15 },
      { bucket: "2026-06-17T10:30:00Z", t: MID, avg: 22, min: 21, max: 23, last: 22 },
      { bucket: "2026-06-17T11:00:00Z", t: END, avg: 15, min: 14, max: 16, last: 15 },
    ],
    ...over,
  };
}

describe("TimeSeriesChart", () => {
  it("trägt ein beschreibendes aria-label (Sensor + Einheit) und role img", () => {
    const { getByRole } = render(
      <TimeSeriesChart series={makeSeries()} driftSegments={[]} startMs={START} endMs={END} />,
    );
    const img = getByRole("img");
    expect(img.getAttribute("aria-label")).toContain("spindle_temp");
    expect(img.getAttribute("aria-label")).toContain("°C");
  });

  it("zeichnet die Trendlinie", () => {
    const { container } = render(
      <TimeSeriesChart series={makeSeries()} driftSegments={[]} startMs={START} endMs={END} />,
    );
    expect(container.querySelector('[data-testid="trend-line"]')).not.toBeNull();
  });

  it("zeichnet das Normalband als entsättigte Fläche, wenn Normalwerte vorliegen", () => {
    const { container } = render(
      <TimeSeriesChart series={makeSeries()} driftSegments={[]} startMs={START} endMs={END} />,
    );
    const band = container.querySelector('[data-testid="normal-band"]');
    expect(band).not.toBeNull();
    expect(band?.getAttribute("fill")).toContain("normalband");
  });

  it("ohne Normalband (normalMin/Max null) → keine Normalband-Fläche", () => {
    const { container } = render(
      <TimeSeriesChart
        series={makeSeries({ normalMin: null, normalMax: null })}
        driftSegments={[]}
        startMs={START}
        endMs={END}
      />,
    );
    expect(container.querySelector('[data-testid="normal-band"]')).toBeNull();
  });

  it("Eigenprofil graceful: profileBand null → keine Referenzlinie (kein erfundener Strich)", () => {
    const { container } = render(
      <TimeSeriesChart series={makeSeries()} driftSegments={[]} startMs={START} endMs={END} />,
    );
    expect(container.querySelector('[data-testid="profile-band"]')).toBeNull();
  });

  it("Eigenprofil vorhanden: gestrichelter Korridor (data-series-2), klar vom Normalband unterscheidbar", () => {
    const series = makeSeries({
      profileBand: {
        computedAt: Date.parse("2026-06-17T22:00:00Z"),
        effectSizeK: 3,
        points: [
          { t: START, lower: 12, mid: 15, upper: 18 },
          { t: END, lower: 12, mid: 15, upper: 18 },
        ],
      },
    });
    const { container } = render(
      <TimeSeriesChart series={series} driftSegments={[]} startMs={START} endMs={END} />,
    );
    const band = container.querySelector('[data-testid="profile-band"]');
    expect(band).not.toBeNull();
    // Eigener Token (nicht der Vollflächen-Normalband-Token) + gestrichelt = unterscheidbar.
    expect(band?.innerHTML).toContain("data-series-2");
    expect(band?.querySelector("[stroke-dasharray]")).not.toBeNull();
    // aria-Label benennt den Erwartungskorridor (nicht nur sichtbar, auch zugänglich).
    const img = container.querySelector('[role="img"]');
    expect(img?.getAttribute("aria-label")).toContain("Eigenprofil");
  });

  it("Drift als Akzent (diff-over + Schraffur), NICHT Alarm-Rot", () => {
    const drift: DriftSegment[] = [
      {
        direction: "over",
        fromT: MID,
        toT: MID,
        samples: [{ bucket: "2026-06-17T10:30:00Z", t: MID, avg: 22, min: 21, max: 23, last: 22 }],
      },
    ];
    const { container } = render(
      <TimeSeriesChart series={makeSeries()} driftSegments={drift} startMs={START} endMs={END} />,
    );
    const over = container.querySelector('[data-testid="drift-over"]');
    expect(over).not.toBeNull();
    expect(over?.getAttribute("fill")).toContain("diff-over");
    expect(container.querySelector("pattern")).not.toBeNull();
    expect(container.innerHTML).not.toContain("alarm-critical");
  });
});
