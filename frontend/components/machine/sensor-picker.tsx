// ============================================================
//  FOREMAN Frontend — components/machine/sensor-picker.tsx
//  Zweck: Sensorauswahl für den Mehrfach-Sensor-Trend (ein-/ausblenden, gestapelt).
//         `max` begrenzt die Auswahl für die reduzierte Werker-Variante (Studie §4B:
//         „reduzierte Sensorauswahl"). Mehrkanalig: Zustand über aria-pressed + Stil,
//         nicht nur Farbe. Keine Hover-only-Funktion.
//  Architektur-Einordnung: Steuerung (Schicht 3, client).
// ============================================================
"use client";

import type { DataPointRead } from "@/lib/api/contracts";
import { cx } from "@/lib/ui/cx";

export interface SensorPickerProps {
  dataPoints: DataPointRead[];
  selected: number[];
  onToggle: (id: number) => void;
  /** Obergrenze gleichzeitig gewählter Sensoren (reduzierte Variante). */
  max?: number;
}

export function SensorPicker({ dataPoints, selected, onToggle, max }: SensorPickerProps) {
  const selectedSet = new Set(selected);
  return (
    <div role="group" aria-label="Sensoren" className="flex flex-wrap gap-2">
      {dataPoints.map((dataPoint) => {
        const active = selectedSet.has(dataPoint.id);
        const atLimit = !active && max !== undefined && selected.length >= max;
        return (
          <button
            key={dataPoint.id}
            type="button"
            aria-pressed={active}
            disabled={atLimit}
            onClick={() => onToggle(dataPoint.id)}
            className={cx(
              "touch-target rounded-md border px-3 text-body",
              active ? "border-line-strong text-fg-primary" : "border-line-subtle text-fg-secondary",
              atLimit ? "opacity-50" : "",
            )}
          >
            {dataPoint.name}
            {dataPoint.unit ? ` (${dataPoint.unit})` : ""}
          </button>
        );
      })}
    </div>
  );
}
