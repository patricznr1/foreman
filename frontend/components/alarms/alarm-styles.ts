// ============================================================
//  FOREMAN Frontend — components/alarms/alarm-styles.ts
//  Zweck: Statische Tailwind-Klassen-Maps für die Prioritäts-Kodierung (der
//         Purge-Scanner findet keine Template-Strings — gelernte Lektion FE1).
//         ISA-101-Ruhe: nur kritisch trägt die vollflächige Rot-Kodierung (gefüllter
//         Chip + breite Kante + Puls); die übrigen Tiers sind Rand/Punkt/Label.
//  Architektur-Einordnung: Darstellungs-Tokens (Schicht 2).
// ============================================================
import type { Priority } from "@/lib/alarms/types";

/** Linke Kantenfarbe je Tier (border-alarm-*). */
export const PRIORITY_BORDER: Record<Priority, string> = {
  critical: "border-alarm-critical",
  high: "border-alarm-high",
  medium: "border-alarm-medium",
  low: "border-alarm-low",
  journal: "border-alarm-journal",
};

/** Punkt-/Flächenfarbe je Tier (bg-alarm-*). */
export const PRIORITY_DOT: Record<Priority, string> = {
  critical: "bg-alarm-critical",
  high: "bg-alarm-high",
  medium: "bg-alarm-medium",
  low: "bg-alarm-low",
  journal: "bg-alarm-journal",
};

/** Textfarbe je Tier (text-alarm-*). */
export const PRIORITY_TEXT: Record<Priority, string> = {
  critical: "text-alarm-critical",
  high: "text-alarm-high",
  medium: "text-alarm-medium",
  low: "text-alarm-low",
  journal: "text-alarm-journal",
};

/**
 * Severity-/Prioritäts-Chip (dritter Kanal: Label). Kritisch ist GEFÜLLT (die eine
 * dominante Rot-Fläche); die übrigen sind umrandet/gedämpft — kein Vollflächen-Rot.
 */
export const PRIORITY_CHIP: Record<Priority, string> = {
  critical: "bg-alarm-critical text-fg-on-accent",
  high: "border border-alarm-high text-alarm-high",
  medium: "border border-alarm-medium text-alarm-medium",
  low: "border border-alarm-low text-alarm-low",
  journal: "border border-alarm-journal text-alarm-journal",
};

/** Kritisch trägt die breitere Kante (visuelle Dominanz, ohne Dauer-Rotfläche). */
export function railWidth(priority: Priority): string {
  return priority === "critical" ? "border-l-8" : "border-l-4";
}
