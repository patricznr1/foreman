// ============================================================
//  FOREMAN Frontend — lib/cockpit/palette.test.ts
//  Zweck: KONTRAST GEMESSEN, NICHT GERATEN (§5.2/§5.8). Sichert die verbindlichen
//         Eigenschaften der Heatmap-Palette gegen tokens/contrast:
//         (1) sequenziell, kein Regenbogen — Luminanz streng monoton je Theme
//             (Reihenfolge perzeptuell erhalten, farbsehschwäche-sicher);
//         (2) nur Auffälliges sticht — die lauten Stufen (4/5) ≥ 3:1 gegen die
//             ruhige Grundfläche, die leisen Stufen treten bewusst zurück;
//         (3) Mehrkanal robust — der haloed FCSM-Buchstabe (fg-primary + neutraler
//             surface-canvas-Strich) ist der GARANTIERTE farbunabhängige Kind-Kanal:
//             ≥ 4:1 auf JEDER Intensität (einer der beiden Töne ist immer hochkontrastig);
//             die haloed Schraffur ≥ 3:1 auf den lauten Zellen (4/5) + gegen die
//             Grundfläche; der Fokusring (im Zwischenraum gezeichnet) ≥ 3:1 gegen canvas.
//         Plus: cellFillToken/hatchFor-Abbildung.
// ============================================================
import { describe, expect, it } from "vitest";

import { contrastRatio, relativeLuminance } from "@/tokens/contrast";
import { THEME_NAMES, themes, type SemanticColorToken, type ThemeName } from "@/tokens/themes";

import { cellFillToken, hatchFor } from "./palette";
import type { DeviationLevel } from "./types";

function heatLuminances(theme: ThemeName): number[] {
  return [1, 2, 3, 4, 5].map((n) => relativeLuminance(themes[theme][`heatmap-${n}` as SemanticColorToken]));
}

function strictlyMonotonic(values: number[]): boolean {
  const increasing = values.every((v, i) => i === 0 || v > values[i - 1]!);
  const decreasing = values.every((v, i) => i === 0 || v < values[i - 1]!);
  return increasing || decreasing;
}

describe("Heatmap-Palette — sequenziell (kein Regenbogen)", () => {
  for (const theme of THEME_NAMES) {
    it(`${theme}: Luminanz der Stufen 1..5 ist streng monoton`, () => {
      expect(strictlyMonotonic(heatLuminances(theme))).toBe(true);
    });
  }
});

describe("Heatmap-Palette — nur Auffälliges sticht (§4A/§5.8)", () => {
  for (const theme of THEME_NAMES) {
    it(`${theme}: die lauten Stufen (4/5) heben sich von der Grundfläche ab (≥ 3:1)`, () => {
      const canvas = themes[theme]["surface-canvas"];
      expect(contrastRatio(themes[theme]["heatmap-4"], canvas)).toBeGreaterThanOrEqual(3);
      expect(contrastRatio(themes[theme]["heatmap-5"], canvas)).toBeGreaterThanOrEqual(3);
    });
  }
});

const HEAT_LEVELS = [1, 2, 3, 4, 5] as const;

function fillOf(theme: ThemeName, level: number): string {
  return themes[theme][`heatmap-${level}` as SemanticColorToken];
}

/** Sichtbarkeit eines haloed Elements: Element-Farbe ODER neutraler surface-canvas-Halo. */
function haloMax(theme: ThemeName, color: string, level: number): number {
  return Math.max(contrastRatio(color, fillOf(theme, level)), contrastRatio(themes[theme]["surface-canvas"], fillOf(theme, level)));
}

describe("Heatmap-Palette — Schraffur ≥ 3:1 gegen die Grundfläche (§5.8)", () => {
  for (const theme of THEME_NAMES) {
    it(`${theme}: diff-over/under ≥ 3:1 gegen Grundfläche und Karte`, () => {
      const t = themes[theme];
      for (const token of ["diff-over", "diff-under"] as const) {
        expect(contrastRatio(t[token], t["surface-canvas"])).toBeGreaterThanOrEqual(3);
        expect(contrastRatio(t[token], t["surface-raised"])).toBeGreaterThanOrEqual(3);
      }
    });
  }
});

describe("Heatmap — FCSM-Symbol auf JEDER Zelle lesbar (garantierter Kanal, §5.8)", () => {
  // Der haloed Buchstabe (fg-primary + surface-canvas-Strich) trägt den farbunabhängigen
  // Kind-Kanal: auf jeder Intensität ist EINER der beiden Töne hochkontrastig (light/dark-Paar).
  for (const theme of THEME_NAMES) {
    it(`${theme}: haloed Buchstabe ≥ 4:1 auf allen Stufen 1..5`, () => {
      for (const level of HEAT_LEVELS) {
        expect(haloMax(theme, themes[theme]["fg-primary"], level)).toBeGreaterThanOrEqual(4);
      }
    });
  }
});

describe("Heatmap — haloed Schraffur + Fokusring auf hellen Zellen sichtbar (§5.8)", () => {
  for (const theme of THEME_NAMES) {
    it(`${theme}: haloed Schraffur ≥ 3:1 auf den lauten Stufen (4/5)`, () => {
      for (const level of [4, 5] as const) {
        expect(haloMax(theme, themes[theme]["diff-over"], level)).toBeGreaterThanOrEqual(3);
        expect(haloMax(theme, themes[theme]["diff-under"], level)).toBeGreaterThanOrEqual(3);
      }
    });
    it(`${theme}: Fokusring ≥ 3:1 gegen die Grundfläche (im Zwischenraum gezeichnet)`, () => {
      const t = themes[theme];
      expect(contrastRatio(t["focus-ring"], t["surface-canvas"])).toBeGreaterThanOrEqual(3);
    });
  }
});

describe("cellFillToken / hatchFor", () => {
  it("Stufe 0 → ruhige Grundfläche, 1..5 → heatmap-1..5", () => {
    expect(cellFillToken(0)).toBe("surface-raised");
    for (const level of [1, 2, 3, 4, 5] as DeviationLevel[]) {
      expect(cellFillToken(level)).toBe(`heatmap-${level}`);
    }
  });

  it("Drift → over (45°), Warnung → under (-45°), Normalbetrieb → keine Schraffur", () => {
    expect(hatchFor("drift")).toBe("over");
    expect(hatchFor("warning")).toBe("under");
    expect(hatchFor("healthy")).toBeNull();
  });
});
