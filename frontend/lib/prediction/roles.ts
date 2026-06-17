// ============================================================
//  FOREMAN Frontend — lib/prediction/roles.ts
//  Zweck: Rollen-Varianten der Sektion E (Studie §3.1 Matrix + §4E): Werker liest
//         knapp ohne Trigger; Schichtleiter fordert an und quittiert; Techniker
//         liest mit Faktor-Detail; Manager sieht NUR das Aggregat, nie die
//         Einzelempfehlung als Befehl. Sichtbarkeit ≤ Backend-Autorisierung
//         (der Server-Guard bleibt die Autorität).
//  Architektur-Einordnung: Zugriffs-Spiegel (Schicht 2). Reine Logik.
// ============================================================
import type { Role } from "@/lib/api/contracts";

export interface PredictionRoleView {
  /** Darf eine frische Vorhersage anfordern (On-Demand-Trigger)? */
  canTrigger: boolean;
  /** Darf quittieren/verwerfen (HITL-Entscheidung)? */
  canDecide: boolean;
  /** Sieht das volle Faktor-Detail (Diagnose) statt der knappen Auswahl? */
  factorDetail: boolean;
  /** Sieht NUR das aggregierte Risikobild über Maschinen (nie die Einzelempfehlung)? */
  aggregateOnly: boolean;
}

const ROLE_VIEW: Record<Role, PredictionRoleView> = {
  // Werker: liest Empfehlung + Vorbehalt, klar und knapp, ohne Trigger.
  worker: { canTrigger: false, canDecide: false, factorDetail: false, aggregateOnly: false },
  // Schichtleiter: fordert an, quittiert.
  shift_lead: { canTrigger: true, canDecide: true, factorDetail: true, aggregateOnly: false },
  // Techniker: liest mit Faktor-Detail für die Diagnose (kein Trigger, keine Entscheidung).
  technician: { canTrigger: false, canDecide: false, factorDetail: true, aggregateOnly: false },
  // Manager: aggregiertes Risikobild über Maschinen, nie die Einzelempfehlung als Befehl.
  manager: { canTrigger: false, canDecide: false, factorDetail: false, aggregateOnly: true },
};

/** Restriktivster Default für unbekannte Backend-Rollen (default-deny). */
const DENY_VIEW: PredictionRoleView = {
  canTrigger: false,
  canDecide: false,
  factorDetail: false,
  aggregateOnly: false,
};

export function predictionRoleView(role: Role): PredictionRoleView {
  return ROLE_VIEW[role] ?? DENY_VIEW;
}
