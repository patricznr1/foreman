// ============================================================
//  FOREMAN Frontend — lib/machine/time-window.ts
//  Zweck: Wählbare Trend-Zeitfenster (Studie §4B: Schicht/Tag/Woche). Die Backend-
//         Trend-Route (`/machines/{id}/trend`) deckelt bei 168 h (1 Woche) — Monat
//         und 9 Monate (die „tiefe Zeitreise") sind [VISION] und werden hier bewusst
//         NICHT angeboten (kein Fenster, das das Backend nicht bedienen kann).
//  Architektur-Einordnung: View-State (Schicht 2, rein).
// ============================================================

export type TimeWindowId = "shift" | "day" | "week";

export interface TimeWindow {
  id: TimeWindowId;
  label: string;
  hours: number;
}

/** Obergrenze der Backend-Trend-Route (`hours` 1–168). */
export const MAX_BACKEND_HOURS = 168;

const SHIFT: TimeWindow = { id: "shift", label: "Schicht", hours: 8 };
const DAY: TimeWindow = { id: "day", label: "Tag", hours: 24 };
const WEEK: TimeWindow = { id: "week", label: "Woche", hours: 168 };

export const TIME_WINDOWS: readonly TimeWindow[] = [SHIFT, DAY, WEEK];

export const DEFAULT_TIME_WINDOW: TimeWindowId = "day";

/** Löst eine Fenster-ID auf (Fallback: Tag). */
export function timeWindow(id: TimeWindowId): TimeWindow {
  return TIME_WINDOWS.find((window) => window.id === id) ?? DAY;
}

/** Startgrenze (Epoche ms) des Fensters relativ zu `nowMs`. */
export function windowStartMs(nowMs: number, hours: number): number {
  return nowMs - hours * 3600 * 1000;
}
