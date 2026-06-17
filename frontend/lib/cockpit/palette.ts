// ============================================================
//  FOREMAN Frontend — lib/cockpit/palette.ts
//  Zweck: Bildet die abgeleitete Zell-Kodierung auf die SEMANTISCHEN Token-Namen
//         ab (Studie §5.2). Die Komponente nutzt diese Namen direkt als
//         `var(--color-…)` im SVG — kein dynamischer Tailwind-Klassenname (umgeht die
//         Purge-Falle, FE1-Lernung). Füllung = entsättigte sequenzielle Palette;
//         Schraffur-Richtung = farbunabhängiger zweiter Kanal (Drift „bahnt sich an"
//         = diff-over/45°, Warnung „brennt" = diff-under/-45°).
//  Architektur-Einordnung: View-State (Schicht 2, rein, testbar).
// ============================================================
import type { CellKind, DeviationLevel } from "./types";

/** Semantischer Token der Zell-Füllung je Intensität (0 = ruhige Grundfläche). */
export function cellFillToken(level: DeviationLevel): string {
  return level === 0 ? "surface-raised" : `heatmap-${level}`;
}

export type HatchDirection = "over" | "under";

/**
 * Schraffur-Richtung je Zell-Art (farbunabhängiger Kanal): Drift → over (diff-over,
 * 45°), offene Warnung → under (diff-under, -45°). Normalbetrieb → keine Schraffur.
 */
export function hatchFor(kind: CellKind): HatchDirection | null {
  if (kind === "drift") {
    return "over";
  }
  if (kind === "warning") {
    return "under";
  }
  return null;
}
