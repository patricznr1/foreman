// ============================================================
//  FOREMAN Frontend — lib/prediction/confidence.test.ts
//  Zweck: Konfidenz ehrlich — keine Scheingenauigkeit, grobes Band + verbale Stufe.
// ============================================================
import { describe, expect, it } from "vitest";
import { confidenceLevel, deriveConfidence } from "./confidence";
import { makePrediction } from "./testing/fixtures";

describe("deriveConfidence — keine Scheingenauigkeit", () => {
  it("trägt KEINEN Prozent-Punktwert, nur ein grobes Band + verbale Stufe", () => {
    const c = deriveConfidence(makePrediction({ probability: 0.873, decision_threshold: 0.5 }));
    // Kein Feld, das die rohe Wahrscheinlichkeit als Scheingenauigkeit durchreicht.
    expect(c).not.toHaveProperty("probability");
    expect(c.coarse).toBe(true);
    expect(c.level).toBe("hoch");
  });

  it("vergröbert den Punktwert auf einen 10-PP-Bucket (0.873 → [0.8, 0.9])", () => {
    const c = deriveConfidence(makePrediction({ probability: 0.873 }));
    expect(c.bandLow).toBeCloseTo(0.8, 10);
    expect(c.bandHigh).toBeCloseTo(0.9, 10);
  });

  it("hält auch bei p=1.0 ein sichtbares Band [0.9, 1.0]", () => {
    const c = deriveConfidence(makePrediction({ probability: 1, decision_threshold: 0.5 }));
    expect(c.bandLow).toBeCloseTo(0.9, 10);
    expect(c.bandHigh).toBeCloseTo(1, 10);
  });

  it("hält bei p=0.0 ein Band [0.0, 0.1]", () => {
    const c = deriveConfidence(makePrediction({ probability: 0, decision_threshold: 0.5, decision: "normal" }));
    expect(c.bandLow).toBeCloseTo(0, 10);
    expect(c.bandHigh).toBeCloseTo(0.1, 10);
  });
});

describe("confidenceLevel — dreistufig, schwellwert-bewusst", () => {
  it("unter Schwellwert → gering", () => {
    expect(confidenceLevel(0.4, 0.5)).toBe("gering");
  });
  it("knapp über Schwellwert → erhöht", () => {
    expect(confidenceLevel(0.6, 0.5)).toBe("erhoeht");
  });
  it("deutlich über Schwellwert (≥ halber Abstand zu 1) → hoch", () => {
    expect(confidenceLevel(0.8, 0.5)).toBe("hoch");
  });
  it("Stufe gering gilt genau dann, wenn die Wahrscheinlichkeit unter dem Schwellwert liegt", () => {
    expect(confidenceLevel(0.49, 0.5)).toBe("gering");
    expect(confidenceLevel(0.5, 0.5)).not.toBe("gering");
  });
});
