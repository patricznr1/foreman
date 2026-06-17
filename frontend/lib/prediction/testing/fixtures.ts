// ============================================================
//  FOREMAN Frontend — lib/prediction/testing/fixtures.ts
//  Zweck: Realistische Test-Fixtures gegen den REALEN Backend-Vertrag (F-PRED/
//         F-REC). Feature-Tags, Vorbehalt-Text und Literal-Werte exakt wie im
//         Backend, damit Tests echte Verträge prüfen, nicht Annahmen.
//  Architektur-Einordnung: Test-Hilfen (nur Tests).
// ============================================================
import type {
  FailurePredictionRead,
  TopFactor,
  WorkerRecommendationRead,
} from "@/lib/api/contracts";

/** Der deterministische Backend-Vorbehalt (reasoners/failure/schema.py:145). */
export const DETERMINISTIC_CAVEAT =
  "Diese Einschätzung beruht auf simulierten Verläufen und ist nicht an realen Ausfällen validiert.";

export const SAMPLE_FACTORS: TopFactor[] = [
  { feature: "bearing_temp__mean", value: 78.4, shap: 0.92, direction: "increases_risk" },
  { feature: "vibration_rms__slope", value: 0.13, shap: 0.61, direction: "increases_risk" },
  { feature: "maint__hours_since_last", value: 612, shap: 0.34, direction: "increases_risk" },
  { feature: "spindle_load__last_minus_mean", value: -4.1, shap: 0.18, direction: "decreases_risk" },
  { feature: "drift__count", value: 3, shap: 0.27, direction: "increases_risk" },
];

export function makePrediction(over: Partial<FailurePredictionRead> = {}): FailurePredictionRead {
  return {
    id: 101,
    machine_id: 7,
    reference_time: "2026-06-17T08:00:00+00:00",
    horizon_h: 336,
    probability: 0.82,
    decision_threshold: 0.5,
    decision: "elevated_risk",
    top_factors: SAMPLE_FACTORS,
    validation_status: "simulation_only",
    data_regime: "simulation",
    model_version: "lgbm-2026.06.01",
    created_at: "2026-06-17T08:30:00+00:00",
    ...over,
  };
}

export function makeRecommendation(
  over: Partial<WorkerRecommendationRead> = {},
): WorkerRecommendationRead {
  return {
    id: 555,
    prediction_id: 101,
    machine_id: 7,
    recommendation_text:
      "Lagertemperatur und Schwingungsverlauf an Maschine 7 in der nächsten Schicht prüfen; eine Schmierung vor dem regulären Intervall vorziehen.",
    validation_caveat: DETERMINISTIC_CAVEAT,
    validation_status: "simulation_only",
    data_regime: "simulation",
    model_version: "lgbm-2026.06.01",
    referenced_source_ids: ["pred:101", "factor:bearing_temp__mean", "factor:vibration_rms__slope"],
    horizon_h: 336,
    probability: 0.82,
    decision: "elevated_risk",
    created_at: "2026-06-17T08:30:05+00:00",
    ...over,
  };
}
