// ============================================================
//  FOREMAN Frontend — lib/machine/trend-series.test.ts
//  Zweck: Sichert die transport-agnostische Trend-Logik — den sprungfreien Merge
//         von historischem Pull + Live-1h-Fenster (auf bucket-Schlüssel), die
//         Drift-Segment-Ableitung (Über-/Unterschreitung des Normalbands, an
//         Lücken abgebrochen) und die Ausschnitts-Aufbereitung für den stufenlosen
//         Zoom (visibleSlice, splitAtGaps, decimate).
// ============================================================
import { describe, expect, it } from "vitest";

import type { MachineTrendOut, TrendPointOut } from "@/lib/api/contracts";

import { BUCKET_MS } from "./time-window";
import {
  DEFAULT_MAX_GAP_MS,
  decimate,
  deriveDriftSegments,
  mergeTrendSeries,
  splitAtGaps,
  toTrendSamples,
  visibleSlice,
} from "./trend-series";
import type { TrendSample, TrendSeries } from "./types";

function point(bucket: string, avg: number, extra: Partial<TrendPointOut> = {}): TrendPointOut {
  return { bucket, avg, min: extra.min ?? avg, max: extra.max ?? avg, last: extra.last ?? avg };
}

/** Zeitanker der Fixtures — feste Epoche, damit alle Abstände nachrechenbar sind. */
const T0 = Date.parse("2026-06-17T10:00:00Z");

/** Baut Samples mit FREI wählbaren Zeitpunkten (ms relativ zu T0) — für Grenzwerte. */
function samplesAt(offsets: readonly number[], avgs?: readonly number[]): TrendSample[] {
  return offsets.map((offset, index) => {
    const avg = avgs?.[index] ?? 15;
    return {
      bucket: new Date(T0 + offset).toISOString(),
      t: T0 + offset,
      avg,
      min: avg,
      max: avg,
      last: avg,
    };
  });
}

