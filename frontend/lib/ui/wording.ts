// ============================================================
//  FOREMAN Frontend — lib/ui/wording.ts
//  Zweck: Sichtbares UI-Wording in HALLENSPRACHE (Paraphrase-Disziplin, Studie 0/1.3):
//         FCSM-Zustände (NE 107), komponierter Maschinenstatus und Alarm-Severity
//         als kurze deutsche Labels — KEIN internes Vokabular, keine Verfahrensnamen.
//  Architektur-Einordnung: Darstellungs-Wording (Schicht 1).
// ============================================================
import type { MachineStatus } from "../api/contracts";

/** NAMUR NE 107 — kanonisches Zustandsmodell (kennt der Techniker vom Feldgerät). */
export type Fcsm = "failure" | "check" | "outofspec" | "maintenance" | "ok";

export const FCSM_LABEL: Record<Fcsm, string> = {
  failure: "Ausfall",
  check: "Funktionsprüfung",
  outofspec: "Außerhalb Spezifikation",
  maintenance: "Wartung nötig",
  ok: "Normal",
};

/** Zweiter, farbunabhängiger Kanal: das gelernte FCSM-Kürzel (Form/Label). */
export const FCSM_LETTER: Record<Fcsm, string> = {
  failure: "F",
  check: "C",
  outofspec: "S",
  maintenance: "M",
  ok: "OK",
};

/** Semantisches Farb-Token je FCSM-Zustand (state-*). */
export const FCSM_TOKEN: Record<Fcsm, string> = {
  failure: "state-failure",
  check: "state-check",
  outofspec: "state-outofspec",
  maintenance: "state-maintenance",
  ok: "state-ok",
};

/** Komponierter Maschinenstatus (Backend) → Hallensprache. */
export const MACHINE_STATUS_LABEL: Record<MachineStatus, string> = {
  healthy: "Normalbetrieb",
  drift_active: "Abweichung erkannt",
  open_warning: "Offene Warnung",
  critical: "Kritischer Alarm",
};

/** Komponierter Status → FCSM-Indikator (Severity-Rampe ok → S → C → F). */
export const MACHINE_STATUS_TO_FCSM: Record<MachineStatus, Fcsm> = {
  healthy: "ok",
  drift_active: "outofspec",
  open_warning: "check",
  critical: "failure",
};

/** Alarm-Severity (ISA-18.2) → Hallensprache. */
const SEVERITY_LABEL: Record<string, string> = {
  emergency: "Notfall",
  critical: "Kritisch",
  alarm: "Alarm",
  high: "Hoch",
  warning: "Warnung",
  medium: "Mittel",
  low: "Niedrig",
  info: "Hinweis",
  journal: "Journal",
};

export function severityLabel(key: string): string {
  return SEVERITY_LABEL[key] ?? key;
}
