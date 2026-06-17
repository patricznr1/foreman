// ============================================================
//  FOREMAN Frontend — lib/capture/scope.ts
//  Zweck: Die client-seitig auswählbaren Maschinen — reiner UX-/Führungs-Filter,
//         KEINE AuthZ-Grenze. Der worker_notes-POST ist server-seitig NICHT
//         scope-gefiltert (§20: Per-User-Scope greift nur bei Lese-/WS-Abos); das
//         Backend nimmt jede machine_id an. Diese Beschränkung spiegelt die
//         inScope-Logik aus app/(app)/machines/page.tsx (Naht: später nach lib
//         hochziehen + dort teilen) und führt den Werker auf seine Maschinen.
//  Architektur-Einordnung: Zugriffs-Spiegel (Schicht 2). Reine Logik, testbar.
// ============================================================
import type { CurrentUser, MachineRead } from "@/lib/api/contracts";

/**
 * Liegt eine Maschine im Scope des Nutzers? manager/technician unrestricted;
 * worker → seine zugewiesenen Maschinen; shift_lead → Maschinen seiner Linien.
 * Leeres Scope-Array = kein Scope (default-deny, konsistent mit §20.4).
 */
export function machineInScope(user: CurrentUser, machine: MachineRead): boolean {
  switch (user.role) {
    case "manager":
    case "technician":
      return true;
    case "worker":
      return user.assigned_machine_ids.includes(machine.id);
    case "shift_lead":
      return machine.line_id !== null && user.assigned_line_ids.includes(machine.line_id);
    default:
      // Unbekannte Backend-Rolle (offener String) → default-deny.
      return false;
  }
}

/** Die für den Nutzer auswählbaren Maschinen (UX-Filter), Eingabereihenfolge erhalten. */
export function selectableMachines(user: CurrentUser, machines: MachineRead[]): MachineRead[] {
  return machines.filter((machine) => machineInScope(user, machine));
}

/**
 * Ist eine (z. B. aus ?machine= vorausgewählte) machine_id für den Nutzer wählbar?
 * Liegt die ID außerhalb des Scopes oder nicht in der geladenen Liste, wird sie
 * NICHT vorausgewählt — der Nutzer wählt dann selbst (graceful, kein toter Zustand).
 */
export function isMachineSelectable(
  user: CurrentUser,
  machineId: number,
  machines: MachineRead[],
): boolean {
  return selectableMachines(user, machines).some((machine) => machine.id === machineId);
}

/** Anzeige-Label einer Maschine; Fallback „Maschine {id}" ohne Stammdaten (wie B/C). */
export function machineLabel(machine: MachineRead): string {
  return machine.label.trim() || `Maschine ${machine.id}`;
}