/** Baut eine Reihe direkt aus Samples — umgeht den ISO-Bucket-Weg für Grenzwerte. */
function seriesOf(samples: TrendSample[], over: Partial<TrendSeries> = {}): TrendSeries {
  return {
    dataPointId: 42,
    dataPointName: "spindle_temp",
    unit: "°C",
    measurementType: "temperature",
    normalMin: 10,
    normalMax: 20,
    profileBand: null,
    samples,
    truncated: false,
    ...over,
  };
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

  it("bricht einen Lauf an einer Lücke ab — derselbe Datensatz ohne Loch bleibt EIN Segment", () => {
    // BELEGT: Die Differenzfläche endet dort, wo die Messung endet. Ein Lauf, der über
    // ein Loch hinwegwächst, schraffiert Zeit als „Abweichung", für die kein Messwert
    // vorliegt — beim Hineinzoomen wird daraus ein bildfüllender, erfundener Verlauf.
    // Der Zwilling ohne Loch ist die Aufbau-Kontrolle: ohne ihn belegte der erste Fall
    // nur, dass irgendwo getrennt wird.
    // ROT BEI: Entfernt man den Lücken-flush im Schleifenkopf von deriveDriftSegments,
    // liefert der Loch-Fall wieder EIN Segment.
    const mitLoch = mergeTrendSeries(
      trend([
        point("2026-06-17T10:00:00Z", 25), // über 20
        point("2026-06-17T10:01:00Z", 26), // über 20
        // 10:02 und 10:03 fehlen — drei Minuten ohne Messwert
        point("2026-06-17T10:04:00Z", 27), // über 20
        point("2026-06-17T10:05:00Z", 28), // über 20
      ]),
      null,
    );
    const geteilt = deriveDriftSegments(mitLoch!);
    expect(geteilt).toHaveLength(2);
    expect(geteilt.map((s) => s.direction)).toEqual(["over", "over"]);
    // Das erste Stück endet beim LETZTEN Messwert davor, nicht am nächsten danach.
    expect(geteilt[0]?.toT).toBe(Date.parse("2026-06-17T10:01:00Z"));
    expect(geteilt[1]?.fromT).toBe(Date.parse("2026-06-17T10:04:00Z"));

    const ohneLoch = mergeTrendSeries(
      trend([
        point("2026-06-17T10:00:00Z", 25),
        point("2026-06-17T10:01:00Z", 26),
        point("2026-06-17T10:02:00Z", 27),
        point("2026-06-17T10:03:00Z", 28),
      ]),
      null,
    );
    expect(deriveDriftSegments(ohneLoch!)).toHaveLength(1);
  });

  it("trennt bei einem Abstand ÜBER maxGapMs, nicht schon auf der Grenze", () => {
    // BELEGT: den Grenzwert selbst, in beide Richtungen — genau auf maxGapMs bleibt der
    // Lauf zusammen, eine Millisekunde darüber zerfällt er. Ohne diesen Fall wäre die
    // Toleranz nur ein Kommentar.
    // ROT BEI: `>` zu `>=` im Lücken-Vergleich (der Grenzfall trennt dann) oder den
    // Vergleich ganz entfernen (der Fall darüber trennt dann nicht mehr).
    const aufDerGrenze = seriesOf(samplesAt([0, BUCKET_MS], [25, 26]));
    expect(deriveDriftSegments(aufDerGrenze, BUCKET_MS)).toHaveLength(1);

    const knappDarueber = seriesOf(samplesAt([0, BUCKET_MS + 1], [25, 26]));
    expect(deriveDriftSegments(knappDarueber, BUCKET_MS)).toHaveLength(2);
  });

  it("nimmt ohne Angabe DEFAULT_MAX_GAP_MS: ein fehlender Bucket trennt, ein Bucket Abstand nicht", () => {
    // BELEGT: Der Vorgabewert ist selbst eine Zusicherung — der bestehende Aufrufer in
    // use-machine-trend.ts übergibt kein Argument, und lückenlose Minuten-Buckets
    // (60 s Abstand) dürfen dort nicht in Stücke zerfallen, während ein einzelner
    // fehlender Bucket (120 s Abstand) sehr wohl trennt.
    // ROT BEI: DEFAULT_MAX_GAP_MS auf 1 * BUCKET_MS senken (der lückenlose Fall zerfällt)
    // oder auf 3 * BUCKET_MS heben (der fehlende Bucket trennt nicht mehr).
    expect(DEFAULT_MAX_GAP_MS).toBeGreaterThan(BUCKET_MS);
    expect(DEFAULT_MAX_GAP_MS).toBeLessThan(2 * BUCKET_MS);

    const lueckenlos = seriesOf(samplesAt([0, BUCKET_MS, 2 * BUCKET_MS], [25, 26, 27]));
    expect(deriveDriftSegments(lueckenlos)).toHaveLength(1);

    const einBucketFehlt = seriesOf(samplesAt([0, BUCKET_MS, 3 * BUCKET_MS], [25, 26, 27]));
    expect(deriveDriftSegments(einBucketFehlt)).toHaveLength(2);
  });

  it("hält die Lücken-Trennung auch dort, wo die Richtung gleich bleibt und der Wert steigt", () => {
    // BELEGT: Der Abbruch hängt am ZEITABSTAND, nicht an einem Richtungswechsel. Genau
    // dieser Fall — durchgehend „over", nur mit Loch — ist der, den die alte Fassung
    // stillschweigend zu einer Fläche verband.
    // ROT BEI: den Lücken-flush an eine zusätzliche Bedingung hängen (etwa nur bei
    // Richtungswechsel prüfen) — dann entsteht wieder ein durchgehendes Segment.
    const series = seriesOf(samplesAt([0, 10 * BUCKET_MS], [25, 25]));
    const segments = deriveDriftSegments(series);
    expect(segments).toHaveLength(2);
    expect(segments[0]?.samples).toHaveLength(1);
    expect(segments[1]?.samples).toHaveLength(1);
  });
});

