// ============================================================
//  FOREMAN Frontend — lib/memory/roles.ts
//  Zweck: Rollen-Varianten der Sektion H (Studie §3.1 Matrix + §4H): Werker sucht
//         einfach und liest grosse Karten; Schichtleiter/Techniker nutzen Filter,
//         Verknuepfung und Sprung in die Diagnose; Manager sieht zuerst Muster
//         (Verdichtung ueber Maschinen), weniger den Einzelfall. Sichtbarkeit
//         <= Backend-Autorisierung (der Server-Guard bleibt die Autoritaet).
//  Architektur-Einordnung: Zugriffs-Spiegel (Schicht 2). Reine Logik.
// ============================================================
import type { Role } from "@/lib/api/contracts";

export interface MemoryRoleView {
  /** Filter-Chips (Maschine, Zeitraum, Quelltyp) sichtbar? */
  canFilter: boolean;
  /** Verknuepfungs-Ansicht (wie Treffer zusammenhaengen) sichtbar? */
  showRelations: boolean;
  /** Manager: Muster/Verdichtung zuerst, Einzelfall sekundaer. */
  aggregateFirst: boolean;
  /** Werker: grosse, knappe Treffer-Karten. */
  largeCards: boolean;
  /** Sprung in die Diagnose (Maschine/Ereigniskette) anbieten? */
  jumpToDiagnosis: boolean;
}

const ROLE_VIEW: Record<Role, MemoryRoleView> = {
  // Werker: einfache hatten-wir-das-Suche, grosse Karten, kein Filter-Overhead.
  worker: {
    canFilter: false,
    showRelations: false,
    aggregateFirst: false,
    largeCards: true,
    jumpToDiagnosis: false,
  },
  // Schichtleiter: volle Suche ueber Bereiche, Verknuepfung, Sprung in Diagnose.
  shift_lead: {
    canFilter: true,
    showRelations: true,
    aggregateFirst: false,
    largeCards: false,
    jumpToDiagnosis: true,
  },
  // Techniker: tiefe Suche mit Detail, Verknuepfung, Sprung in Diagnose.
  technician: {
    canFilter: true,
    showRelations: true,
    aggregateFirst: false,
    largeCards: false,
    jumpToDiagnosis: true,
  },
  // Manager = Werksleiter-/Vorführ-Vollzugriff (§21.12): aggregierte Muster zuerst,
  // aber voller Zugang inkl. Sprung in die Diagnose (keine Sackgasse).
  manager: {
    canFilter: true,
    showRelations: true,
    aggregateFirst: true,
    largeCards: false,
    jumpToDiagnosis: true,
  },
};

/** Restriktivster Default fuer unbekannte Backend-Rollen (default-deny). */
const DENY_VIEW: MemoryRoleView = {
  canFilter: false,
  showRelations: false,
  aggregateFirst: false,
  largeCards: false,
  jumpToDiagnosis: false,
};

export function memoryRoleView(role: Role): MemoryRoleView {
  return ROLE_VIEW[role] ?? DENY_VIEW;
}
