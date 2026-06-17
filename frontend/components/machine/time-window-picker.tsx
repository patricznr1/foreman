// ============================================================
//  FOREMAN Frontend — components/machine/time-window-picker.tsx
//  Zweck: Zeitfenster-Umschalter (Schicht/Tag/Woche) für den Sensortrend (Studie §4B).
//         Monat/9 Monate (die „tiefe Zeitreise") sind [VISION] — hier bewusst nicht
//         angeboten, da die Backend-Trend-Route bei 168 h (1 Woche) deckelt.
//  Architektur-Einordnung: Steuerung (Schicht 3, client). Tastatur/Fokus, ≥56 px.
// ============================================================
"use client";

import { TIME_WINDOWS, type TimeWindowId } from "@/lib/machine/time-window";
import { cx } from "@/lib/ui/cx";

export interface TimeWindowPickerProps {
  value: TimeWindowId;
  onChange: (id: TimeWindowId) => void;
}

export function TimeWindowPicker({ value, onChange }: TimeWindowPickerProps) {
  return (
    <div role="group" aria-label="Zeitfenster" className="inline-flex gap-1 rounded-md border border-line-subtle p-1">
      {TIME_WINDOWS.map((window) => {
        const active = window.id === value;
        return (
          <button
            key={window.id}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(window.id)}
            className={cx(
              "touch-target rounded px-3 text-body",
              active ? "bg-surface-overlay text-fg-primary" : "text-fg-secondary",
            )}
          >
            {window.label}
          </button>
        );
      })}
    </div>
  );
}