describe("visibleSlice", () => {
  it("nimmt je EINEN Punkt außerhalb beider Ränder mit", () => {
    // BELEGT: Die Linie erreicht den Plotrand. Ohne den Nachbarpunkt endet sie sichtbar
    // davor, und der Werker liest den Zwischenraum als fehlenden Messwert — eine
    // erfundene Lücke, ausgerechnet in einer Ansicht, die echte Lücken als Aussage
    // markiert. Geprüft über die t-Werte des ERSTEN und LETZTEN Elements.
    // ROT BEI: die Nachbarpunkt-Erweiterung entfernen (`firstInside` bzw. `firstAfter`
    // ohne −1 / +1) — dann liegen erster und letzter t innerhalb des Ausschnitts.
    const samples = samplesAt([0, BUCKET_MS, 2 * BUCKET_MS, 3 * BUCKET_MS, 4 * BUCKET_MS]);
    const sichtbar = visibleSlice(samples, T0 + 1.5 * BUCKET_MS, T0 + 2.5 * BUCKET_MS);
    expect(sichtbar.map((s) => s.t)).toEqual([
      T0 + BUCKET_MS,
      T0 + 2 * BUCKET_MS,
      T0 + 3 * BUCKET_MS,
    ]);
    // Der erste liegt LINKS des Ausschnitts, der letzte RECHTS davon.
    expect(sichtbar[0]!.t).toBeLessThan(T0 + 1.5 * BUCKET_MS);
    expect(sichtbar[sichtbar.length - 1]!.t).toBeGreaterThan(T0 + 2.5 * BUCKET_MS);
  });

  it("erfindet am Reihenanfang und -ende keinen Nachbarn", () => {
    // BELEGT: Die Erweiterung halluziniert keine Punkte. Umfasst der Ausschnitt die
    // ganze Reihe, kommt genau die Reihe zurück — kein erfundener Punkt links von der
    // ersten und keiner rechts von der letzten Messung.
    // ROT BEI: den Index ohne Math.max/Längenprüfung um eins verschieben (undefined im
    // Ergebnis) oder einen Randpunkt synthetisieren.
    const samples = samplesAt([0, BUCKET_MS, 2 * BUCKET_MS]);
    const sichtbar = visibleSlice(samples, T0 - 10 * BUCKET_MS, T0 + 10 * BUCKET_MS);
    expect(sichtbar.map((s) => s.t)).toEqual([T0, T0 + BUCKET_MS, T0 + 2 * BUCKET_MS]);
  });

  it("zählt einen Punkt GENAU auf dem Rand zum Ausschnitt, nicht als Nachbarn", () => {
    // BELEGT: den Grenzwert selbst — auf der Grenze, knapp darunter und knapp darüber.
    // Ohne diesen Fall wäre unentschieden, ob `>=`/`<=` oder `>`/`<` gemeint ist, und
    // die Auswahl verschöbe sich lautlos um einen Punkt.
    // ROT BEI: `sample.t >= startMs` zu `> startMs` ändern (der Punkt auf startMs
    // gilt dann als Nachbar) bzw. `sample.t > endMs` zu `>= endMs`.
    const samples = samplesAt([0, BUCKET_MS, 2 * BUCKET_MS, 3 * BUCKET_MS, 4 * BUCKET_MS]);
    // Ausschnitt exakt von Bucket 1 bis Bucket 3: drinnen 1..3, Nachbarn 0 und 4.
    const aufDerGrenze = visibleSlice(samples, T0 + BUCKET_MS, T0 + 3 * BUCKET_MS);
    expect(aufDerGrenze.map((s) => s.t)).toEqual([
      T0,
      T0 + BUCKET_MS,
      T0 + 2 * BUCKET_MS,
      T0 + 3 * BUCKET_MS,
      T0 + 4 * BUCKET_MS,
    ]);
    // Eine Millisekunde weiter rechts: Bucket 1 fällt aus dem Ausschnitt und wird zum
    // linken Nachbarn — Bucket 0 fällt damit ganz weg.
    const knappDarueber = visibleSlice(samples, T0 + BUCKET_MS + 1, T0 + 3 * BUCKET_MS);
    expect(knappDarueber.map((s) => s.t)).toEqual([
      T0 + BUCKET_MS,
      T0 + 2 * BUCKET_MS,
      T0 + 3 * BUCKET_MS,
      T0 + 4 * BUCKET_MS,
    ]);
  });

  it("liefert für die leere Reihe und für eine Spanne von 0 ein sauberes Ergebnis", () => {
    // BELEGT: die entarteten Fälle. Eine leere Reihe darf keinen undefined-Eintrag
    // erzeugen, und eine Spanne von 0 (Anfang == Ende) muss den Punkt genau dort samt
    // beiden Nachbarn liefern statt einer leeren Auswahl.
    // ROT BEI: den Fall `firstInside === -1` auf einen festen Index setzen (die leere
    // Reihe liefert dann [undefined]) oder die Spanne 0 als leer kurzschließen.
    expect(visibleSlice([], T0, T0 + BUCKET_MS)).toEqual([]);

    const samples = samplesAt([0, BUCKET_MS, 2 * BUCKET_MS]);
    const punktgenau = visibleSlice(samples, T0 + BUCKET_MS, T0 + BUCKET_MS);
    expect(punktgenau.map((s) => s.t)).toEqual([T0, T0 + BUCKET_MS, T0 + 2 * BUCKET_MS]);
  });

  it("gibt bei einem Ausschnitt komplett rechts der Reihe nur den linken Nachbarn zurück", () => {
    // BELEGT: Ein Ausschnitt jenseits aller Messwerte liefert genau den letzten Punkt
    // als Nachbarn — nicht die ganze Reihe (das wäre ein Diagramm voller Daten, die
    // gar nicht im Bild liegen) und nicht nichts (dann verschwände die Linie auch am
    // Rand des Bildes, obwohl links davon gemessen wurde).
    // ROT BEI: den Zweig `firstInside === -1` durch `from = 0` ersetzen — dann kommt
    // die ganze Reihe zurück.
    const samples = samplesAt([0, BUCKET_MS, 2 * BUCKET_MS]);
    const rechtsDavon = visibleSlice(samples, T0 + 10 * BUCKET_MS, T0 + 20 * BUCKET_MS);
    expect(rechtsDavon.map((s) => s.t)).toEqual([T0 + 2 * BUCKET_MS]);

    const linksDavon = visibleSlice(samples, T0 - 20 * BUCKET_MS, T0 - 10 * BUCKET_MS);
    expect(linksDavon.map((s) => s.t)).toEqual([T0]);
  });
});

