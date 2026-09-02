// ============================================================
//  FOREMAN Frontend — components/machine/time-series-chart.test.tsx
//  Zweck: Sichert die verbindlichen Designvorgaben des Sensortrends (Studie §4B/§5.5):
//         Normalband als entsättigte Fläche, Eigenprofil graceful (null → kein Strich),
//         Drift als Akzent (diff-over/under + Schraffur, NICHT Alarm-Rot), Mehrkanal-
//         Kodierung, beschreibendes aria-label.
//         Dazu die Zusicherungen des freien Ausschnitts: Beschneidung der Datenschichten,
//         vier getrennte Marken für vier Gründe leerer Fläche, die Linie bricht an
//         Löchern, Minutenpunkte samt Hülle am Zoom-Boden, mitskalierende Wert-Achse.
//         Alle Geometrie-Zusicherungen rechnen in viewBox-Einheiten (width/height sind
//         Requisiten, preserveAspectRatio ist "none") — jsdom misst kein Layout.
// ============================================================
import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { DriftSegment, TrendSample, TrendSeries } from "@/lib/machine/types";
import { MAX_SPAN_MS } from "@/lib/machine/viewport";

import { TimeSeriesChart } from "./time-series-chart";

const START = Date.parse("2026-06-17T10:00:00Z");
const MID = Date.parse("2026-06-17T10:30:00Z");
const END = Date.parse("2026-06-17T11:00:00Z");

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;

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

/** Lückenlose Minuten-Buckets ab `fromMs` — die Auflösung, die der Speicher führt. */
function minuteSamples(fromMs: number, count: number, avgAt: (index: number) => number): TrendSample[] {
  return Array.from({ length: count }, (_, index) => {
    const t = fromMs + index * MINUTE;
    const avg = avgAt(index);
    return { bucket: new Date(t).toISOString(), t, avg, min: avg - 1, max: avg + 1, last: avg };
  });
}

/** Texte aller `<text>`-Knoten — die Achsen- und Marken-Beschriftung. */
function texts(container: HTMLElement): string[] {
  return [...container.querySelectorAll("text")].map((node) => node.textContent ?? "");
}

