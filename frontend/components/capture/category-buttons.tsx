// ============================================================
//  FOREMAN Frontend — components/capture/category-buttons.tsx
//  Zweck: Die Werker-Kategorie als große, MEHRKANALIG kodierte Buttons (Studie
//         §4J/§5.8): Farbfläche + Form-Glyph + Klartext-Label + aria-pressed —
//         nie Farbe allein, kein Dropdown-Fummeln. Handschuh-Ziele (≥ 56 px). Der
//         Werker wählt MANUELL; ein automatischer Vorschlag ist [VISION] (nicht
//         erfunden). Aktive Fläche nutzt fg-on-accent (≥ 4.5:1 in beiden Themes,
//         gemessen), idle trägt fg-primary + farbigen Glyph (≥ 3:1 als Grafik).
//  Architektur-Einordnung: Sicht-Komponente (Schicht 3, client).
// ============================================================
"use client";

import { CLASSIFICATIONS } from "@/lib/capture/classification";
import type { Classification } from "@/lib/capture/types";
import { cx } from "@/lib/ui/cx";

// Statische Klassen-Maps, damit der Tailwind-Scanner sie findet (kein Template-String).
const ACTIVE_FILL: Record<Classification, string> = {
  routine: "bg-state-ok text-fg-on-accent",
  auffaellig: "bg-alarm-medium text-fg-on-accent",
  kritisch: "bg-alarm-critical text-fg-on-accent",
};

const IDLE_GLYPH: Record<Classification, string> = {
  routine: "text-state-ok",
  auffaellig: "text-alarm-medium",
  kritisch: "text-alarm-critical",
};

export interface CategoryButtonsProps {
  value: Classification | null;
  onChange: (value: Classification | null) => void;
  disabled?: boolean;
}

export function CategoryButtons({ value, onChange, disabled = false }: CategoryButtonsProps) {
  return (
    <div role="group" aria-label="Kategorie der Beobachtung" className="flex flex-wrap gap-3">
      {CLASSIFICATIONS.map((option) => {
        const active = value === option.id;
        return (
          <button
            key={option.id}
            type="button"
            // Optional: erneuter Tap auf die aktive Kategorie hebt die Wahl auf.
            onClick={() => onChange(active ? null : option.id)}
            disabled={disabled}
            aria-pressed={active}
            title={option.hint}
            className={cx(
              "touch-target inline-flex flex-1 basis-28 items-center justify-center gap-2 rounded-lg px-4",
              "text-body font-semibold transition-colors",
              active
                ? ACTIVE_FILL[option.id]
                : "border border-line-strong bg-surface-raised text-fg-primary",
              disabled && "opacity-50",
            )}
          >
            <span aria-hidden="true" className={cx("text-body-l", active ? "" : IDLE_GLYPH[option.id])}>
              {option.glyph}
            </span>
            <span>{option.label}</span>
          </button>
        );
      })}
    </div>
  );
}
