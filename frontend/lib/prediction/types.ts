// ============================================================
//  FOREMAN Frontend — lib/prediction/types.ts
//  Zweck: Das abgeleitete Vier-Block-View-Modell der Ausfallvorhersage (Sektion E,
//         Studie §4E): Konfidenz → Einflussfaktoren → Empfehlung → Vorbehalt.
//         Transport-agnostisch; aus FailurePredictionRead + WorkerRecommendationRead
//         zusammengeführt (view-model.ts). Trägt NIE einen Verfahrensnamen und nie
//         eine Scheingenauigkeit.
//  Architektur-Einordnung: View-State (Schicht 2). Reine Daten.
// ============================================================
import type { FactorDirection, RiskDecision } from "@/lib/api/contracts";

/** Grobe verbale Konfidenz-Stufe — bewusst dreistufig, keine Scheingenauigkeit. */
export type ConfidenceLevel = "gering" | "erhoeht" | "hoch";

/**
 * Block 1 — Konfidenz. Der Backend-Vertrag liefert NUR einen Punktwert; ein echtes
 * Unsicherheits-Band gibt es nicht. `coarse=true` markiert das ehrlich: das Band ist
 * eine bewusste VERGRÖBERUNG gegen Scheingenauigkeit (kein gemessenes Intervall),
 * die eigentliche Unsicherheit trägt der Vorbehalt-Block.
 */
export interface ConfidenceModel {
  level: ConfidenceLevel;
  /** Untergrenze des groben Bandes [0,1] (gerundete Anzeige, kein Messintervall). */
  bandLow: number;
  /** Obergrenze des groben Bandes [0,1]. */
  bandHigh: number;
  /** Kostensensitiver Schwellwert [0,1] — Markierungslinie. */
  threshold: number;
  /** decision === "elevated_risk": Band liegt über dem Schwellwert. */
  overThreshold: boolean;
  /** true = Punktwert grob dargestellt (keine erfundene Bandbreite). */
  coarse: boolean;
}

/** Block 2 — ein Einflussfaktor in Werker-Sprache (Faktor-Methode unbenannt). */
export interface FactorRow {
  /** Technischer Tag — NUR Schlüssel/Test-Anker, NIE gerendert. */
  key: string;
  /** Paraphrasiertes Werker-Label (Hallensprache, kein Verfahrensname). */
  label: string;
  direction: FactorDirection;
  /** Relatives Gewicht [0,1], normiert auf den stärksten Treiber (farbunabhängige Balkenlänge). */
  weight: number;
}

/** Block 3 — die Empfehlung (immer Vorschlag, nie Befehl). */
export interface RecommendationModel {
  text: string;
  /** Anzahl belegter Quellen (UI zeigt nur die Zahl, keine internen IDs). */
  sourceCount: number;
}

/**
 * Block 4 — der untrennbare Vorbehalt. `text` ist der DETERMINISTISCHE Backend-Satz
 * (validation_caveat, wörtlich) — das Frontend formuliert ihn NIE selbst.
 */
export interface CaveatModel {
  text: string;
  validationStatus: string;
  dataRegime: string;
}

/** Das vollständige Vier-Block-Modell einer Karte (Konfidenz ⊕ Vorbehalt untrennbar). */
export interface PredictionCardModel {
  predictionId: number;
  recommendationId: number;
  machineId: number;
  horizonH: number;
  decision: RiskDecision;
  confidence: ConfidenceModel;
  factors: FactorRow[];
  recommendation: RecommendationModel;
  caveat: CaveatModel;
  /** ISO-Stand der Erkenntnis (Zeitpunkt der Empfehlung). */
  generatedAt: string;
}

/**
 * Prediction + Empfehlung als On-Demand-Ergebnis-Paar. `recommendation` ist NICHT
 * nullable: der Hook (use-prediction) löst nur mit einem VOLLSTÄNDIGEN Paar auf —
 * nie eine nackte Vorhersage. (Der defensive null-Guard in view-model bleibt als
 * eigener Vertrag der reinen Funktion bestehen, falls sie anders aufgerufen wird.)
 */
export interface PredictionPair {
  prediction: import("@/lib/api/contracts").FailurePredictionRead;
  recommendation: import("@/lib/api/contracts").WorkerRecommendationRead;
}
