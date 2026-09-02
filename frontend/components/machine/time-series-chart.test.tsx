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
  // ──────────────────────────────────────────────────────────────────
  //  Die Zeitachse muss die SPANNE lesbar machen
  // ──────────────────────────────────────────────────────────────────

  it("kurze Spanne: die Enden tragen nur die Uhrzeit", () => {
    // Eine Stunde — hier ist die Uhrzeit eindeutig und das Datum nur Ballast.
    const { container } = render(
      <TimeSeriesChart series={makeSeries()} driftSegments={[]} startMs={START} endMs={END} />,
    );
    const beschriftung = [...container.querySelectorAll("text")].map((t) => t.textContent ?? "");
    // KEINE feste Uhrzeit erwarten: `toLocaleTimeString` rechnet in die Zeitzone
    // des Laufs um. Der Testdatensatz steht in UTC — lokal (UTC+2) erscheint
    // "12:00", in der CI (UTC) "10:00". Ein festgeschriebener Wanduhr-Wert
    // prüft also die Zeitzone des Rechners, nicht den Prüfling. Geprüft wird
    // die FORM, und um die geht es hier: Uhrzeit ja, Datum nein.
    const zeiten = beschriftung.filter((b) => /^\d{2}:\d{2}$/.test(b));
    expect(zeiten).toHaveLength(2);
    expect(beschriftung.some((b) => /\d{2}\.\d{2}\./.test(b))).toBe(false);
  });

  it("Tagesfenster: die Enden tragen das Datum, nicht nur die Uhrzeit", () => {
    // DER TRAGENDE FALL. Ueber 24 Stunden liegen Anfang und Ende fast auf
    // derselben Uhrzeit — die Achse las sich als "12:00 bis 12:01", und der
    // Verlauf schien die letzte Minute zu zeigen statt eines ganzen Tages.
    // Ein Ausschlag ueber einen Tag ist etwas voellig anderes als einer ueber
    // eine Minute; die Verwechslung ist teuer.
    const tagEnde = START + 24 * 60 * 60 * 1000 + 60_000;
    const { container } = render(
      <TimeSeriesChart series={makeSeries()} driftSegments={[]} startMs={START} endMs={tagEnde} />,
    );
    const beschriftung = [...container.querySelectorAll("text")].map((t) => t.textContent ?? "");
    const mitDatum = beschriftung.filter((b) => /\d{2}\.\d{2}\./.test(b));
    expect(mitDatum).toHaveLength(2);
    // Und sie unterscheiden sich — sonst waere das Datum so nichtssagend wie
    // vorher die Uhrzeit.
    expect(mitDatum[0]).not.toBe(mitDatum[1]);
  });
});
