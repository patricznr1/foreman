// ============================================================
//  FOREMAN Frontend — lib/prediction/caveat.test.ts
//  Zweck: Der Vorbehalt-Guard — vorhanden/leer, deterministischer Text vom Backend.
// ============================================================
import { describe, expect, it } from "vitest";
import { deriveCaveat, hasCaveat } from "./caveat";
import { DETERMINISTIC_CAVEAT, makeRecommendation } from "./testing/fixtures";

describe("hasCaveat / deriveCaveat", () => {
  it("erkennt einen vorhandenen deterministischen Vorbehalt", () => {
    const rec = makeRecommendation();
    expect(hasCaveat(rec)).toBe(true);
    expect(deriveCaveat(rec)?.text).toBe(DETERMINISTIC_CAVEAT);
  });

  it("gibt bei leerem Vorbehalt null zurück (erzwingt später den Fehler-Zustand)", () => {
    expect(hasCaveat(makeRecommendation({ validation_caveat: "" }))).toBe(false);
    expect(hasCaveat(makeRecommendation({ validation_caveat: "   " }))).toBe(false);
    expect(deriveCaveat(makeRecommendation({ validation_caveat: "" }))).toBeNull();
  });

  it("der Vorbehalt-Text wird wörtlich vom Backend übernommen, nicht formuliert", () => {
    const text = "Eigener Backend-Satz zum Validierungsstatus.";
    expect(deriveCaveat(makeRecommendation({ validation_caveat: text }))?.text).toBe(text);
  });
});
