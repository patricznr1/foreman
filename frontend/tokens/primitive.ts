// ============================================================
//  FOREMAN Frontend — tokens/primitive.ts
//  Zweck: Ebene 1 der Token-Quelle (Studie §5.7) — ROHWERTE. Hex-Farben,
//         Abstände, Schriftgrößen. Wird NIE direkt im UI referenziert; die
//         semantische Ebene (themes.ts) bildet darauf ab.
//  Architektur-Einordnung: Design-System-Fundament (Schicht 0).
//  Quelle: Designstudie §5.2 (Farben), §5.3 (Typo), §5.4 (Raster/Dichte/Touch).
// ============================================================

/** Rohfarben. Benannt nach Ton + Helligkeit, nicht nach Bedeutung. */
export const color = {
  // — Neutrale, entsättigte Graustufen (Dark, ~90 % der Pixel) —
  neutral950: "#15181C",
  neutral900: "#1C2025",
  neutral850: "#23282E",
  neutral800: "#2C3239",
  neutral700: "#3A424B",
  // fg-muted/alarm-journal: aufgehellt, damit Hinweistext auch auf surface-raised
  // UND surface-overlay ≥ 4.5:1 erreicht (nicht nur auf canvas) — Review-Fix.
  neutral400: "#8D959D",
  neutral300: "#A7B0B8",
  neutral100: "#E8ECEF",
  white: "#FFFFFF",

  // — Neutrale Graustufen (High-Contrast-Light, eigene geprüfte Palette) —
  lnNeutral000: "#FFFFFF",
  lnNeutral050: "#F2F4F7",
  lnNeutral100: "#E8EBEF",
  lnNeutral200: "#D2D7DE",
  lnNeutral400: "#AEB6BF",
  lnText900: "#14181D",
  lnText700: "#41494F",
  lnText500: "#5E666D",

  // — Gesättigte Bedeutungsfarben (Dark) —
  red500: "#E5484D", // ISA-18.2 kritisch / NE107 Failure
  orange500: "#F2820D", // hoch / Function check
  yellow500: "#E8C500", // mittel / Out of spec
  blue500: "#5B8DEF", // niedrig / Maintenance
  green500: "#3BA776", // OK (gedämpftes Grün)
  indigo400: "#8B7CE5", // Vorbehalt (note/caveat — KEIN Alarm)

  // — Gesättigte Bedeutungsfarben (Light, abgedunkelt für Kontrast auf Weiß) —
  redDark: "#C62A2F",
  orangeDark: "#B45A09",
  goldDark: "#8A6D00",
  blueDark: "#2D5BB8",
  greenDark: "#1E7A50",
  indigoDark: "#5B4DBE",

  // — Daten-/Sensorreihen (entsättigt, kategorial unterscheidbar; KEINE Semantik) —
  dataDark1: "#9AA6B0",
  dataDark2: "#7FB0C9",
  dataDark3: "#C2A57E",
  dataDark4: "#A99BC0",
  dataLight1: "#4A5560",
  dataLight2: "#3E6B82",
  dataLight3: "#7A5E36",
  dataLight4: "#5E5078",

  // — Drift-/Heatmap-Sequenz (einfarbig, hell→intensiv; NIE Regenbogen) —
  heatDark1: "#22332F",
  heatDark2: "#27554A",
  heatDark3: "#2E8B6F",
  heatDark4: "#49B98E",
  heatDark5: "#7FE0BE",
  heatLight1: "#E2ECE8",
  heatLight2: "#A9D2C4",
  heatLight3: "#5BA990",
  heatLight4: "#2E8B6F",
  heatLight5: "#15604A",
} as const;

/** Abstände — 8-px-System mit 4-px-Subraster (Studie §5.4). In rem. */
export const space = {
  "0": "0",
  "1": "0.25rem", // 4px (Subraster)
  "2": "0.5rem", // 8px (Basis)
  "3": "0.75rem", // 12px (Mindestabstand Touch)
  "4": "1rem", // 16px
  "5": "1.25rem", // 20px
  "6": "1.5rem", // 24px (Gutter Leitstand)
  "8": "2rem", // 32px
  "10": "2.5rem", // 40px
  "12": "3rem", // 48px
} as const;

/** Schriftgrößen (Studie §5.3) — untere Grenze 14px, nie darunter. In rem. */
export const fontSize = {
  caption: "0.875rem", // 14px (Minimum: Achsenlabel, Metadaten)
  body: "1rem", // 16px
  bodyL: "1.125rem", // 18px (Leitstand-Distanz)
  h2: "1.375rem", // 22px
  h1: "1.75rem", // 28px
  kpi: "3rem", // 48px (Cockpit-KPI, untere Display-Stufe)
  display: "4.5rem", // 72px (große Statuszahl, Distanz)
} as const;

/** Touch-Ziele (Studie §5.4) — verbindlich, nie unterschreiten. In rem. */
export const touch = {
  min: "3.5rem", // 56px primär
  safety: "4rem", // 64px sicherheitsrelevant (Quittieren, Simulation)
  action: "4.5rem", // 72px Quittieren/Speichern Maximalhöhe
  gap: "0.75rem", // 12px Mindestabstand (Handschuh)
} as const;

/** Bewegungsdauern (Studie §5.6) — funktional, nie dekorativ. */
export const motion = {
  fast: "120ms",
  base: "160ms",
  slow: "200ms",
} as const;

export const radius = {
  sm: "0.25rem",
  md: "0.5rem",
  lg: "0.75rem",
} as const;
