// ============================================================
//  FOREMAN Frontend — lib/machine/roles.ts
//  Zweck: Rollen-Varianten der Maschinen-Detail-Sicht (Matrix 3.1, ACCESS_MATRIX.B
//         = worker reduced / shift_lead full / technician full / manager reduced;
//         Studie §4B). Werker: lesen + Notiz, reduzierte Sensoren. Schichtleiter:
//         voll, fordert Vorhersage an, quittiert. Techniker: Diagnose-Tiefe +
//         Offline-Cache. Manager: nur Aggregat, keine Einzelaktion. Sichtbarkeit
//         bleibt ≤ Server-Autorisierung (Guard requireSection("B")).
//  Architektur-Einordnung: View-State (Schicht 2, rein).
// ============================================================
import type { Role } from "@/lib/api/contracts";

export interface MachineRoleView {
  /** Notiz erfassen (→ J). */
  canCaptureNote: boolean;
  /** Vorhersage anfordern (→ E, On-Demand-Trigger) — nur Schichtleiter. */
  canRequestPrediction: boolean;
  /** Maschinen-Alarme quittieren (HITL, über die C-Wiederverwendung). */
  canAcknowledge: boolean;
  /** Sensor-Dichte: reduziert (Werker) vs. voll (Schichtleiter/Techniker). */
  sensorDetail: "reduced" | "full";
  /** Faktor-/Diagnose-Bezug (Techniker-Tiefe). */
  factorContext: boolean;
  /** Nur verdichtetes Bild, keine Einzelaktion (Manager). */
  aggregateOnly: boolean;
  /** Offline lesbar mit Stand-Stempel (Techniker, mobil). */
  offlineCache: boolean;
}

const ROLE_VIEW: Record<Role, MachineRoleView> = {
  worker: {
    canCaptureNote: true,
    canRequestPrediction: false,
    canAcknowledge: false,
    sensorDetail: "reduced",
    factorContext: false,
    aggregateOnly: false,
    offlineCache: false,
  },
  shift_lead: {
    canCaptureNote: true,
    canRequestPrediction: true,
    canAcknowledge: true,
    sensorDetail: "full",
    factorContext: true,
    aggregateOnly: false,
    offlineCache: false,
  },
  technician: {
    canCaptureNote: true,
    canRequestPrediction: false,
    canAcknowledge: true,
    sensorDetail: "full",
    factorContext: true,
    aggregateOnly: false,
    offlineCache: true,
  },
  manager: {
    canCaptureNote: false,
    canRequestPrediction: false,
    canAcknowledge: false,
    sensorDetail: "reduced",
    factorContext: false,
    aggregateOnly: true,
    offlineCache: false,
  },
};

/** Defensiver Fallback (unbekannte Rolle → nur lesen, reduziert). */
const FALLBACK_VIEW: MachineRoleView = {
  canCaptureNote: false,
  canRequestPrediction: false,
  canAcknowledge: false,
  sensorDetail: "reduced",
  factorContext: false,
  aggregateOnly: false,
  offlineCache: false,
};

export function machineRoleView(role: Role): MachineRoleView {
  return ROLE_VIEW[role] ?? FALLBACK_VIEW;
}
