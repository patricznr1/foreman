// ============================================================
//  FOREMAN Frontend — lib/prediction/view-model.ts
//  Zweck: Führt FailurePredictionRead (F-PRED) + WorkerRecommendationRead (F-REC)
//         zum Vier-Block-Modell zusammen (Studie §4E). Trägt die KERN-INVARIANTEN
//         als Guards: (1) der Vorbehalt ist Pflicht — fehlt er, gibt es KEINE Karte,
//         nur den Fehler-Zustand (nie eine vorbehaltlose Karte); (2) Integrität —
//         die autoritativen Zahlen der Empfehlung müssen exakt zur Vorhersage
//         passen (Client-Spiegel der Backend-Grounding-Invariante I), sonst
//         Fehler-Zustand statt einer in sich widersprüchlichen Karte.
//  Architektur-Einordnung: View-State-Komposition (Schicht 2). Reine Funktion.
// ============================================================
import type { FailurePredictionRead, WorkerRecommendationRead } from "@/lib/api/contracts";
import { deriveCaveat } from "./caveat";
import { deriveConfidence } from "./confidence";
import { toFactorRows } from "./factors";
import type { PredictionCardModel } from "./types";

export type AssembleFailure =
  | "no-prediction"
  | "no-recommendation"
  | "caveat-missing"
  | "integrity-mismatch";

export type AssembleResult =
  | { ok: true; card: PredictionCardModel }
  | { ok: false; reason: AssembleFailure };

/** Die autoritativen Zahlen müssen Empfehlung↔Vorhersage exakt teilen (Invariante I). */
function integrityHolds(
  prediction: FailurePredictionRead,
  recommendation: WorkerRecommendationRead,
): boolean {
  return (
    recommendation.prediction_id === prediction.id &&
    recommendation.machine_id === prediction.machine_id &&
    recommendation.probability === prediction.probability &&
    recommendation.decision === prediction.decision &&
    recommendation.horizon_h === prediction.horizon_h
  );
}

/**
 * Setzt die Vier-Block-Karte zusammen — oder verweigert sie begründet. Die Karte
 * existiert NUR, wenn Vorhersage UND Empfehlung da sind, der Vorbehalt nicht fehlt
 * und die Zahlen konsistent sind. Damit ist die Konfidenz (Block 1) nie ohne den
 * Vorbehalt (Block 4) sichtbar — sie werden gemeinsam gebaut oder gar nicht.
 */
export function assemblePredictionCard(
  prediction: FailurePredictionRead | null,
  recommendation: WorkerRecommendationRead | null,
): AssembleResult {
  if (prediction === null) {
    return { ok: false, reason: "no-prediction" };
  }
  if (recommendation === null) {
    return { ok: false, reason: "no-recommendation" };
  }
  // NEGATIV-GUARD (Kern): fehlt der deterministische Vorbehalt → keine Karte.
  const caveat = deriveCaveat(recommendation);
  if (caveat === null) {
    return { ok: false, reason: "caveat-missing" };
  }
  if (!integrityHolds(prediction, recommendation)) {
    return { ok: false, reason: "integrity-mismatch" };
  }
  const card: PredictionCardModel = {
    predictionId: prediction.id,
    recommendationId: recommendation.id,
    machineId: prediction.machine_id,
    horizonH: prediction.horizon_h,
    decision: prediction.decision,
    confidence: deriveConfidence(prediction),
    factors: toFactorRows(prediction.top_factors),
    recommendation: {
      text: recommendation.recommendation_text,
      sourceCount: recommendation.referenced_source_ids.length,
    },
    caveat,
    generatedAt: recommendation.created_at,
  };
  return { ok: true, card };
}

/** Hallensprache zu einem Nicht-Karte-Grund (für den Fehler-/Ruhezustand). */
export const ASSEMBLE_FAILURE_TEXT: Record<AssembleFailure, string> = {
  "no-prediction": "Noch keine Vorhersage angefordert",
  "no-recommendation": "Vorhersage liegt vor — Empfehlung noch nicht erzeugt",
  "caveat-missing": "Vorhersage ohne Vorbehalt — nicht anzeigbar (Datenfehler)",
  "integrity-mismatch": "Empfehlung passt nicht zur Vorhersage — nicht anzeigbar (Datenfehler)",
};
