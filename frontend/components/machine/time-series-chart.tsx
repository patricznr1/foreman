// ============================================================
//  FOREMAN Frontend — components/machine/time-series-chart.tsx
//  Zweck: Das Herzstück von Sektion B — der Sensortrend (Studie 4B/5.5). Maßge-
//         schneidertes, token-getriebenes SVG (keine Charting-Lib: hält das <100kB-
//         Erstbild-Ziel, volle Kontrolle über Mehrkanal-Kodierung, Transport-Agnostik).
//         Die X-Achsen-Domäne wird vom sichtbaren Ausschnitt gesetzt (startMs/endMs),
//         NICHT von den Daten -> der Live-Rand wächst rein, ohne Achsen-/Layout-Sprung.
//         Die Y-Domäne folgt dagegen der SICHTBAREN Scheibe (durch `niceDomain`
//         gerastert) — sonst bliebe ein 20-Minuten-Ausschnitt eine platte Linie.
//         Kodierung mehrkanalig (Studie 5.8): Linie (Position) + Normalband (Fläche,
//         entsättigt) + Drift (Differenzfläche diff-over/under + Schraffur-Pattern) +
//         Minutenpunkte samt Min-Max-Hülle beim Hineinzoomen + aria-Label. Drift ist
//         ein Akzent — NIE Alarm-Rot (Beobachtung, kein Alarm).
//         Eigenprofil-Overlay graceful: profileBand null -> kein erfundener Strich.
//         Vier Gründe für leere Fläche tragen VIER Marken mit vier verschiedenen
//         Texten (nicht abgerufen / älter als die Aufbewahrung / kein Messwert /
//         gekappt): eine stumme leere Fläche behauptet gegenüber dem Werker „keine
//         Störung", wo in Wahrheit niemand gefragt hat.
//         Reine Renderfunktion, ohne Hooks — der Ausschnitt wird oben gehalten.
//  Architektur-Einordnung: Visualisierung (Schicht 3). Liest nur abgeleiteten State.
// ============================================================
import {
  envelopePath,
  linePath,
  niceDomain,
  scaleLinear,
  type Point,
} from "@/lib/machine/geometry";
import { BUCKET_MS } from "@/lib/machine/time-window";
import { DEFAULT_MAX_GAP_MS, decimate, splitAtGaps, visibleSlice } from "@/lib/machine/trend-series";
import type { DriftSegment, TrendSample, TrendSeries } from "@/lib/machine/types";
import { DOT_MIN_PX_PER_BUCKET, MAX_SPAN_MS, describeSpan, snapMs } from "@/lib/machine/viewport";

export interface TimeSeriesChartProps {
  series: TrendSeries;
  driftSegments: DriftSegment[];
  startMs: number;
  endMs: number;
  width?: number;
  height?: number;
  /**
   * Rollen-Dichte der Detailsicht (`roleView.sensorDetail`), NICHT
   * prefers-reduced-motion. Die Wert-Achse trägt ihre beiden Domänen-Enden
   * seit der freien Skalierung dauerhaft — eine Sicht ohne vertikale Referenz
   * bei springender Skala wäre skalenblind —, deshalb steuert die Dichte in
   * diesem Baustein nichts. Die Requisite bleibt, weil die aufrufende Sicht
   * sie führt und andere Bausteine sie auswerten.
   */
  reduced?: boolean;
  /** Der Live-Rand. Fällt auf `endMs` zurück: dann steht der Ausschnitt am Jetzt. */
  nowMs?: number;
  /**
   * Anfang des zuletzt ERFOLGREICH beantworteten Ladefensters. Links davon wurde
   * nicht gefragt — diese Fläche wird schraffiert, statt Abdeckung zu behaupten.
   */
  loadedFromMs?: number | null;
  /** Eine Anfrage läuft, während bereits Punkte im Bild stehen. */
  refetching?: boolean;
}

const PAD = { top: 12, right: 14, bottom: 26, left: 48 } as const;

