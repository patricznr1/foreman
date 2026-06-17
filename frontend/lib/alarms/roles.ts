// ============================================================
//  FOREMAN Frontend — lib/alarms/roles.ts
//  Zweck: Rollen-Varianten der Alarm-Sicht (Matrix 3.1, Studie §4C). Werker: eigener
//         Bereich, lesen+filtern, KEIN Quittieren. Schichtleiter: voll, Quittieren/
//         Eskalieren ist Default. Techniker: zugewiesene, offline lesbar, Quittieren.
//         Manager: nur Zähler/Trends, KEIN Einzel-Quittieren. Sichtbarkeit ≤ Server-
//         Autorisierung — das ist ein UX-Spiegel, KEINE Auth-Grenze (die hält der
//         Server; generische GET /alarms-Route ist noch nicht scope-gefiltert →
//         markierter Anschlusspunkt).
//  Architektur-Einordnung: Reine Ableitung (Schicht 2). Ohne UI testbar.
// ============================================================
import type { CurrentUser, Role } from "@/lib/api/contracts";

/** Scope-Achse der sichtbaren Alarme je Rolle (UX-Filter über dem Eigenprofil). */
export type AlarmScope = "assigned-machines" | "own-lines" | "all";

export interface AlarmRoleView {
  /** Darf Einzelalarme quittieren/eskalieren/zurückstellen (HITL). */
  canAcknowledge: boolean;
  /** Sieht nur Aggregat (Zähler/Trends), keine Einzelliste (Manager). */
  aggregateOnly: boolean;
  /** Sichtbarer Maschinen-Scope (UX-Filter). */
  scope: AlarmScope;
  /** Default-Aktion ist Quittieren (Schichtleiter) — beeinflusst die Hervorhebung. */
  acknowledgeIsDefault: boolean;
}

const ROLE_VIEW: Record<Role, AlarmRoleView> = {
  worker: {
    canAcknowledge: false,
    aggregateOnly: false,
    scope: "assigned-machines",
    acknowledgeIsDefault: false,
  },
  shift_lead: {
    canAcknowledge: true,
    aggregateOnly: false,
    scope: "own-lines",
    acknowledgeIsDefault: true,
  },
  technician: {
    canAcknowledge: true,
    aggregateOnly: false,
    scope: "assigned-machines",
    acknowledgeIsDefault: false,
  },
  manager: {
    canAcknowledge: false,
    aggregateOnly: true,
    scope: "all",
    acknowledgeIsDefault: false,
  },
};

/** Defensiv: unbekannte Backend-Rolle → restriktivste Sicht (default-deny). Scope
 *  „assigned-machines" mit (typischerweise leerer) Zuweisungsliste zeigt nichts —
 *  konsistent mit dem Default-Deny-Versprechen, nicht „all". */
const FALLBACK_VIEW: AlarmRoleView = {
  canAcknowledge: false,
  aggregateOnly: true,
  scope: "assigned-machines",
  acknowledgeIsDefault: false,
};

export function alarmRoleView(role: Role): AlarmRoleView {
  return ROLE_VIEW[role] ?? FALLBACK_VIEW;
}

export function canAcknowledgeAlarms(role: Role): boolean {
  return alarmRoleView(role).canAcknowledge;
}

/**
 * Ist eine Maschine im sichtbaren Scope der Rolle? Reiner UX-Filter (der Server
 * bleibt die Autorität). Manager/„all" sehen alles; Werker/Techniker nur
 * zugewiesene Maschinen; Schichtleiter seine Linien (über die Maschinen der Linie).
 */
export function machineInScope(
  user: Pick<CurrentUser, "role" | "assigned_machine_ids" | "assigned_line_ids">,
  machineId: number,
  machineLineId: number | null,
): boolean {
  const view = alarmRoleView(user.role);
  switch (view.scope) {
    case "all":
      return true;
    case "assigned-machines":
      return user.assigned_machine_ids.includes(machineId);
    case "own-lines":
      return machineLineId !== null && user.assigned_line_ids.includes(machineLineId);
  }
}
