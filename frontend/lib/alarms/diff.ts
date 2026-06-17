// ============================================================
//  FOREMAN Frontend — lib/alarms/diff.ts
//  Zweck: Live-Insert ohne Sprung (Studie §4C/§3.2). Der WS pusht KEINE Alarm-
//         Zeilen, nur Aggregat-Signale → die Sicht lädt bei Signal nach und
//         bestimmt per ID-Diff, welche Alarme FRISCH sind. Nur die bekommen den
//         einmaligen Einblend-Puls; die Liste sortiert nicht neu/springt nicht.
//         Erstladung (prev = null) markiert NICHTS als neu (kein Puls-Gewitter).
//  Architektur-Einordnung: Reine Ableitung (Schicht 2). Ohne UI testbar.
// ============================================================
import type { AlarmRead } from "@/lib/api/contracts";

export function idSet(alarms: readonly AlarmRead[]): Set<number> {
  return new Set(alarms.map((a) => a.id));
}

/**
 * IDs in `next`, die in `prev` noch nicht vorkamen. `prev = null` (Erstladung) →
 * leere Menge: die initiale Liste pulst nicht, nur echte Neuzugänge.
 */
export function diffNewIds(
  prev: ReadonlySet<number> | null,
  next: readonly AlarmRead[],
): Set<number> {
  if (prev === null) {
    return new Set();
  }
  const fresh = new Set<number>();
  for (const alarm of next) {
    if (!prev.has(alarm.id)) {
      fresh.add(alarm.id);
    }
  }
  return fresh;
}