describe("splitAtGaps", () => {
  it("trennt bei mehr als maxGapMs, nicht bei genau maxGapMs — ohne Loch bleibt EIN Zug", () => {
    // BELEGT: den Grenzwert selbst statt „es wird irgendwo getrennt", plus den
    // Aufbau-Kontroll-Zwilling. Ohne den Grenzfall wäre der Toleranzwert nur ein
    // Kommentar; ohne den Zwilling belegte der Trennfall nur, dass die Funktion
    // überhaupt etwas zerlegt.
    // ROT BEI: `>` zu `>=` ändern — der Fall exakt auf maxGapMs zerfällt dann.
    const grenze = DEFAULT_MAX_GAP_MS;

    const aufDerGrenze = splitAtGaps(samplesAt([0, grenze, 2 * grenze]), grenze);
    expect(aufDerGrenze).toHaveLength(1);
    expect(aufDerGrenze[0]).toHaveLength(3);

    const knappDarunter = splitAtGaps(samplesAt([0, grenze - 1]), grenze);
    expect(knappDarunter).toHaveLength(1);

    const knappDarueber = splitAtGaps(samplesAt([0, grenze + 1]), grenze);
    expect(knappDarueber).toHaveLength(2);
    expect(knappDarueber.map((seg) => seg.length)).toEqual([1, 1]);
  });

  it("verliert beim Zerlegen keinen einzigen Punkt und behält die Reihenfolge", () => {
    // BELEGT: Die Zerlegung ist eine Aufteilung, keine Auswahl — zusammengesetzt ergibt
    // sie wieder exakt die Eingabe. Ein Zerlegen, das Punkte unterschlägt, sähe im Bild
    // aus wie eine weitere Lücke und wäre von einer echten nicht zu unterscheiden.
    // ROT BEI: beim Trennen den auslösenden Punkt verwerfen statt ihn als ersten des
    // neuen Zuges zu führen.
    const samples = samplesAt([0, BUCKET_MS, 10 * BUCKET_MS, 11 * BUCKET_MS, 30 * BUCKET_MS]);
    const segments = splitAtGaps(samples, DEFAULT_MAX_GAP_MS);
    expect(segments.map((seg) => seg.length)).toEqual([2, 2, 1]);
    expect(segments.flat()).toEqual(samples);
  });

  it("liefert für die leere Reihe [] und für einen einzelnen Punkt genau einen Zug", () => {
    // BELEGT: die entarteten Fälle. `[]` darf kein leeres Segment erzeugen — ein leerer
    // Zug würde im Diagramm zu einem Pfad ohne Punkte und damit zu einem `d=""`.
    // ROT BEI: das laufende Segment am Ende bedingungslos anhängen (die leere Reihe
    // liefert dann [[]]).
    expect(splitAtGaps([], DEFAULT_MAX_GAP_MS)).toEqual([]);
    expect(splitAtGaps(samplesAt([0]), DEFAULT_MAX_GAP_MS)).toHaveLength(1);
  });
});

