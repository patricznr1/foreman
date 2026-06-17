// ============================================================
//  FOREMAN Frontend — lib/prediction/confidence.ts
//  Zweck: Block 1 (Konfidenz) ehrlich ableiten (Studie §4E/§1.3). KEINE
//         Scheingenauigkeit (kein „87,3 %"): grobe verbale Stufe + bewusst
//         vergröbertes Wahrscheinlichkeitsband relativ zum Schwellwert. Der
//         Backend-Vertrag liefert nur einen Punktwert → es wird KEIN gemessenes
//         Unsicherheits-Intervall erfunden (coarse=true). Die echte Unsicherheit
//         trägt der Vorbehalt-Block.
//  Architektur-Einordnung: View-State (Schicht 2). Reine Funktion.
// ============================================================
import type { FailurePredictionRead } from "@/lib/api/contracts";
import type { ConfidenceLevel, ConfidenceModel } from "./types";

/** Breite des groben Bandes (10 Prozentpunkte) — Vergröberung gegen Scheingenauigkeit. */
const BAND_WIDTH = 0.1;

/** Auf den unteren 10-PP-Bucket vergröbern (z. B. 0.873 → [0.8, 0.9]). */
function coarseBand(probability: number): { low: number; high: number } {
  const clamped = Math.min(Math.max(probability, 0), 1);
  // Untergrenze nie über 0.9, damit auch p=1.0 ein sichtbares Band [0.9, 1.0] behält.
  const low = Math.min(Math.floor(clamped * 10) / 10, 1 - BAND_WIDTH);
  return { low, high: low + BAND_WIDTH };
}

/**
 * Grobe verbale Stufe, schwellwert-bewusst und konsistent zur Backend-Entscheidung:
 * unter Schwellwert → „gering" (decision normal); über Schwellwert → „erhöht",
 * deutlich darüber (≥ halber Abstand Schwellwert→1) → „hoch".
 */
export function confidenceLevel(probability: number, threshold: number): ConfidenceLevel {
  if (probability < threshold) {
    return "gering";
  }
  const highCut = threshold + (1 - threshold) * 0.5;
  return probability >= highCut ? "hoch" : "erhoeht";
}

export function deriveConfidence(prediction: FailurePredictionRead): ConfidenceModel {
  const band = coarseBand(prediction.probability);
  return {
    level: confidenceLevel(prediction.probability, prediction.decision_threshold),
    bandLow: band.low,
    bandHigh: band.high,
    threshold: prediction.decision_threshold,
    overThreshold: prediction.decision === "elevated_risk",
    coarse: true,
  };
}

/** Anzeige-Label der verbalen Stufe (Hallensprache). */
export const CONFIDENCE_LEVEL_LABEL: Record<ConfidenceLevel, string> = {
  gering: "geringes Risiko",
  erhoeht: "erhöhtes Risiko",
  hoch: "hohes Risiko",
};
