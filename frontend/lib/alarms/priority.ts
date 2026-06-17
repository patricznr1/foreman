// ============================================================
//  FOREMAN Frontend — lib/alarms/priority.ts
//  Zweck: ISA-18.2-Prioritäts-Staffelung. Die Backend-Severity ist 5-stufig
//         (info/warning/alarm/critical/emergency); die Sicht leitet daraus die
//         vier Prioritäts-Tiers + Diagnose/Journal ab (Studie §4C/§5.2). Statische
//         Klassen-Maps (Tailwind-Scanner findet keine Template-Strings).
//  Architektur-Einordnung: Reine Ableitung (Schicht 2). Ohne UI testbar.
// ============================================================
import type { AlarmSeverity } from "@/lib/api/contracts";
import type { Priority } from "./types";

/** Reihenfolge der Tiers, dringlichste zuerst (Index = Rang, 0 = höchste). */
export const PRIORITY_ORDER: readonly Priority[] = [
  "critical",
  "high",
  "medium",
  "low",
  "journal",
] as const;

/** Severity → Prioritäts-Tier. emergency UND critical fallen in den einen Rot-Tier
 *  (ISA-18.2: max. eine dominante Rot-Fläche). Unbekanntes → Journal (neutral). */
const SEVERITY_TO_PRIORITY: Record<AlarmSeverity, Priority> = {
  emergency: "critical",
  critical: "critical",
  alarm: "high",
  warning: "medium",
  info: "low",
};

export function severityToPriority(severity: string): Priority {
  return SEVERITY_TO_PRIORITY[severity as AlarmSeverity] ?? "journal";
}

/** Feinrang der Severity für stabile Sortierung INNERHALB eines Tiers (Notfall vor Kritisch). */
const SEVERITY_RANK: Record<string, number> = {
  emergency: 0,
  critical: 1,
  alarm: 2,
  warning: 3,
  info: 4,
};

export function severityRank(severity: string): number {
  return SEVERITY_RANK[severity] ?? 5;
}

export const PRIORITY_LABEL: Record<Priority, string> = {
  critical: "Kritisch",
  high: "Hoch",
  medium: "Mittel",
  low: "Niedrig",
  journal: "Journal",
};

/** Semantisches Alarm-Token je Tier (alarm-*). Nur kritisch ist vollflächig erlaubt. */
export const PRIORITY_TOKEN: Record<Priority, string> = {
  critical: "alarm-critical",
  high: "alarm-high",
  medium: "alarm-medium",
  low: "alarm-low",
  journal: "alarm-journal",
};

/** Rang eines Tiers (0 = kritisch/höchste). */
export function priorityRank(priority: Priority): number {
  return PRIORITY_ORDER.indexOf(priority);
}
