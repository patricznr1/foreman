// ============================================================
//  FOREMAN Frontend — lib/alarms/lifecycle.ts
//  Zweck: Lebenszyklus-Ableitung aus den REALEN Zeitstempeln (das Backend hat kein
//         lifecycle-Feld): cleared_at → geklärt; sonst acknowledged_at → quittiert;
//         sonst aktiv (Studie §4C). Drift-Erkennung (eigene, weichere Klasse) und
//         die erwartete Bedienhandlung je Zustand (Hallensprache).
//  Architektur-Einordnung: Reine Ableitung (Schicht 2). Ohne UI testbar.
// ============================================================
import { DRIFT_ALARM_CODE } from "@/lib/api/contracts";
import type { BaseLifecycle, DisplayLifecycle, Priority } from "./types";

interface LifecycleInput {
  cleared_at: string | null;
  acknowledged_at: string | null;
}

export function deriveBaseLifecycle(alarm: LifecycleInput): BaseLifecycle {
  if (alarm.cleared_at !== null) {
    return "cleared";
  }
  if (alarm.acknowledged_at !== null) {
    return "acknowledged";
  }
  return "active";
}

export function isDriftAlarm(alarm: { code: string | null }): boolean {
  return alarm.code === DRIFT_ALARM_CODE;
}

export const LIFECYCLE_LABEL: Record<DisplayLifecycle, string> = {
  active: "Aktiv",
  acknowledged: "Quittiert",
  cleared: "Geklärt",
  shelved: "Zurückgestellt",
};

/**
 * Erwartete Bedienhandlung (Studie §4C: „erwartete Bedienhandlung" je Zeile).
 * Hallensprache, kurz. Geklärt/quittiert/zurückgestellt schlagen die Priorität.
 */
export function expectedAction(
  priority: Priority,
  lifecycle: DisplayLifecycle,
  isDrift: boolean,
): string {
  if (lifecycle === "cleared") {
    return "Erledigt";
  }
  if (lifecycle === "shelved") {
    return "Zurückgestellt — kommt wieder";
  }
  if (lifecycle === "acknowledged") {
    return "Quittiert — Klärung abwarten";
  }
  // aktiv:
  if (isDrift) {
    return "Abweichung prüfen";
  }
  switch (priority) {
    case "critical":
      return "Sofort prüfen und quittieren";
    case "high":
      return "Zeitnah prüfen";
    case "medium":
      return "Beobachten";
    case "low":
      return "Zur Kenntnis";
    case "journal":
      return "Protokoll";
  }
}
