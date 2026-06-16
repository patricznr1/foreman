// ============================================================
//  FOREMAN Frontend — components/atoms/kpi-tile.tsx
//  Zweck: KPI-Kachel (§5.5, Prinzip 6) — Wert NIE nackt: immer mit Label,
//         Zustands-Indikator und Trendrichtung/Spark. Tabellenziffern, damit
//         Live-Werte beim Update nicht springen (§5.3).
//  Architektur-Einordnung: Atom (Schicht 2). Rein präsentational.
// ============================================================
import type { Fcsm } from "@/lib/ui/wording";
import { StatusIndicator } from "./status-indicator";

export type Trend = "up" | "down" | "flat";

export interface KpiTileProps {
  label: string;
  value: number | string;
  unit?: string;
  /** Zustands-Indikator (mehrkanalig) — macht die Zahl deutbar. */
  status?: Fcsm;
  trend?: Trend;
  /** Verlaufs-Spark (entsättigt). Optional — sonst trägt der Zustand die Deutung. */
  spark?: number[];
  className?: string;
}

const TREND_GLYPH: Record<Trend, string> = { up: "↑", down: "↓", flat: "→" };
const TREND_LABEL: Record<Trend, string> = {
  up: "steigend",
  down: "fallend",
  flat: "gleichbleibend",
};

function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

function Sparkline({ values }: { values: number[] }) {
  const width = 72;
  const height = 22;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * width;
      const y = height - ((value - min) / range) * height;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      aria-hidden="true"
      className="shrink-0"
    >
      <polyline
        points={points}
        fill="none"
        stroke="var(--color-data-series-1)"
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function KpiTile({ label, value, unit, status, trend, spark, className }: KpiTileProps) {
  const hasSpark = spark !== undefined && spark.length > 1;
  return (
    <div
      className={cx(
        "flex flex-col gap-2 rounded-lg border border-line-subtle bg-surface-raised p-4",
        className,
      )}
    >
      <span className="text-caption text-fg-muted">{label}</span>
      <div className="flex items-baseline gap-2">
        <span className="text-kpi font-semibold leading-none tabular-nums text-fg-primary">
          {value}
        </span>
        {unit ? <span className="text-body text-fg-secondary">{unit}</span> : null}
        {trend ? (
          <span className="text-body text-fg-secondary" aria-label={`Trend ${TREND_LABEL[trend]}`}>
            {TREND_GLYPH[trend]}
          </span>
        ) : null}
      </div>
      <div className="flex items-center justify-between gap-3">
        {status ? <StatusIndicator status={status} size="s" /> : <span aria-hidden="true" />}
        {hasSpark ? <Sparkline values={spark} /> : null}
      </div>
    </div>
  );
}
