// ============================================================
//  FOREMAN Frontend — lib/prediction/view-model.test.ts
//  Zweck: Vier-Block-Komposition + KERN-NEGATIV-GUARD: fehlt der Vorbehalt, gibt
//         es KEINE Karte (Fehler-Zustand) — nie eine vorbehaltlose Vorhersage.
// ============================================================
import { describe, expect, it } from "vitest";
import { DETERMINISTIC_CAVEAT, makePrediction, makeRecommendation } from "./testing/fixtures";
import { assemblePredictionCard } from "./view-model";

describe("assemblePredictionCard — Erfolg", () => {
  it("führt Vorhersage + Empfehlung zur Vier-Block-Karte zusammen", () => {
    const result = assemblePredictionCard(makePrediction(), makeRecommendation());
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    const { card } = result;
    expect(card.confidence.level).toBe("hoch");
    expect(card.factors.length).toBeGreaterThan(0);
    expect(card.recommendation.text.length).toBeGreaterThan(0);
    expect(card.caveat.text).toBe(DETERMINISTIC_CAVEAT);
  });
});

describe("assemblePredictionCard — KERN-NEGATIV-GUARD (Vorbehalt Pflicht)", () => {
  it("verweigert die Karte, wenn der validation_caveat fehlt/leer ist", () => {
    const result = assemblePredictionCard(
      makePrediction(),
      makeRecommendation({ validation_caveat: "" }),
    );
    expect(result).toEqual({ ok: false, reason: "caveat-missing" });
  });

  it("zeigt NIE eine nackte Vorhersage ohne Empfehlung", () => {
    expect(assemblePredictionCard(makePrediction(), null)).toEqual({
      ok: false,
      reason: "no-recommendation",
    });
  });

  it("ohne Vorhersage → kein Block 1", () => {
    expect(assemblePredictionCard(null, makeRecommendation())).toEqual({
      ok: false,
      reason: "no-prediction",
    });
  });
});

describe("assemblePredictionCard — Integritäts-Guard (Invariante I)", () => {
  it("verweigert die Karte, wenn die Zahlen Empfehlung↔Vorhersage divergieren", () => {
    const result = assemblePredictionCard(
      makePrediction({ probability: 0.82 }),
      makeRecommendation({ probability: 0.40 }),
    );
    expect(result).toEqual({ ok: false, reason: "integrity-mismatch" });
  });

  it("verweigert die Karte bei fremder prediction_id-Verknüpfung", () => {
    const result = assemblePredictionCard(
      makePrediction({ id: 101 }),
      makeRecommendation({ prediction_id: 999 }),
    );
    expect(result).toEqual({ ok: false, reason: "integrity-mismatch" });
  });
});
