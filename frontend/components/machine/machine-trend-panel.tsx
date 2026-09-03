// ============================================================
//  FOREMAN Frontend — components/machine/machine-trend-panel.tsx
//  Zweck: Ein Sensor-Trendpanel — verdrahtet useMachineTrend (Pull + Live) mit dem
//         TimeSeriesChart in der Fünf-Zustände-Hülle, plus Herkunftsstempel (live/
//         gecacht mit Stand). Mehrere Sensoren werden als gestapelte Panels gezeigt
//         (gemeinsamer Ausschnitt) — Studie §4B „eine oder gestapelte Sensorkurven".
//         Seit dem 02.09.2026 ist der Ausschnitt frei zoom- und schiebbar; das Panel
//         umschliesst den Chart mit der Gestenflaeche und loest den Ausschnitt SELBST
//         nach startMs/endMs auf. Genau hier und nicht im Hook: Nur so waechst der
//         Live-Rand bei einem WS-Push weiter, ohne dass die Detailsicht eine tickende
//         Uhr braucht.
//  Architektur-Einordnung: Sicht-Baustein (Schicht 3, client).
// ============================================================
"use client";

import { ProvenanceStamp } from "@/components/atoms/provenance-stamp";
import type { DataPointRead } from "@/lib/api/contracts";
import { useMachineTrend } from "@/lib/machine/use-machine-trend";
import { type TrendViewport, resolveViewport } from "@/lib/machine/viewport";
import { FiveState } from "@/lib/ui/five-states";

import { TimeSeriesChart } from "./time-series-chart";
import { TrendViewportSurface } from "./trend-viewport-surface";

export interface MachineTrendPanelProps {
  machineId: number;
  dataPoint: DataPointRead;
  /** Der GETEILTE Ausschnitt aller gestapelten Panels. */
  viewport: TrendViewport;
  /** Abzurufende Stunden (Vertrag 1–168) — monoton nachgezogen von useTimeViewport. */
  hours: number;
  /**
   * Gesten der Flaeche gehen UNVERAENDERT nach oben. Die Flaeche dreht das
   * Vorzeichen aus `gesture.ts` bereits genau einmal (Zeigerweg nach rechts →
   * Ausschnitt in die Vergangenheit). Wer hier ein zweites Mal dreht, laesst den
   * Inhalt der Hand entgegenlaufen — und das faellt erst am Geraet auf.
   */
  onPan: (fraction: number) => void;
  onZoom: (factor: number, anchorFraction: number) => void;
  onGestureEnd: () => void;
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
  viewport,
  hours,
  onPan,
  onZoom,
  onGestureEnd,
  reduced = false,
  nowMs,
}: MachineTrendPanelProps) {
  const { state, loadedFromMs, refetching, stampedAt } = useMachineTrend({
    machineId,
    dataPointId: dataPoint.id,
    dataPointName: dataPoint.name,
    hours,
  });

  const now = nowMs ?? Date.now();
  const { startMs, endMs } = resolveViewport(viewport, now);

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
            <TrendViewportSurface
              viewport={viewport}
              nowMs={now}
              onPan={onPan}
              onZoom={onZoom}
              onGestureEnd={onGestureEnd}
            >
              <TimeSeriesChart
                series={data.series}
                driftSegments={data.driftSegments}
                startMs={startMs}
                endMs={endMs}
                nowMs={now}
                loadedFromMs={loadedFromMs}
                refetching={refetching}
                reduced={reduced}
              />
            </TrendViewportSurface>
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
