// ============================================================
//  FOREMAN Frontend — lib/cockpit/history.ts
//  Zweck: Kleiner reiner Ring-Puffer für die KPI-Sparklines + Trendrichtung. Das
//         Cockpit hält je Kennzahl eine kurze Live-Verlaufsspur dieser Sitzung,
//         damit die KpiTile nie nackt steht (Spark + Trend, Prinzip 6). Ehrlich:
//         es ist der Verlauf SEIT dem Öffnen, kein historisches Backend-Fenster.
//  Architektur-Einordnung: View-State (Schicht 2, rein, testbar).
// ============================================================
import type { Trend } from "@/components/atoms/kpi-tile";

/** Obergrenze der Verlaufsspur (genug für einen lesbaren Spark, ohne zu wachsen). */
export const HISTORY_CAP = 24;

/** Schwelle, ab der eine Differenz als Richtung zählt (Rauschen unterdrücken). */
const TREND_EPSILON = 1e-9;

/**
 * Hängt einen Messwert an die Spur an und kappt auf `cap` (älteste fallen weg).
 * Gibt eine NEUE Liste zurück (immutable, referenz-stabil für React).
 */
export function pushSample(history: readonly number[], value: number, cap: number = HISTORY_CAP): number[] {
  const next = [...history, value];
  if (next.length > cap) {
    return next.slice(next.length - cap);
  }
  return next;
}

/** Trendrichtung aus erstem vs. letztem Wert der Spur (flat bei zu kurzer Spur). */
export function trendOf(history: readonly number[]): Trend {
  if (history.length < 2) {
    return "flat";
  }
  const first = history[0]!;
  const last = history[history.length - 1]!;
  const delta = last - first;
  if (delta > TREND_EPSILON) {
    return "up";
  }
  if (delta < -TREND_EPSILON) {
    return "down";
  }
  return "flat";
}