/**
 * Die vier Gründe für leere Fläche in vier Sätzen. Sie stehen beieinander, weil
 * ihre VERSCHIEDENHEIT die eigentliche Zusicherung ist: „noch nicht abgerufen",
 * „gibt es nicht", „kein Messwert" und „gekappt" meinen vier verschiedene Dinge.
 * Sie zu einem Text zusammenzufassen wäre bequem und falsch; ein Test hält sie
 * paarweise auseinander.
 */
const MARK_TEXT = {
  unloaded: "noch nicht abgerufen",
  loading: "wird geladen …",
  // „über diese Ansicht": Die Route pinnt das Fensterende auf jetzt und nimmt nur
  // eine Stundenzahl. Was in der Datenbank liegt, weiß diese Sicht nicht.
  retentionWall: `Älter als ${describeSpan(MAX_SPAN_MS)}: kein Verlauf über diese Ansicht`,
  gap: "kein Messwert",
  truncatedRight: "Neueste Punkte gekappt",
} as const;

function formatNumber(value: number): string {
  return value.toLocaleString("de-DE", { maximumFractionDigits: 1 });
}

/** Datum UND Uhrzeit — für das aria-Label, das den Ausschnitt eindeutig benennen muss. */
function formatMoment(ms: number): string {
  const d = new Date(ms);
  const date = d.toLocaleDateString("de-DE", { day: "2-digit", month: "2-digit" });
  const time = d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  return `${date} ${time}`;
}

/** Ab dieser Spanne trägt eine reine Uhrzeit die Achse nicht mehr (12 Stunden). */
const DATUM_AB_MS = 12 * 60 * 60 * 1000;

/**
 * Beschriftung der Zeitachse — Datum, sobald die SPANNE oder das ALTER des
 * beschrifteten Zeitpunkts zwölf Stunden erreicht.
 *
 * WARUM DIE SPANNE: Bei einem Tages- oder Wochenfenster liegen Anfang und Ende
 * fast auf derselben Uhrzeit. Die Achse las sich dann als „08:15 bis 08:16" — der
 * Verlauf schien die letzte Minute zu zeigen, während er in Wahrheit eine Woche
 * zeigte. Die Angabe war nicht falsch, aber sie führte in die Irre, und zwar in
 * genau die Richtung, in der eine Fehlinterpretation teuer ist: Ein Ausschlag über
 * eine Woche ist etwas ganz anderes als einer über eine Minute.
 *
 * WARUM ZUSÄTZLICH DAS ALTER: Seit der Ausschnitt frei in der Vergangenheit stehen
 * kann, ist ein „08:12" von vorletztem Dienstag von heute morgen nicht zu
 * unterscheiden — bei einer Spanne von zwanzig Minuten trüge die Spanne allein
 * diese Unterscheidung nicht.
 *
 * Es bleibt EINE Regel aus Zahlen: kein Schalter, den ein Aufrufer setzt. Eine
 * zweite Quelle für die Spanne liefe der ersten davon; das Alter des beschrifteten
 * Zeitpunkts ist keine solche zweite Quelle.
 */