/** Zahl aus einem SVG-Attribut; NaN würde jede Zusicherung darauf rot machen. */
function attrNumber(element: Element | null, name: string): number {
  return Number(element?.getAttribute(name));
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
    const beschriftung = texts(container);
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
    const beschriftung = texts(container);
    const mitDatum = beschriftung.filter((b) => /\d{2}\.\d{2}\./.test(b));
    expect(mitDatum).toHaveLength(2);
    // Und sie unterscheiden sich — sonst waere das Datum so nichtssagend wie
    // vorher die Uhrzeit.
    expect(mitDatum[0]).not.toBe(mitDatum[1]);
  });

  it("kurze Spanne WEIT in der Vergangenheit: die Enden tragen trotzdem das Datum", () => {
    // BELEGT die zweite Hälfte der ODER-Regel, die die Spanne allein nicht trägt:
    // ein "08:12" von vorletztem Dienstag ist von heute morgen nicht zu unter-
    // scheiden. Zwei Stunden Spanne (unter der Datumsschwelle), sechs Tage zurück.
    // Dass die beiden Fälle darüber heute schon grün wären, belegt diesen NICHT.
    const now = START + 7 * 24 * HOUR;
    const ende = now - 6 * 24 * HOUR;
    const { container } = render(
      <TimeSeriesChart
        series={makeSeries()}
        driftSegments={[]}
        startMs={ende - 2 * HOUR}
        endMs={ende}
        nowMs={now}
      />,
    );
    const achse = texts(container).filter((b) => /\d{2}\.\d{2}\./.test(b));
    expect(achse).toHaveLength(2);
  });

  // ──────────────────────────────────────────────────────────────────
  //  Freier Ausschnitt: Beschneidung, Marken, Löcher, Zoom-Boden, Wert-Achse
  // ──────────────────────────────────────────────────────────────────

  it("die Datenschichten tragen ein clip-path, dessen id im defs-Block definiert ist", () => {
    // BELEGT, dass das Beschneiden VERDRAHTET ist und nicht nur deklariert: beide
    // Stellen werden abgefragt und die ids verglichen. Ohne Beschneidung läuft die
    // Kurve beim Hineinzoomen über die Achsenbeschriftung — in jsdom unsichtbar,
    // im Attribut eindeutig.
    // MUTATION, die rot machen MUSS: das clip-path-Attribut von der Datengruppe
    // entfernen (den <clipPath> im defs stehen lassen).
    const { container } = render(
      <TimeSeriesChart series={makeSeries()} driftSegments={[]} startMs={START} endMs={END} />,
    );
    const clip = container.querySelector("clipPath");
    const clipId = clip?.getAttribute("id") ?? "";
    expect(clipId).not.toBe("");
    const layers = container.querySelector('[data-testid="data-layers"]');
    expect(layers?.getAttribute("clip-path")).toBe(`url(#${clipId})`);
    // Und die Datenschichten liegen wirklich darin, nicht daneben.
    expect(layers?.querySelector('[data-testid="trend-line"]')).not.toBeNull();
    expect(layers?.querySelector('[data-testid="normal-band"]')).not.toBeNull();
    // Die Wert-Beschriftung gehört zum Rahmen und bleibt AUSSERHALB — sonst
    // beschnitte sie sich selbst weg (sie steht links von der Zeichenfläche).
    expect(layers?.querySelector('[data-testid="y-max"]')).toBeNull();
    expect(container.querySelector('[data-testid="y-max"]')).not.toBeNull();
  });

  it("unloaded, retention-wall, gap und truncated-right sind VIER Marken mit paarweise verschiedenen Texten", () => {
    // DER ANTI-LÜGEN-TEST. Genau hier verschmelzen "noch nicht abgerufen",
    // "gibt es nicht", "kein Messwert" und "gekappt" sonst zu einer stummen leeren
    // Fläche — und die behauptet gegenüber dem Werker "keine Störung", wo in
    // Wahrheit nur niemand gefragt hat.
    // MUTATIONEN, die rot machen MÜSSEN: zwei der vier Texte gleich formulieren
    // (Paarvergleich) bzw. eine Marke weglassen (Existenz-Zusicherung).
    const now = Date.parse("2026-06-17T12:00:00Z");
    const startMs = now - MAX_SPAN_MS; // genau auf der Aufbewahrungswand
    const endMs = startMs + 2 * HOUR;
    const series = makeSeries({
      truncated: true,
      samples: [
        ...minuteSamples(startMs + 20 * MINUTE, 5, () => 15),
        ...minuteSamples(startMs + 60 * MINUTE, 5, () => 16),
      ],
    });

    const { container } = render(
      <TimeSeriesChart
        series={series}
        driftSegments={[]}
        startMs={startMs}
        endMs={endMs}
        nowMs={now}
        loadedFromMs={startMs + 30 * MINUTE}
      />,
    );

    const marken = {
      unloaded: container.querySelector('[data-testid="mark-unloaded"]'),
      wall: container.querySelector('[data-testid="mark-retention-wall"]'),
      gap: container.querySelector('[data-testid="mark-gap"]'),
      truncated: container.querySelector('[data-testid="mark-truncated-right"]'),
    };
    expect(marken.unloaded).not.toBeNull();
    expect(marken.wall).not.toBeNull();
    expect(marken.gap).not.toBeNull();
    expect(marken.truncated).not.toBeNull();

    const texte = [
      marken.unloaded?.textContent ?? "",
      marken.wall?.textContent ?? "",
      marken.gap?.textContent ?? "",
      marken.truncated?.textContent ?? "",
    ];
    for (const text of texte) {
      expect(text.length).toBeGreaterThan(0);
    }
    // Alle sechs Paare einzeln — ein Zähler über ein Set bliebe grün, solange
    // irgendwo noch ein Unterschied steht.
    expect(texte[0]).not.toBe(texte[1]);
    expect(texte[0]).not.toBe(texte[2]);
    expect(texte[0]).not.toBe(texte[3]);
    expect(texte[1]).not.toBe(texte[2]);
    expect(texte[1]).not.toBe(texte[3]);
    expect(texte[2]).not.toBe(texte[3]);
  });

  it("die unloaded-Fläche endet exakt bei xScale(loadedFromMs); ohne ungefragten Bereich existiert sie nicht", () => {
    // BELEGT echte Geometrie ohne Layout: width/height sind Requisiten und
    // preserveAspectRatio ist "none". Eine Fläche, die existiert, aber an der
    // falschen Stelle endet, behauptet Abdeckung, die es nicht gibt — bloße
    // Existenz fängt das nicht.
    // MUTATIONEN, die rot machen MÜSSEN: die Breite auf die halbe Strecke setzen
    // (Kanten-Vergleich); die Existenzbedingung von > auf >= ändern (zweiter Fall).
    const loadedFromMs = START + 15 * MINUTE;
    const { container } = render(
      <TimeSeriesChart
        series={makeSeries()}
        driftSegments={[]}
        startMs={START}
        endMs={END}
        loadedFromMs={loadedFromMs}
      />,
    );
    // Linker Rand und Breite der Zeichenfläche werden ABGELESEN (Normalband-Rechteck),
    // nicht abgetippt: die Polsterung ist ein Layout-Detail dieses Bausteins.
    const band = container.querySelector('[data-testid="normal-band"]');
    const plotLeft = attrNumber(band, "x");
    const plotWidth = attrNumber(band, "width");
    const erwartetesEnde = plotLeft + ((loadedFromMs - START) / (END - START)) * plotWidth;

    const veil = container.querySelector('[data-testid="mark-unloaded"] rect');
    expect(veil).not.toBeNull();
    expect(attrNumber(veil, "x")).toBeCloseTo(plotLeft, 6);
    expect(attrNumber(veil, "x") + attrNumber(veil, "width")).toBeCloseTo(erwartetesEnde, 6);

    // Zweiter Fall: reicht das geladene Fenster mindestens bis an den linken Rand,
    // steht KEIN Schleier — er behauptete sonst "nicht geladen", wo alles da ist.
    const { container: bündig } = render(
      <TimeSeriesChart
        series={makeSeries()}
        driftSegments={[]}
        startMs={START}
        endMs={END}
        loadedFromMs={START}
      />,
    );
    expect(bündig.querySelector('[data-testid="mark-unloaded"]')).toBeNull();
  });

  it("ein Loch ergibt ZWEI Linien-Züge und eine gap-Marke, dieselben Punkte ohne Loch EINEN Zug und keine Marke", () => {
    // BELEGT die gezeichnete Sache: die Zahl der M-Kommandos in den Trendlinien.
    // Der Zwilling ohne Loch ist die Aufbau-Kontrolle — ohne ihn misst der Test nichts.
    // MUTATION, die rot machen MUSS: splitAtGaps im Baustein durch einen einzelnen
    // linePath über alle Punkte ersetzen.
    const mitLoch = makeSeries({
      samples: [
        ...minuteSamples(START, 5, () => 15),
        ...minuteSamples(START + 15 * MINUTE, 5, () => 16),
      ],
    });
    const ohneLoch = makeSeries({ samples: minuteSamples(START, 20, () => 15) });
    const endeMs = START + 19 * MINUTE;

    const zaehleM = (container: HTMLElement): number =>
      [...container.querySelectorAll('[data-testid="trend-line"]')].reduce(
        (sum, path) => sum + ((path.getAttribute("d") ?? "").match(/M/g)?.length ?? 0),
        0,
      );

    const { container: a } = render(
      <TimeSeriesChart series={mitLoch} driftSegments={[]} startMs={START} endMs={endeMs} />,
    );
    expect(zaehleM(a)).toBe(2);
    expect(a.querySelectorAll('[data-testid="mark-gap"]')).toHaveLength(1);

    const { container: b } = render(
      <TimeSeriesChart series={ohneLoch} driftSegments={[]} startMs={START} endMs={endeMs} />,
    );
    expect(zaehleM(b)).toBe(1);
    expect(b.querySelectorAll('[data-testid="mark-gap"]')).toHaveLength(0);
  });

  it("eine lückenlose Reihe, die verdichtet werden MUSS, bleibt EIN Zug ohne gap-Marke", () => {
    // BELEGT die zwingende Reihenfolge (zuschneiden → trennen → verdichten) an der
    // Stelle, an der sie sich auswirkt: 1000 Minuten-Buckets auf rund 330 Spalten,
    // also drei Punkte je Spalte, von denen die Verdichtung höchstens zwei behält.
    // Der Abstand der übrig gebliebenen Nachbarn überschreitet dann das Loch-
    // Kriterium — würde erst danach getrennt, zerfiele eine lückenlos gemessene
    // Reihe in Dutzende Züge, und über gemessener Zeit stünde "kein Messwert".
    // MUTATION, die rot machen MUSS: die beiden Schritte tauschen, also
    // splitAtGaps(decimate(visible, …), …) statt decimate je Zug.
    const anzahl = 1000;
    const series = makeSeries({ samples: minuteSamples(START, anzahl, (i) => 15 + (i % 5)) });
    const { container } = render(
      <TimeSeriesChart
        series={series}
        driftSegments={[]}
        startMs={START}
        endMs={START + (anzahl - 1) * MINUTE}
      />,
    );
    expect(container.querySelectorAll('[data-testid="trend-line"]')).toHaveLength(1);
    expect(container.querySelectorAll('[data-testid="mark-gap"]')).toHaveLength(0);
    // Aufbau-Kontrolle: Die Verdichtung hat wirklich stattgefunden — stünden noch
    // alle 1000 Punkte im Pfad, bewiese der Test nur, dass nichts passiert ist.
    const d = container.querySelector('[data-testid="trend-line"]')?.getAttribute("d") ?? "";
    const punkte = (d.match(/[ML]/g) ?? []).length;
    expect(punkte).toBeGreaterThan(0);
    expect(punkte).toBeLessThan(anzahl);
  });

  it("Punkte UND Min-Max-Hülle erscheinen bei 20 Minuten Spanne und fehlen bei 24 Stunden", () => {
    // BELEGT die Sichtbarmachung des 1-Minuten-Bodens ohne Layout: der Schwellwert
    // rechnet mit der width-Requisite. Beide Richtungen, damit der Test nicht grün
    // bleibt, wenn die Punkte bei Wochenspanne zu einem Balken verschmieren.
    // MUTATIONEN, die rot machen MÜSSEN: den Schwellwert-Vergleich zu ">= 0" machen
    // (24-h-Fall); die Hülle weglassen (Hüllen-Zusicherung im 20-min-Fall).
    const series = makeSeries({ samples: minuteSamples(START, 21, (i) => 15 + (i % 3)) });

    const { container: nah } = render(
      <TimeSeriesChart series={series} driftSegments={[]} startMs={START} endMs={START + 20 * MINUTE} />,
    );
    expect(nah.querySelectorAll('[data-testid="sample-dot"]').length).toBeGreaterThan(0);
    const huelle = nah.querySelector('[data-testid="bucket-envelope"]');
    expect(huelle).not.toBeNull();
    // Eine GESCHLOSSENE Fläche über die sichtbaren Punkte — ein leerer Pfad wäre ein
    // vorhandenes Element ohne Aussage und bliebe bei bloßer Existenzprüfung grün.
    expect(huelle?.getAttribute("d") ?? "").toContain("Z");

    const { container: fern } = render(
      <TimeSeriesChart series={series} driftSegments={[]} startMs={START} endMs={START + 24 * HOUR} />,
    );
    expect(fern.querySelectorAll('[data-testid="sample-dot"]')).toHaveLength(0);
    expect(fern.querySelector('[data-testid="bucket-envelope"]')).toBeNull();
  });

  it("aria-label nennt Anfang, Ende, Spanne in Worten, das Zustandswort und die Auflösung — an drei Spannen", () => {
    // BELEGT die Barrierefreiheits-Auflage wörtlich, an drei Zoomgraden statt an
    // einem: fünf getrennte Zusicherungen auf die ausgegebene Form.
    // MUTATION, die rot machen MUSS: das Zustandswort aus dem Label entfernen —
    // genau diese Zusicherung wird rot, die anderen bleiben grün.
    const now = Date.parse("2026-06-17T12:00:00Z");
    const faelle: Array<{ spanMs: number; wort: string }> = [
      { spanMs: 20 * MINUTE, wort: "Spanne 20 Minuten" },
      { spanMs: 8 * HOUR, wort: "Spanne 8 Stunden" },
      { spanMs: MAX_SPAN_MS, wort: "Spanne 7 Tage" },
    ];

    for (const fall of faelle) {
      const { container } = render(
        <TimeSeriesChart
          series={makeSeries()}
          driftSegments={[]}
          startMs={now - fall.spanMs}
          endMs={now}
          nowMs={now}
        />,
      );
      const label = container.querySelector('[role="img"]')?.getAttribute("aria-label") ?? "";
      const ausschnitt = /Ausschnitt (\d{2}\.\d{2}\. \d{2}:\d{2}) bis (\d{2}\.\d{2}\. \d{2}:\d{2})/.exec(label);
      expect(ausschnitt).not.toBeNull();
      expect(ausschnitt?.[1]).not.toBe(ausschnitt?.[2]);
      expect(label).toContain(fall.wort);
      expect(label).toContain("folgt dem Live-Rand");
      expect(label).toContain("Auflösung 1 Minute");
    }

    // Kontroll-Zwilling zum Zustandswort: ein Ausschnitt weit hinter dem Live-Rand
    // sagt "steht fest" — ohne ihn belegte die Zusicherung oben nur, dass irgendein
    // fester Satz im Label steht.
    const { container: fester } = render(
      <TimeSeriesChart
        series={makeSeries()}
        driftSegments={[]}
        startMs={now - 6 * HOUR}
        endMs={now - 4 * HOUR}
        nowMs={now}
      />,
    );
    const fest = fester.querySelector('[role="img"]')?.getAttribute("aria-label") ?? "";
    expect(fest).toContain("steht fest");
    expect(fest).not.toContain("folgt dem Live-Rand");
  });

  it("die Wert-Achse folgt dem sichtbaren Ausschnitt, und beide Enden sind auch bei reduced ohne Normalband beschriftet", () => {
    // BELEGT (1): ein Ausschnitt MIT Ausreißer ergibt eine andere y-max-Beschriftung
    // als derselbe Ausschnitt ohne ihn — sonst wäre der Zoom folgenlos, weil die
    // Domäne über die ganze geladene Reihe stünde.
    // BELEGT (2): bei reduced und ohne Normalband stehen beide Beschriftungen
    // trotzdem — sonst ist die Manager-Sicht bei springender Skala skalenblind.
    // MUTATIONEN, die rot machen MÜSSEN: die Y-Domäne wieder über ALLE samples
    // ziehen (1); die Beschriftungen hinter "!reduced && hasBand" gaten (2).
    const series = makeSeries({ samples: minuteSamples(START, 60, (i) => (i === 50 ? 200 : 15)) });

    const yMaxText = (container: HTMLElement): string =>
      container.querySelector('[data-testid="y-max"]')?.textContent ?? "";

    const { container: mitAusreisser } = render(
      <TimeSeriesChart series={series} driftSegments={[]} startMs={START} endMs={START + 55 * MINUTE} />,
    );
    const { container: ohneAusreisser } = render(
      // Der Nachbarpunkt außerhalb des Randes gehört dazu (Minute 41) — der
      // Ausreißer bei Minute 50 liegt sicher außerhalb.
      <TimeSeriesChart series={series} driftSegments={[]} startMs={START} endMs={START + 40 * MINUTE} />,
    );
    expect(yMaxText(mitAusreisser)).not.toBe("");
    expect(yMaxText(ohneAusreisser)).not.toBe("");
    expect(yMaxText(mitAusreisser)).not.toBe(yMaxText(ohneAusreisser));

    const { container: karg } = render(
      <TimeSeriesChart
        series={makeSeries({ normalMin: null, normalMax: null })}
        driftSegments={[]}
        startMs={START}
        endMs={END}
        reduced
      />,
    );
    expect(karg.querySelector('[data-testid="y-max"]')).not.toBeNull();
    expect(karg.querySelector('[data-testid="y-min"]')).not.toBeNull();
  });
});
