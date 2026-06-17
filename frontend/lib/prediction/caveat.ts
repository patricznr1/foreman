// ============================================================
//  FOREMAN Frontend — lib/prediction/caveat.ts
//  Zweck: Block 4 (Vorbehalt) — der DETERMINISTISCHE Backend-Vorbehalt, nie im
//         Frontend formuliert (Studie §4E). NEGATIV-GUARD (Kern-Invariante §16):
//         fehlt der validation_caveat oder ist er leer, gibt es KEINE Karte — die
//         Sicht fällt in den Fehler-Zustand. Eine Vorhersage ohne ihren Vorbehalt
//         darf nie auf den Schirm.
//  Architektur-Einordnung: View-State (Schicht 2). Reine Funktion + Guard.
// ============================================================
import type { WorkerRecommendationRead } from "@/lib/api/contracts";
import type { CaveatModel } from "./types";

/** Trägt die Empfehlung einen nicht-leeren, deterministischen Vorbehalt? */
export function hasCaveat(recommendation: Pick<WorkerRecommendationRead, "validation_caveat">): boolean {
  return (
    typeof recommendation.validation_caveat === "string" &&
    recommendation.validation_caveat.trim().length > 0
  );
}

/**
 * Baut Block 4 — NUR wenn der Vorbehalt da ist. Null erzwingt im aufrufenden
 * view-model den Fehler-Zustand (nie eine vorbehaltlose Karte).
 */
export function deriveCaveat(recommendation: WorkerRecommendationRead): CaveatModel | null {
  if (!hasCaveat(recommendation)) {
    return null;
  }
  return {
    text: recommendation.validation_caveat.trim(),
    validationStatus: recommendation.validation_status,
    dataRegime: recommendation.data_regime,
  };
}

/** Enum → Hallensprache (direkte Wiedergabe der Datenlage, keine Formulierung). */
export const VALIDATION_STATUS_LABEL: Record<string, string> = {
  simulation_only: "nicht an realen Ausfällen validiert",
};

export const DATA_REGIME_LABEL: Record<string, string> = {
  simulation: "Simulation",
};

export function validationStatusLabel(status: string): string {
  return VALIDATION_STATUS_LABEL[status] ?? status;
}

export function dataRegimeLabel(regime: string): string {
  return DATA_REGIME_LABEL[regime] ?? regime;
}
