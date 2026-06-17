// ============================================================
//  FOREMAN Frontend — tokens/themes.ts
//  Zweck: Ebene 2 (semantisch) + Ebene 3 (Theme) der Token-Quelle (Studie §5.7).
//         SEMANTIC_COLOR_TOKENS sind die EINZIGEN Farbnamen, die das UI nutzt;
//         `themes` weist ihnen je Theme (dark / hc-light) einen Rohwert zu.
//         Dark ist Primärmodus (Halle), High-Contrast-Light gleichwertig (Streulicht).
//  Architektur-Einordnung: Design-System-Fundament (Schicht 0).
//  Quelle: Designstudie §5.2 (Paletten), §5.7 (Token-Ebenen).
// ============================================================
import { color as c } from "./primitive";

export type ThemeName = "dark" | "hc-light";
export const THEME_NAMES: readonly ThemeName[] = ["dark", "hc-light"] as const;
export const DEFAULT_THEME: ThemeName = "dark";

/**
 * Ebene 2: die semantischen Farb-Tokens. Bedeutung, nicht Rohwert. Das UI
 * referenziert ausschließlich diese Namen (als Tailwind-Utility oder CSS-Var).
 */
export const SEMANTIC_COLOR_TOKENS = [
  // Flächen & Ränder (entsättigte Bühne)
  "surface-canvas",
  "surface-raised",
  "surface-overlay",
  "line-subtle",
  "line-strong",
  "focus-ring",
  // Text (Studie: text/primary, text/secondary, text/muted — als fg-* benannt,
  // damit die Tailwind-Utility sauber liest: text-fg-primary statt text-text-primary)
  "fg-primary",
  "fg-secondary",
  "fg-muted",
  "fg-on-accent",
  // Alarmstufen (ISA-18.2)
  "alarm-critical",
  "alarm-high",
  "alarm-medium",
  "alarm-low",
  "alarm-journal",
  // Zustände (NAMUR NE 107 — FCSM + OK)
  "state-failure",
  "state-check",
  "state-outofspec",
  "state-maintenance",
  "state-ok",
  // Vorbehalt (KEIN Alarm — eigene ruhige Signalfarbe)
  "note-caveat",
  // Daten-/Visualisierungs-Palette (entsättigt, nicht-semantisch)
  "data-series-1",
  "data-series-2",
  "data-series-3",
  "data-series-4",
  "data-normalband",
  // Drift-/Heatmap-Sequenz (einfarbig, hell→intensiv)
  "heatmap-1",
  "heatmap-2",
  "heatmap-3",
  "heatmap-4",
  "heatmap-5",
  // Differenz (Über-/Unterschreitung; farbsehschwäche-sicher Blau↔Orange)
  "diff-over",
  "diff-under",
] as const;

export type SemanticColorToken = (typeof SEMANTIC_COLOR_TOKENS)[number];

/** Ebene 3: konkrete Theme-Zuweisung semantisch → primitive. */
export const themes: Record<ThemeName, Record<SemanticColorToken, string>> = {
  dark: {
    "surface-canvas": c.neutral950,
    "surface-raised": c.neutral900,
    "surface-overlay": c.neutral850,
    "line-subtle": c.neutral800,
    "line-strong": c.neutral700,
    "focus-ring": c.blue500,
    "fg-primary": c.neutral100,
    "fg-secondary": c.neutral300,
    "fg-muted": c.neutral400,
    "fg-on-accent": c.neutral950, // dunkle Schrift auf heller Kritisch-Fläche
    "alarm-critical": c.red500,
    "alarm-high": c.orange500,
    "alarm-medium": c.yellow500,
    "alarm-low": c.blue500,
    "alarm-journal": c.neutral400,
    "state-failure": c.red500,
    "state-check": c.orange500,
    "state-outofspec": c.yellow500,
    "state-maintenance": c.blue500,
    "state-ok": c.green500,
    "note-caveat": c.indigo400,
    "data-series-1": c.dataDark1,
    "data-series-2": c.dataDark2,
    "data-series-3": c.dataDark3,
    "data-series-4": c.dataDark4,
    "data-normalband": c.neutral800,
    "heatmap-1": c.heatDark1,
    "heatmap-2": c.heatDark2,
    "heatmap-3": c.heatDark3,
    "heatmap-4": c.heatDark4,
    "heatmap-5": c.heatDark5,
    "diff-over": c.blue500,
    "diff-under": c.orange500,
  },
  "hc-light": {
    "surface-canvas": c.lnNeutral000,
    "surface-raised": c.lnNeutral050,
    "surface-overlay": c.lnNeutral100,
    "line-subtle": c.lnNeutral200,
    "line-strong": c.lnNeutral400,
    "focus-ring": c.blueDark,
    "fg-primary": c.lnText900,
    "fg-secondary": c.lnText700,
    "fg-muted": c.lnText500,
    "fg-on-accent": c.white, // weiße Schrift auf dunkler Kritisch-Fläche
    "alarm-critical": c.redDark,
    "alarm-high": c.orangeDark,
    "alarm-medium": c.goldDark,
    "alarm-low": c.blueDark,
    "alarm-journal": c.lnText500,
    "state-failure": c.redDark,
    "state-check": c.orangeDark,
    "state-outofspec": c.goldDark,
    "state-maintenance": c.blueDark,
    "state-ok": c.greenDark,
    "note-caveat": c.indigoDark,
    "data-series-1": c.dataLight1,
    "data-series-2": c.dataLight2,
    "data-series-3": c.dataLight3,
    "data-series-4": c.dataLight4,
    "data-normalband": c.lnNeutral100,
    "heatmap-1": c.heatLight1,
    "heatmap-2": c.heatLight2,
    "heatmap-3": c.heatLight3,
    "heatmap-4": c.heatLight4,
    "heatmap-5": c.heatLight5,
    "diff-over": c.blueDark,
    "diff-under": c.orangeDark,
  },
};
