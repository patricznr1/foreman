// ============================================================
//  FOREMAN Frontend — lib/event-chains/confidence.test.ts
//  Zweck: Verbale Konfidenz-Stufe — NIE als Prozent.
// ============================================================
import { describe, expect, it } from "vitest";
import { CONFIDENCE_LABEL, confidenceLabel, confidenceLevel } from "./confidence";

describe("confidence — verbale Stufe, nie Prozent", () => {
  it("mappt low/medium/high auf gering/mittel/hoch", () => {
    expect(confidenceLevel("low")).toBe("gering");
    expect(confidenceLevel("medium")).toBe("mittel");
    expect(confidenceLevel("high")).toBe("hoch");
  });

  it("kein Label trägt ein Prozentzeichen", () => {
    for (const value of ["low", "medium", "high"] as const) {
      expect(confidenceLabel(value)).not.toContain("%");
    }
    expect(CONFIDENCE_LABEL.hoch).toBe("hohe Konfidenz");
  });
});