describe("decimate", () => {
  it("ein einzelner Minuten-Ausschlag überlebt die Verdichtung auf 330 Spalten mit EXAKTEM Wert", () => {
    // BELEGT: den Unterschied zwischen einer Verdichtung und dem stillen Löschen genau
    // der Information, wegen der jemand auf das Diagramm schaut. Geprüft wird der WERT,
    // nicht die Anzahl: 10.080 Punkte (ein volles 168-h-Fenster) auf 330 Spalten, mit
    // einem einminütigen Ausschlag mittendrin.
    // ROT BEI: Min/Max durch „jeden n-ten Punkt" ersetzen — der Ausschlag verschwindet
    // aus dem Ergebnis. Genau diese Mutation ist die wahrscheinlichste künftige
    // „Optimierung", deshalb steht sie auch im Kommentar von decimate.
    const AUSSCHLAG_INDEX = 5003;
    const AUSSCHLAG_WERT = 987.5;
    const offsets: number[] = [];
    const avgs: number[] = [];
    for (let i = 0; i < 10_080; i += 1) {
      offsets.push(i * BUCKET_MS);
      avgs.push(i === AUSSCHLAG_INDEX ? AUSSCHLAG_WERT : 10 + (i % 7) * 0.1);
    }
    const verdichtet = decimate(samplesAt(offsets, avgs), 330);

    expect(verdichtet.map((s) => s.avg)).toContain(AUSSCHLAG_WERT);
    expect(verdichtet.find((s) => s.avg === AUSSCHLAG_WERT)?.t).toBe(
      T0 + AUSSCHLAG_INDEX * BUCKET_MS,
    );
    // Je Spalte höchstens zwei Punkte — die Verdichtung verdichtet auch wirklich.
    expect(verdichtet.length).toBeLessThanOrEqual(2 * 330);
    // Und die Zeitachse bleibt aufsteigend, sonst zöge der Pfad Zickzack.
    for (let i = 1; i < verdichtet.length; i += 1) {
      expect(verdichtet[i]!.t).toBeGreaterThanOrEqual(verdichtet[i - 1]!.t);
    }
  });

  it("gibt kleinsten und größten Punkt einer Spalte in ZEITREIHENFOLGE aus", () => {
    // BELEGT: die Reihenfolge innerhalb einer Spalte, nicht nur ihre Anwesenheit. Eine
    // feste Min-vor-Max-Ausgabe zöge den Pfad rückwärts durch die Zeit — im Bild ein
    // Zickzack, das es in den Messwerten nicht gibt.
    // ROT BEI: immer `[lowest, highest]` schieben statt nach `t` zu ordnen — der erste
    // Fall (Maximum liegt zeitlich VOR dem Minimum) wird rot.
    const maxZuerst = decimate(samplesAt([0, 1, 2, 3], [5, 50, 1, 5]), 1);
    expect(maxZuerst.map((s) => s.avg)).toEqual([50, 1]);

    const minZuerst = decimate(samplesAt([0, 1, 2, 3], [5, 1, 50, 5]), 1);
    expect(minZuerst.map((s) => s.avg)).toEqual([1, 50]);
  });

  it("lässt jeden Punkt stehen, solange die Reihe nicht mehr Punkte hat als Spalten", () => {
    // BELEGT: Bis zur Spaltenzahl geht kein Punkt verloren — auch genau AUF der Grenze
    // (Punkte == Spalten). Die zweite Hälfte (knapp darunter wird wirklich verdichtet)
    // ist die Aufbau-Kontrolle; ohne sie belegte die erste nur, dass die Funktion
    // überhaupt nie etwas tut.
    // ROT BEI: decimate immer die Eingabe zurückgeben lassen — die dritte Zusicherung
    // wird rot.
    // AUSDRÜCKLICH NICHT ROT bei `samples.length <= targetColumns` → `<`: gemessen, die
    // Gegenprobe blieb grün. Bei Spalten >= Punkten fällt je Spalte höchstens ein Punkt
    // an, und die Spaltenrechnung liefert dann Punkt für Punkt dasselbe wie die
    // Abkürzung. Der Durchreiche-Zweig ist eine Abkürzung, keine Zusicherung — die
    // Zusicherung ist der Werterhalt, und den fordert dieser Test ein.
    const samples = samplesAt(
      [0, BUCKET_MS, 2 * BUCKET_MS, 3 * BUCKET_MS, 4 * BUCKET_MS],
      [12, 18, 14, 20, 11],
    );
    expect(decimate(samples, 9)).toEqual(samples);
    // Genau auf der Grenze: fünf Punkte, fünf Spalten.
    expect(decimate(samples, 5)).toEqual(samples);
    // Knapp darunter wird wirklich verdichtet — sonst belegte der Grenzfall nur, dass
    // die Funktion überhaupt nie etwas tut.
    expect(decimate(samples, 2).length).toBeLessThan(samples.length);
  });

  it("liefert bei 0 Spalten und bei leerer Reihe kein NaN und keine leere Auswahl", () => {
    // BELEGT: die entarteten Fälle. `targetColumns = 0` entsteht aus einer Plotbreite
    // von 0 (jsdom, oder ein Panel vor dem ersten Layout) — eine Division durch null
    // schriebe NaN in die Zeitachse, und ein NaN zerstört das SVG STILL: kein Fehler,
    // kein Log, nur ein leerer Rahmen. Statt Punkte zu verlieren, bleibt die Reihe.
    // ROT BEI: den Guard `targetColumns <= 0` entfernen — das Ergebnis ist dann leer.
    const samples = samplesAt([0, BUCKET_MS, 2 * BUCKET_MS], [12, 18, 14]);
    expect(decimate(samples, 0)).toEqual(samples);
    expect(decimate(samples, -5)).toEqual(samples);
    expect(decimate([], 330)).toEqual([]);
    expect(decimate([], 0)).toEqual([]);
    for (const sample of decimate(samples, 0)) {
      expect(Number.isNaN(sample.t)).toBe(false);
    }
  });

  it("gibt eine neue Reihe zurück und lässt die Eingabe unberührt", () => {
    // BELEGT: Der Durchreiche-Fall reicht nicht das Original-Array weiter. Sonst könnte
    // eine spätere Sortierung im Diagramm die verschmolzene Reihe im Hook umsortieren,
    // und der Fehler zeigte sich erst beim nächsten Live-Push an ganz anderer Stelle.
    // ROT BEI: im Durchreiche-Zweig `return samples` statt `return [...samples]`.
    const samples = samplesAt([0, BUCKET_MS], [12, 18]);
    const durchgereicht = decimate(samples, 99);
    expect(durchgereicht).not.toBe(samples);
    expect(durchgereicht).toEqual(samples);
  });
});
