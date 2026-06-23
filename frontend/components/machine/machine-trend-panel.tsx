// ============================================================
//  FOREMAN Frontend — components/machine/machine-trend-panel.tsx
//  Zweck: Ein Sensor-Trendpanel — verdrahtet useMachineTrend (Pull + Live) mit dem
//         TimeSeriesChart in der Fünf-Zustände-Hülle, plus Herkunftsstempel (live/
//         gecacht mit Stand). Mehrere Sensoren werden als gestapelte Panels gezeigt
//         (gemeinsames Zeitfenster) — Studie §4B „eine oder gestapelte Sensorkurven".
//  Architektur-Einordnung: Sicht-Baustein (Schicht 3, client).
// ============================================================
"use client";

import { ProvenanceStamp } from "@/components/atoms/provenance-stamp";
import type { DataPointRead } from "@/lib/api/contracts";
import { useMachineTrend } from "@/lib/machine/use-machine-trend";
import { FiveState } from "@/lib/ui/five-states";

import { TimeSeriesChart } from "./time-series-chart";

export interface MachineTrendPanelProps {
  machineId: number;
  dataPoint: DataPointRead;
  hours: number;
  reduced?: boolean;
  nowMs?: number;
}

/** Profil-Stand (computed_at) lesbar — ehrlich als „Stand", keine Live-Aktualität. */
function formatProfileStand(ms: number): string {
  return new Date(ms).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" });
}

export function MachineTrendPanel({
  machineId,
  dataPoint,
  hours,
  reduced = false,
  nowMs,
}: MachineTrendPanelProps) {
  const { state, startMs, endMs, stampedAt } = useMachineTrend({
    machineId,
    dataPointId: dataPoint.id,
    dataPointName: dataPoint.name,
    hours,
    nowMs,
  });

  const unitSuffix = dataPoint.unit ? ` (${dataPoint.unit})` : "";

  return (
    <figure className="flex flex-col gap-2 rounded-lg border border-line-subtle bg-surface-raised p-4">
      <figcaption className="text-body text-fg-primary">
        {dataPoint.name}
        {unitSuffix}
      </figcaption>
      <FiveState state={state} label={`Trend ${dataPoint.name}`}>
        {(data, freshness) => (
          <div className="flex flex-col gap-2">
            <TimeSeriesChart
              series={data.series}
              driftSegments={data.driftSegments}
              startMs={startMs}
              endMs={endMs}
              reduced={reduced}
            />
            <div className="flex items-center justify-between gap-2">
              {data.series.profileBand ? (
                <span data-testid="profile-stamp" className="text-caption text-fg-muted">
                  Eigenprofil · Stand {formatProfileStand(data.series.profileBand.computedAt)}
                </span>
              ) : null}
              <ProvenanceStamp freshness={freshness} stampedAt={stampedAt} className="ml-auto" />
            </div>
          </div>
        )}
      </FiveState>
    </figure>
  );
}
