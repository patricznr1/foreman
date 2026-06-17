// ============================================================
//  FOREMAN Frontend — lib/prediction/decision.ts
//  Zweck: Die menschliche HITL-Entscheidung über einer Empfehlung (Studie §4E,
//         drei Haltungen). Die Empfehlung ist ein VORSCHLAG — der Mensch quittiert
//         oder verwirft sie MIT BEGRÜNDUNG (auditierbar: wer/wann/warum). HARTE
//         GRENZE: keine Entscheidung verknüpft sich je mit einer Anlagen-Aktorik.
//         Es gibt (noch) KEINE Backend-Route → die Entscheidung wird client-seitig
//         als auditierbarer Datensatz geführt (vorbereiteter Anschlusspunkt Audit I).
//  Architektur-Einordnung: Reine Ableitung + Sicherheits-Invariante (Schicht 2).
// ============================================================
import type { RiskDecision } from "@/lib/api/contracts";
import type { PredictionCardModel } from "./types";

/** Quittiert (Empfehlung angenommen) oder verworfen (abgelehnt). */
export type DecisionDisposition = "acknowledged" | "dismissed";

/**
 * Auditierbarer Entscheidungs-Datensatz (§4E: wer/wann/warum). „Wer" entsteht
 * server-seitig, sobald die Audit-Route (Sektion I) existiert; das Frontend führt
 * Bezug, Disposition und Begründung. KEIN Anlagen-Schreibpfad.
 */
export interface DecisionRecord {
  predictionId: number;
  recommendationId: number;
  machineId: number;
  disposition: DecisionDisposition;
  /** Pflicht-Begründung bei Verwerfen und bei erhöhtem Risiko, sonst optional. */
  reason: string | null;
  /** Erfasster Zeitpunkt der Geste (Client); der autoritative Stempel kommt vom Server. */
  atIso: string;
}

/**
 * Wann ist eine Begründung Pflicht? Beim Verwerfen IMMER (man begründet, warum man
 * eine Erkenntnis verwirft) und bei erhöhtem Risiko für jede Disposition (man
 * begründet das Handeln/Nicht-Handeln). Bei geringem Risiko + Quittieren optional.
 */
export function requiresDecisionReason(
  disposition: DecisionDisposition,
  decision: RiskDecision,
): boolean {
  return disposition === "dismissed" || decision === "elevated_risk";
}

export function buildDecisionRecord(
  card: Pick<PredictionCardModel, "predictionId" | "recommendationId" | "machineId" | "decision">,
  disposition: DecisionDisposition,
  reason: string | null,
  atIso: string,
): DecisionRecord {
  const normalized = reason && reason.trim().length > 0 ? reason.trim() : null;
  // Zweite Linie zum UI-Submit-Guard: der Datensatz darf die Begründungs-Lücke nie öffnen.
  if (requiresDecisionReason(disposition, card.decision) && normalized === null) {
    throw new Error("Diese Entscheidung erfordert eine Begründung");
  }
  return {
    predictionId: card.predictionId,
    recommendationId: card.recommendationId,
    machineId: card.machineId,
    disposition,
    reason: normalized,
    atIso,
  };
}

/**
 * SICHERHEITS-INVARIANTE (Negativtest-Anker): Es existiert HEUTE keine Backend-Route
 * für die Entscheidung — sie bleibt client-seitig. `predictionDecisionEndpoint`
 * gibt darum null. Wenn die Audit-Route (Sektion I) kommt, ist nur ein
 * Audit-Append-Pfad zulässig — NIEMALS ein schaltender/Aktor-Pfad.
 */
export function predictionDecisionEndpoint(): string | null {
  return null;
}

/** Erlaubter (künftiger) Audit-Append-Pfad — nie ein Aktor-Pfad. Heute ungenutzt. */
export function isPredictionAuditActionPath(path: string): boolean {
  return /^\/api\/v1\/audit\/decisions$/.test(path);
}
