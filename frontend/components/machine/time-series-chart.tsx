// ============================================================
//  FOREMAN Frontend — components/machine/time-series-chart.tsx
//  Zweck: Das Herzstück von Sektion B — der Sensortrend (Studie 4B/5.5). Maßge-
//         schneidertes, token-getriebenes SVG (keine Charting-Lib: hält das <100kB-
//         Erstbild-Ziel, volle Kontrolle über Mehrkanal-Kodierung, Transport-Agnostik).
//         Die X-Achsen-Domäne wird vom gewählten Zeitfenster gesetzt (startMs/endMs),
//         NICHT von den Daten -> der Live-Rand wächst rein, ohne Achsen-/Layout-Sprung.
//         Kodierung mehrkanalig (Studie 5.8): Linie (Position) + Normalband (Fläche,
//         entsättigt) + Drift (Differenzfläche diff-over/under + Schraffur-Pattern) +
//         aria-Label. Drift ist ein Akzent — NIE Alarm-Rot (Beobachtung, kein Alarm).
//         Eigenprofil-Overlay graceful: profileBand null -> kein erfundener Strich.
//  Architektur-Einordnung: Visualisierung (Schicht 3). Liest nur abgeleiteten State.
// ============================================================
import { linePath, scaleLinear, type Point } from "@/lib/machine/geometry";
import type { DriftSegment, TrendSeries } from "@/lib/machine/types";

export interface TimeSeriesChartProps {
  series: TrendSeries;
  driftSegments: DriftSegment[];
  startMs: number;
  endMs: number;
  width?: number;
  height?: number;
  reduced?: boolean;
}

const PAD = { top: 12, right: 14, bottom: 26, left: 48 } as const;

function formatNumber(value: number): string {
  return value.toLocaleString("de-DE", { maximumFractionDigits: 1 });
}

function formatTime(ms: number): string {
  return new Date(ms).toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
}

function areaPath(top: readonly Point[], bottom: readonly Point[]): string {
  if (top.length === 0) {
    return "";
  }
  const forward = top.map((p, index) => `${index === 0 ? "M" : "L"}${p.x},${p.y}`).join("");
  const back = [...bottom].reverse().map((p) => `L${p.x},${p.y}`).join("");
  return `${forward}${back}Z`;
}

export function TimeSeriesChart({
  series,
  driftSegments,
  startMs,
  endMs,
  width = 720,
  height = 220,
  reduced = false,
}: TimeSeriesChartProps) {
  const { normalMin, normalMax, samples, unit, dataPointName, dataPointId } = series;
  const hasBand = normalMin !== null && normalMax !== null;

  const xScale = scaleLinear([startMs, endMs], [PAD.left, width - PAD.right]);

  let yLow = Infinity;
  let yHigh = -Infinity;
  const consider = (value: number): void => {
    if (value < yLow) yLow = value;
    if (value > yHigh) yHigh = value;
  };
  for (const sample of samples) {
    consider(sample.min);
    consider(sample.max);
    consider(sample.avg);
  }
  if (normalMin !== null) consider(normalMin);
  if (normalMax !== null) consider(normalMax);
  if (!Number.isFinite(yLow) || !Number.isFinite(yHigh)) {
    yLow = 0;
    yHigh = 1;
  }
  const yPad = (yHigh - yLow) * 0.08 || 1;
  const yScale = scaleLinear([yLow - yPad, yHigh + yPad], [height - PAD.bottom, PAD.top]);

  const linePoints: Point[] = samples.map((sample) => ({ x: xScale(sample.t), y: yScale(sample.avg) }));
  const last = samples.at(-1) ?? null;

  const ariaParts: string[] = [`Sensortrend ${dataPointName}${unit ? ` in ${unit}` : ""}`];
  if (last) {
    ariaParts.push(`aktuell ${formatNumber(last.avg)}${unit ? ` ${unit}` : ""}`);
  }
  if (hasBand) {
    ariaParts.push(`Normalbereich ${formatNumber(normalMin)} bis ${formatNumber(normalMax)} ${unit ?? ""}`.trim());
  }
  if (driftSegments.length > 0) {
    ariaParts.push("Abweichung gegen den Normalbereich erkannt");
  }
  const ariaLabel = `${ariaParts.join(", ")}.`;

  const hatchOver = `fmn-hatch-over-${dataPointId}`;
  const hatchUnder = `fmn-hatch-under-${dataPointId}`;

  return (
    <svg
      role="img"
      aria-label={ariaLabel}
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className="h-auto w-full"
    >
      <defs>
        <pattern id={hatchOver} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="6" stroke="var(--color-diff-over)" strokeWidth="1.4" />
        </pattern>
        <pattern id={hatchUnder} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
          <line x1="0" y1="0" x2="0" y2="6" stroke="var(--color-diff-under)" strokeWidth="1.4" />
        </pattern>
      </defs>

      {hasBand ? (
        <rect
          data-testid="normal-band"
          x={PAD.left}
          y={yScale(normalMax)}
          width={width - PAD.left - PAD.right}
          height={Math.max(0, yScale(normalMin) - yScale(normalMax))}
          fill="var(--color-data-normalband)"
        />
      ) : null}

      {/* Eigenprofil-Overlay (F4): profile_band ist Backend-seitig reserviert/null →
          graceful WEGGELASSEN, kein Platzhalter-Strich. Sobald F4 ein Band liefert,
          hier eine gestrichelte Referenzlinie aus dem Band ableiten (Anschlusspunkt). */}

      {driftSegments.map((segment, index) => {
        const boundary = segment.direction === "over" ? normalMax : normalMin;
        if (boundary === null) {
          return null;
        }
        const top: Point[] = segment.samples.map((s) => ({ x: xScale(s.t), y: yScale(s.avg) }));
        const bottom: Point[] = segment.samples.map((s) => ({ x: xScale(s.t), y: yScale(boundary) }));
        const d = areaPath(top, bottom);
        const color = segment.direction === "over" ? "var(--color-diff-over)" : "var(--color-diff-under)";
        const hatch = segment.direction === "over" ? hatchOver : hatchUnder;
        return (
          <g key={`${segment.direction}-${segment.fromT}-${index}`}>
            <path data-testid={`drift-${segment.direction}`} d={d} fill={color} fillOpacity={0.22} />
            <path d={d} fill={`url(#${hatch})`} />
          </g>
        );
      })}

      <path
        data-testid="trend-line"
        d={linePath(linePoints)}
        fill="none"
        stroke="var(--color-data-series-1)"
        strokeWidth={2}
        strokeLinejoin="round"
        strokeLinecap="round"
      />

      {last ? <circle cx={xScale(last.t)} cy={yScale(last.avg)} r={3} fill="var(--color-data-series-1)" /> : null}

      <text x={PAD.left} y={height - 8} fill="var(--color-fg-muted)" fontSize="11">
        {formatTime(startMs)}
      </text>
      <text x={width - PAD.right} y={height - 8} textAnchor="end" fill="var(--color-fg-muted)" fontSize="11">
        {formatTime(endMs)}
      </text>

      {!reduced && hasBand ? (
        <text x={4} y={yScale(normalMax) + 4} fill="var(--color-fg-muted)" fontSize="11">
          {formatNumber(normalMax)}
        </text>
      ) : null}
    </svg>
  );
}
