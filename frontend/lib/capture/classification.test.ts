// ============================================================
//  FOREMAN Frontend — lib/capture/classification.test.ts
//  Zweck: Sichert die Kategorie-Definitionen (Vollständigkeit, Ordnung, Guard).
// ============================================================
import { describe, expect, it } from "vitest";
import {
  CLASSIFICATIONS,
  classificationOption,
  isClassification,
} from "./classification";

describe("CLASSIFICATIONS", () => {
  it("enthält genau die drei Werker-Kategorien", () => {
    expect(CLASSIFICATIONS.map((c) => c.id)).toEqual(["routine", "auffaellig", "kritisch"]);
  });

  it("ist nach aufsteigender Dringlichkeit geordnet (routine < auffaellig < kritisch)", () => {
    const ranks = CLASSIFICATIONS.map((c) => c.rank);
    expect(ranks).toEqual([...ranks].sort((a, b) => a - b));
    expect(new Set(ranks).size).toBe(ranks.length);
  });

  it("kodiert jede Kategorie mehrkanalig: Label UND Glyph (Farbe folgt in der UI)", () => {
    for (const option of CLASSIFICATIONS) {
      expect(option.label.length).toBeGreaterThan(0);
      expect(option.glyph.length).toBeGreaterThan(0);
      expect(option.hint.length).toBeGreaterThan(0);
    }
  });

  it("verwendet KEINE internen Verfahrens-/Prozentbegriffe in sichtbaren Texten", () => {
    const visible = CLASSIFICATIONS.flatMap((c) => [c.label, c.hint]).join(" ").toLowerCase();
    for (const term of ["embedding", "vektor", "score", "%", "ki"]) {
      expect(visible.includes(term)).toBe(false);
    }
  });
});

describe("classificationOption", () => {
  it("findet die Definition zu jeder Kategorie", () => {
    expect(classificationOption("kritisch").label).toBe("Kritisch");
    expect(classificationOption("routine").rank).toBe(0);
  });
});

describe("isClassification", () => {
  it("akzeptiert die drei gültigen Werte", () => {
    expect(isClassification("routine")).toBe(true);
    expect(isClassification("auffaellig")).toBe(true);
    expect(isClassification("kritisch")).toBe(true);
  });

  it("verwirft Fremdwerte, null und undefined (URL/Storage-Härtung)", () => {
    expect(isClassification("dringend")).toBe(false);
    expect(isClassification(null)).toBe(false);
    expect(isClassification(undefined)).toBe(false);
    expect(isClassification("")).toBe(false);
  });
});
