// ============================================================
//  FOREMAN Frontend — lib/event-chains/roles.ts
//  Zweck: Rollen-Varianten der Sektion D (Studie §3.1 Zeile D + §4D): Schichtleiter
//         rekonstruiert (Trigger); Techniker liest für die Diagnose UND pinnt an
//         die Maschine; Werker liest gespeicherte Ketten; Manager sieht NUR die
//         verdichtete Zusammenfassung (ein Satz + Kennzahl), nie die volle Erzählung.
//         Sichtbarkeit ≤ Backend-Autorisierung (Server-Guard bleibt die Autorität).
//  Architektur-Einordnung: Zugriffs-Spiegel (Schicht 2). Reine Logik.
// ============================================================
import type { Role } from "@/lib/api/contracts";

export interface ChainRoleView {
  /** Darf eine Kette rekonstruieren (On-Demand-Trigger gegen einen Anker-Alarm)? */
  canTrigger: boolean;
  /** Darf eine gespeicherte Kette an die Maschinen-Zeitachse (B) anpinnen? */
  canPin: boolean;
  /** Sieht NUR die verdichtete Zusammenfassung (Manager), nicht die volle Erzählung? */
  aggregateOnly: boolean;
}

const ROLE_VIEW: Record<Role, ChainRoleView> = {
  // Werker: liest gespeicherte Ketten (kein Trigger, kein Pin).
  worker: { canTrigger: false, canPin: false, aggregateOnly: false },
  // Schichtleiter: rekonstruiert aktiv und pinnt.
  shift_lead: { canTrigger: true, canPin: true, aggregateOnly: false },
  // Techniker: liest für die Diagnose und pinnt an die Maschine (kein Trigger).
  technician: { canTrigger: false, canPin: true, aggregateOnly: false },
  // Manager: verdichtete Zusammenfassung über Ketten, nie die volle Erzählung.
  manager: { canTrigger: false, canPin: false, aggregateOnly: true },
};

/** Restriktivster Default für unbekannte Backend-Rollen (default-deny). */
const DENY_VIEW: ChainRoleView = { canTrigger: false, canPin: false, aggregateOnly: false };

export function chainRoleView(role: Role): ChainRoleView {
  return ROLE_VIEW[role] ?? DENY_VIEW;
}