function formatTime(ms: number, spanMs: number, nowMs: number): string {
  const d = new Date(ms);
  if (spanMs < DATUM_AB_MS && nowMs - ms < DATUM_AB_MS) {
    return d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
  }
  return d.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** Ein Loch zwischen zwei gezeichneten Zügen — die Marke sitzt genau dazwischen. */
interface Gap {
  fromMs: number;
  toMs: number;
}

export function TimeSeriesChart({
  series,
  driftSegments,
  startMs,
  endMs,
  width = 720,
  height = 220,
  nowMs,
  loadedFromMs = null,
  refetching = false,
}: TimeSeriesChartProps) {
  const { normalMin, normalMax, samples, unit, dataPointName, dataPointId } = series;
  const hasBand = normalMin !== null && normalMax !== null;

  const now = nowMs ?? endMs;
  const spanMs = endMs - startMs;
  const plotWidth = Math.max(0, width - PAD.left - PAD.right);
  const plotHeight = Math.max(0, height - PAD.top - PAD.bottom);

  const xScale = scaleLinear([startMs, endMs], [PAD.left, width - PAD.right]);

  // Reihenfolge ZWINGEND: zuschneiden -> an Löchern trennen -> je Zug verdichten.
  // Die Verdichtung LÄSST PUNKTE WEG (sie behält je Spalte nur die Extreme). Liefe
  // sie vor dem Trennen, überschritte der Abstand der übrig gebliebenen Nachbarn
  // regelmäßig das Loch-Kriterium, und die Marke behauptete „kein Messwert" über
  // Zeit, in der gemessen wurde — ausgerechnet die Marke, die gegen erfundene
  // Aussagen über leere Fläche gebaut ist, wäre dann selbst eine.
  const visible = visibleSlice(samples, startMs, endMs);
  const rawSegments = splitAtGaps(visible, DEFAULT_MAX_GAP_MS);
  const drawSegments = rawSegments.map((segment) => decimate(segment, Math.round(plotWidth / 2)));

  // Die Löcher kommen aus den UNVERDICHTETEN Zügen: die Verdichtung behält die
  // Extreme je Spalte, nicht zwingend den ersten und letzten Punkt eines Zuges.
  const gaps: Gap[] = [];
  for (let index = 1; index < rawSegments.length; index += 1) {
    const before = rawSegments[index - 1]?.at(-1);
    const after = rawSegments[index]?.[0];
    if (before !== undefined && after !== undefined) {
      gaps.push({ fromMs: before.t, toMs: after.t });
    }
  }

  // Y-Domäne aus der SICHTBAREN Scheibe: das Normalband immer (ohne es hätte die
  // Driftfläche keinen Bezug), vom Eigenprofil nur die sichtbaren Punkte.
  let yLow = Infinity;
  let yHigh = -Infinity;
  const consider = (value: number): void => {
    if (value < yLow) yLow = value;
    if (value > yHigh) yHigh = value;
  };
  for (const sample of visible) {
    consider(sample.min);
    consider(sample.max);
    consider(sample.avg);
  }
  if (normalMin !== null) consider(normalMin);
  if (normalMax !== null) consider(normalMax);
  if (series.profileBand) {
    for (const bandPoint of series.profileBand.points) {
      if (bandPoint.t < startMs || bandPoint.t > endMs) {
        continue;
      }
      consider(bandPoint.lower);
      consider(bandPoint.upper);
    }
  }
  if (!Number.isFinite(yLow) || !Number.isFinite(yHigh)) {
    yLow = 0;
    yHigh = 1;
  }
  const [yMin, yMax] = niceDomain(yLow, yHigh);
  const yScale = scaleLinear([yMin, yMax], [height - PAD.bottom, PAD.top]);

  // Ab sechs Pixeln je Bucket zeigen Punkte und Min-Max-Hülle, was wirklich gemessen
  // wurde: zwischen zwei Punkten liegt keine Beobachtung. Gerechnet aus der
  // `width`-REQUISITE, nicht aus gemessenen Pixeln — sonst wäre es ohne Layout
  // (und damit im Test) nicht entscheidbar.
  const bucketsInView = Math.max(1, spanMs / BUCKET_MS);
  const showBuckets = plotWidth / bucketsInView >= DOT_MIN_PX_PER_BUCKET;

  const showVeil = loadedFromMs !== null && loadedFromMs > startMs;
  const veilRightX = loadedFromMs === null ? PAD.left : xScale(loadedFromMs);
  const wallMs = now - MAX_SPAN_MS;
  const showWall = wallMs >= startMs && wallMs <= endMs;
  const showNowEdge = now >= startMs && now <= endMs;
  const behindMs = now - endMs;
  const following = behindMs <= snapMs(spanMs);

  const last = samples.at(-1) ?? null;

  const ariaParts: string[] = [
    `Sensortrend ${dataPointName}${unit ? ` in ${unit}` : ""}`,
    `Ausschnitt ${formatMoment(startMs)} bis ${formatMoment(endMs)}`,
    `Spanne ${describeSpan(spanMs)}`,
    // Das Zustandswort steht im Label, weil ein Bild, das aussieht wie jetzt und es
    // nicht ist, ohne Sicht auf die Statuszeile sonst nicht zu bemerken wäre.
    following ? "folgt dem Live-Rand" : "steht fest",
    // Bei JEDEM Zoomgrad: feiner als eine Minute gibt es nichts, egal wie nah man geht.
    "Auflösung 1 Minute je Punkt",
  ];
  if (last) {
    ariaParts.push(`aktuell ${formatNumber(last.avg)}${unit ? ` ${unit}` : ""}`);
  }
  if (hasBand) {
    ariaParts.push(`Normalbereich ${formatNumber(normalMin)} bis ${formatNumber(normalMax)} ${unit ?? ""}`.trim());
  }
  if (series.profileBand) {
    ariaParts.push("Eigenprofil-Erwartungskorridor eingeblendet");
  }
  if (driftSegments.length > 0) {
    ariaParts.push("Abweichung gegen den Normalbereich erkannt");
  }
  if (showVeil) {
    ariaParts.push(`linker Rand ${refetching ? MARK_TEXT.loading : MARK_TEXT.unloaded}`);
  }
  if (series.truncated) {
    ariaParts.push(MARK_TEXT.truncatedRight);
  }
  const ariaLabel = `${ariaParts.join(", ")}.`;

  const hatchOver = `fmn-hatch-over-${dataPointId}`;
  const hatchUnder = `fmn-hatch-under-${dataPointId}`;
  const hatchUnloaded = `fmn-hatch-unloaded-${dataPointId}`;
  const plotClip = `fmn-plot-clip-${dataPointId}`;

  return (
    <svg
      role="img"
      aria-label={ariaLabel}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className="h-auto w-full"
    >
      <defs>
        {/* Beschneidet JEDE Datenschicht auf die Zeichenfläche. Ohne sie malt eine
            Schicht beim Hineinzoomen über die Achsen- und Wertbeschriftung — im
            Wochen-Erstbild fällt das nie auf, weil dort nichts über den Rand ragt. */}
        <clipPath id={plotClip}>
          <rect x={PAD.left} y={PAD.top} width={plotWidth} height={plotHeight} />
        </clipPath>
        <pattern id={hatchOver} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="6" stroke="var(--color-diff-over)" strokeWidth="1.4" />
        </pattern>
        <pattern id={hatchUnder} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
          <line x1="0" y1="0" x2="0" y2="6" stroke="var(--color-diff-under)" strokeWidth="1.4" />
        </pattern>
        <pattern id={hatchUnloaded} width="8" height="8" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="8" stroke="var(--color-line-subtle)" strokeWidth="1.2" />
        </pattern>
      </defs>

      <g data-testid="data-layers" clipPath={`url(#${plotClip})`}>
        {hasBand ? (
          <rect
            data-testid="normal-band"
            x={PAD.left}
            y={yScale(normalMax)}
            width={plotWidth}
            height={Math.max(0, yScale(normalMin) - yScale(normalMax))}
            fill="var(--color-data-normalband)"
          />
        ) : null}

        {/* F4-Eigenprofil-Overlay: gestrichelter Erwartungskorridor je Zustand (Median +
            Korridorgrenzen) — eigener, gestrichelter Token, klar unterscheidbar von der
            Vollflächen-Normalband-Schicht. Null → graceful weggelassen (kein Strich). */}
        {series.profileBand ? (
          <g data-testid="profile-band">
            <path
              data-testid="profile-band-upper"
              d={linePath(
                series.profileBand.points.map((p) => ({ x: xScale(p.t), y: yScale(p.upper) })),
              )}
              fill="none"
              stroke="var(--color-data-series-2)"
              strokeWidth={1}
              strokeDasharray="4 3"
              opacity={0.75}
            />
            <path
              d={linePath(
                series.profileBand.points.map((p) => ({ x: xScale(p.t), y: yScale(p.lower) })),
              )}
              fill="none"
              stroke="var(--color-data-series-2)"
              strokeWidth={1}
              strokeDasharray="4 3"
              opacity={0.75}
            />
            <path
              data-testid="profile-band-mid"
              d={linePath(
                series.profileBand.points.map((p) => ({ x: xScale(p.t), y: yScale(p.mid) })),
              )}
              fill="none"
              stroke="var(--color-data-series-2)"
              strokeWidth={1.5}
              strokeDasharray="2 3"
            />
          </g>
        ) : null}

        {driftSegments.map((segment, index) => {
          const boundary = segment.direction === "over" ? normalMax : normalMin;
          if (boundary === null) {
            return null;
          }
          const top: Point[] = segment.samples.map((s) => ({ x: xScale(s.t), y: yScale(s.avg) }));
          const bottom: Point[] = segment.samples.map((s) => ({ x: xScale(s.t), y: yScale(boundary) }));
          const d = envelopePath(top, bottom);
          const color = segment.direction === "over" ? "var(--color-diff-over)" : "var(--color-diff-under)";
          const hatch = segment.direction === "over" ? hatchOver : hatchUnder;
          return (
            <g key={`${segment.direction}-${segment.fromT}-${index}`}>
              <path data-testid={`drift-${segment.direction}`} d={d} fill={color} fillOpacity={0.22} />
              <path d={d} fill={`url(#${hatch})`} />
            </g>
          );
        })}

        {/* Min-Max-Hülle des Buckets: der Mittelwert ist NICHT das Signal — zwischen
            Minimum und Maximum einer Minute liegt, was die Linie verschweigt. */}
        {showBuckets
          ? drawSegments.map((segment, index) => (
              <path
                key={`envelope-${index}`}
                data-testid="bucket-envelope"
                d={envelopePath(
                  segment.map((s) => ({ x: xScale(s.t), y: yScale(s.max) })),
                  segment.map((s) => ({ x: xScale(s.t), y: yScale(s.min) })),
                )}
                fill="var(--color-data-series-1)"
                fillOpacity={0.18}
              />
            ))
          : null}

        {/* Ein Zug je lückenlosem Abschnitt: die Linie endet dort, wo die Messung endet. */}
        {drawSegments.map((segment, index) => (
          <path
            key={`line-${index}`}
            data-testid="trend-line"
            d={linePath(segment.map((s) => ({ x: xScale(s.t), y: yScale(s.avg) })))}
            fill="none"
            stroke="var(--color-data-series-1)"
            strokeWidth={2}
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ))}

        {showBuckets
          ? drawSegments.map((segment, segmentIndex) =>
              segment.map((sample: TrendSample) => (
                <circle
                  key={`dot-${segmentIndex}-${sample.bucket}`}
                  data-testid="sample-dot"
                  cx={xScale(sample.t)}
                  cy={yScale(sample.avg)}
                  r={1.8}
                  fill="var(--color-data-series-1)"
                />
              )),
            )
          : null}

        {last ? <circle cx={xScale(last.t)} cy={yScale(last.avg)} r={3} fill="var(--color-data-series-1)" /> : null}

        {/* Marke 1 — nicht abgerufen: links davon hat niemand gefragt. */}
        {showVeil ? (
          <g data-testid="mark-unloaded">
            <rect
              x={PAD.left}
              y={PAD.top}
              width={Math.max(0, veilRightX - PAD.left)}
              height={plotHeight}
              fill={`url(#${hatchUnloaded})`}
            />
            <text x={PAD.left + 4} y={PAD.top + 14} fill="var(--color-fg-muted)" fontSize="11">
              {refetching ? MARK_TEXT.loading : MARK_TEXT.unloaded}
            </text>
          </g>
        ) : null}

        {/* Marke 2 — die Aufbewahrungswand: dahinter liefert diese Ansicht nichts. */}
        {showWall ? (
          <g data-testid="mark-retention-wall">
            <line
              x1={xScale(wallMs)}
              y1={PAD.top}
              x2={xScale(wallMs)}
              y2={height - PAD.bottom}
              stroke="var(--color-line-strong)"
              strokeWidth={1.5}
              strokeDasharray="5 3"
            />
            <text x={xScale(wallMs) + 4} y={PAD.top + 28} fill="var(--color-fg-muted)" fontSize="11">
              {MARK_TEXT.retentionWall}
            </text>
          </g>
        ) : null}

        {/* Marke 3 — echtes Loch in den Messwerten, je Loch eine eigene Marke. */}
        {gaps.map((gap) => (
          <g key={`gap-${gap.fromMs}`} data-testid="mark-gap">
            <rect
              x={xScale(gap.fromMs)}
              y={PAD.top}
              width={Math.max(0, xScale(gap.toMs) - xScale(gap.fromMs))}
              height={plotHeight}
              fill="var(--color-line-subtle)"
              fillOpacity={0.45}
            />
            <text
              x={(xScale(gap.fromMs) + xScale(gap.toMs)) / 2}
              y={PAD.top + 14}
              textAnchor="middle"
              fill="var(--color-fg-muted)"
              fontSize="11"
            >
              {MARK_TEXT.gap}
            </text>
          </g>
        ))}

        {/* Marke 4 — gekappt, und zwar RECHTS: die Route ordnet aufsteigend und
            begrenzt, gekappt werden also die NEUESTEN Punkte. */}
        {series.truncated ? (
          <g data-testid="mark-truncated-right">
            <line
              x1={width - PAD.right}
              y1={PAD.top}
              x2={width - PAD.right}
              y2={height - PAD.bottom}
              stroke="var(--color-note-caveat)"
              strokeWidth={2}
              strokeDasharray="3 3"
            />
            <text
              x={width - PAD.right - 4}
              y={PAD.top + 14}
              textAnchor="end"
              fill="var(--color-fg-muted)"
              fontSize="11"
            >
              {MARK_TEXT.truncatedRight}
            </text>
          </g>
        ) : null}

        {showNowEdge ? (
          <line
            data-testid="now-edge"
            x1={xScale(now)}
            y1={PAD.top}
            x2={xScale(now)}
            y2={height - PAD.bottom}
            stroke="var(--color-line-strong)"
            strokeWidth={1}
          />
        ) : null}

        {/* Der Live-Rand liegt rechts außerhalb — der Abstand zählt sichtbar hoch. */}
        {!showNowEdge && behindMs > 0 ? (
          <g data-testid="mark-newer-offscreen">
            <text
              x={width - PAD.right - 4}
              y={PAD.top + 28}
              textAnchor="end"
              fill="var(--color-fg-muted)"
              fontSize="11"
            >
              {`${describeSpan(behindMs)} hinter dem Live-Rand`}
            </text>
          </g>
        ) : null}
      </g>

      {/* Achsen- und Wertbeschriftung stehen AUSSERHALB der Clip-Gruppe: sie gehören
          zum Rahmen, nicht zu den Daten. */}
      <text x={PAD.left} y={height - 8} fill="var(--color-fg-muted)" fontSize="11">
        {formatTime(startMs, spanMs, now)}
      </text>
      <text x={width - PAD.right} y={height - 8} textAnchor="end" fill="var(--color-fg-muted)" fontSize="11">
        {formatTime(endMs, spanMs, now)}
      </text>

      {/* Beide Domänen-Enden, dauerhaft: die Wert-Achse skaliert mit dem Ausschnitt,
          und ohne Bezifferung sähe derselbe Ausschlag an zwei Schiebepositionen
          verschieden groß aus, ohne dass es jemand nachprüfen könnte. */}
      <text data-testid="y-max" x={4} y={yScale(yMax) + 9} fill="var(--color-fg-muted)" fontSize="11">
        {formatNumber(yMax)}
      </text>
      <text data-testid="y-min" x={4} y={yScale(yMin) - 2} fill="var(--color-fg-muted)" fontSize="11">
        {formatNumber(yMin)}
      </text>
    </svg>
  );
}
