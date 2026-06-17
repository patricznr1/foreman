// ============================================================
//  FOREMAN Frontend — lib/prediction/factors.test.ts
//  Zweck: Faktoren in Werker-Sprache — Richtung + Gewicht farbunabhängig, und der
//         PARAPHRASE-TEST: kein Verfahrensname / kein roher Tag im Label.
// ============================================================
import { describe, expect, it } from "vitest";
import { FACTOR_DIRECTION_LABEL, humanizeFeature, toFactorRows } from "./factors";
import { SAMPLE_FACTORS } from "./testing/fixtures";

/** Verbotene Begriffe: Verfahrensname + rohe Statistik-Tags (kollidieren NICHT mit dt. Wörtern). */
const FORBIDDEN = /shap|lightgbm|gradient|boosting|__|\b(mean|slope|rms|roc|std)\b/i;

describe("humanizeFeature — Paraphrase-Disziplin", () => {
  it("übersetzt {datenpunkt}__{stat} in Hallensprache, ohne rohen Tag", () => {
    const label = humanizeFeature("bearing_temp__mean");
    expect(label).toContain("Lager");
    expect(label).toContain("Temperatur");
    expect(label).not.toContain("bearing_temp__mean");
    expect(label).not.toContain("__");
  });

  it("benennt die Sonder-Features verständlich", () => {
    expect(humanizeFeature("maint__hours_since_last")).toBe("Zeit seit der letzten Wartung");
    expect(humanizeFeature("alarm__count")).toBe("Alarme im Beobachtungszeitraum");
    expect(humanizeFeature("drift__count")).toBe("Auffälligkeiten in der Messreihe");
  });

  it("leakt fuer KEINEN realen Feature-Tag einen Verfahrensnamen / rohen Tag", () => {
    for (const f of SAMPLE_FACTORS) {
      const label = humanizeFeature(f.feature);
      expect(label).not.toMatch(FORBIDDEN);
      expect(label).not.toContain(f.feature);
      expect(label.length).toBeGreaterThan(0);
    }
  });
});

describe("toFactorRows — Richtung + relatives Gewicht (farbunabhängig)", () => {
  it("normiert das Gewicht auf den stärksten Treiber und sortiert absteigend", () => {
    const rows = toFactorRows(SAMPLE_FACTORS);
    expect(rows[0]!.weight).toBeCloseTo(1, 10); // stärkster Treiber = 1.0
    for (let i = 1; i < rows.length; i++) {
      expect(rows[i - 1]!.weight).toBeGreaterThanOrEqual(rows[i]!.weight);
    }
  });

  it("trägt die Richtung als Daten (farbunabhängig über Wort + später Pfeil)", () => {
    const rows = toFactorRows(SAMPLE_FACTORS);
    const up = rows.find((r) => r.key === "bearing_temp__mean");
    expect(up?.direction).toBe("increases_risk");
    expect(FACTOR_DIRECTION_LABEL.increases_risk).toMatch(/hoch/);
    expect(FACTOR_DIRECTION_LABEL.decreases_risk).toMatch(/senkt/);
  });

  it("lässt Faktoren ohne Gewicht (0) aus — kein Treiber", () => {
    const rows = toFactorRows([
      { feature: "bearing_temp__mean", value: 1, shap: 0, direction: "increases_risk" },
    ]);
    expect(rows).toHaveLength(0);
  });
});
