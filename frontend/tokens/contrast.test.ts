// ============================================================
//  FOREMAN Frontend — tokens/contrast.test.ts
//  Zweck: Kontrast-Gate (Studie §5.2/§5.8). Beide Themes (dark, hc-light) erfüllen
//         die strengeren FOREMAN-Schwellen: Status-/Primärtext ≥ 7:1, Körper ≥ 4.5:1,
//         Status-/Grafik-/Bedienfarben ≥ 3:1, Schrift auf Kritisch-Fläche ≥ 4.5:1.
//  Architektur-Einordnung: Quality-Gate (Akzeptanzkriterium F5-FE Prompt 1).
// ============================================================
import { describe, expect, it } from "vitest";
import { contrastRatio } from "./contrast";
import { type SemanticColorToken, THEME_NAMES, themes } from "./themes";

// Farben, die als Status-/Grafik-/Bedienelement getragen werden → ≥ 3:1 (WCAG 1.4.11).
// Status-/Bedien-Farben → ≥ 3:1 (WCAG 1.4.11). NICHT enthalten: die Daten-/
// Heatmap-/Differenz-Palette (data-series-*, heatmap-*, diff-*, data-normalband) —
// das sind sequenzielle Daten-Skalen bzw. schraffur-gestützte Differenzflächen,
// die nach Ordnung/Mehrkanaligkeit bewertet werden, nicht über die 3:1-Schwelle.
const GRAPHIC_TOKENS: readonly SemanticColorToken[] = [
  "alarm-critical",
  "alarm-high",
  "alarm-medium",
  "alarm-low",
  "alarm-journal",
  "state-failure",
  "state-check",
  "state-outofspec",
  "state-maintenance",
  "state-ok",
  "note-caveat",
  "focus-ring",
];

describe("Design-Tokens: Kontrast-Schwellen (Studie §5.2/§5.8)", () => {
  for (const theme of THEME_NAMES) {
    const t = themes[theme];

    // Text wird auf ALLEN Flächen getragen (canvas/raised/overlay) — gegen alle prüfen,
    // nicht nur gegen canvas (Review-Fix: schließt die verschleierte Test-Lücke).
    const surfaces = ["surface-canvas", "surface-raised", "surface-overlay"] as const;

    it(`${theme}: Primär-/Status-Text (fg-primary) ≥ 7:1 auf allen Flächen`, () => {
      for (const surface of surfaces) {
        expect(contrastRatio(t["fg-primary"], t[surface])).toBeGreaterThanOrEqual(7);
      }
    });

    it(`${theme}: Körpertext (fg-secondary, fg-muted) ≥ 4.5:1 auf allen Flächen`, () => {
      for (const surface of surfaces) {
        expect(contrastRatio(t["fg-secondary"], t[surface])).toBeGreaterThanOrEqual(4.5);
        expect(contrastRatio(t["fg-muted"], t[surface])).toBeGreaterThanOrEqual(4.5);
      }
    });

    it(`${theme}: Schrift auf Kritisch-Fläche ≥ 4.5:1 (vollflächiger Alarm)`, () => {
      expect(contrastRatio(t["fg-on-accent"], t["alarm-critical"])).toBeGreaterThanOrEqual(4.5);
    });

    for (const token of GRAPHIC_TOKENS) {
      it(`${theme}: ${token} ≥ 3:1 auf allen Flächen (Grafik/Bedienelement)`, () => {
        for (const surface of surfaces) {
          expect(contrastRatio(t[token], t[surface])).toBeGreaterThanOrEqual(3);
        }
      });
    }
  }
});
