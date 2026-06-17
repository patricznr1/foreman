// ============================================================
//  FOREMAN Frontend — lib/memory/relevance.test.ts
//  Zweck: Relevanz als ordinale Stärke aus der Rang-Position — und KEIN Prozent.
// ============================================================
import { describe, expect, it } from "vitest";
import { STRENGTH_LABEL, STRENGTH_PIPS, strengthFromRank } from "./relevance";

describe("strengthFromRank", () => {
  it("ein einziger Treffer ist stark (er ist der ähnlichste)", () => {
    expect(strengthFromRank(0, 1)).toBe("stark");
  });

  it("stuft oben/mitte/unten über die Drittelung der Liste", () => {
    const total = 9;
    expect(strengthFromRank(0, total)).toBe("stark");
    expect(strengthFromRank(2, total)).toBe("stark");
    expect(strengthFromRank(4, total)).toBe("mittel");
    expect(strengthFromRank(8, total)).toBe("entfernt");
  });

  it("die Pip-Anzahl ist der farbunabhängige zweite Kanal (3/2/1)", () => {
    expect(STRENGTH_PIPS.stark).toBe(3);
    expect(STRENGTH_PIPS.mittel).toBe(2);
    expect(STRENGTH_PIPS.entfernt).toBe(1);
  });

  it("kein Label trägt ein Prozentzeichen (keine Scheingenauigkeit)", () => {
    for (const label of Object.values(STRENGTH_LABEL)) {
      expect(label).not.toMatch(/%/);
      expect(label).not.toMatch(/\d/);
    }
  });
});
