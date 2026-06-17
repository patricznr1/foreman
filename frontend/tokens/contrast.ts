// ============================================================
//  FOREMAN Frontend — tokens/contrast.ts
//  Zweck: WCAG-2.x-Kontrastberechnung (relative Luminanz + Kontrastverhältnis).
//         Grundlage des automatisierten Kontrast-Gates (Studie §5.2/§5.8:
//         Status-Text ≥ 7:1, Körper ≥ 4.5:1, Grafik/Bedienelement ≥ 3:1).
//  Architektur-Einordnung: Design-System-Fundament (Schicht 0).
// ============================================================

/** Zerlegt `#RRGGBB` in [r, g, b] (0–255). Wirft bei ungültigem Wert. */
export function hexToRgb(hex: string): readonly [number, number, number] {
  const match = /^#?([0-9a-fA-F]{6})$/.exec(hex.trim());
  if (!match) {
    throw new Error(`Ungültiger Hex-Farbwert: ${hex}`);
  }
  const int = Number.parseInt(match[1]!, 16);
  return [(int >> 16) & 0xff, (int >> 8) & 0xff, int & 0xff];
}

/** Linearisiert einen sRGB-Kanal (0–255) nach WCAG. */
function channelLuminance(value: number): number {
  const s = value / 255;
  return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
}

/** Relative Luminanz einer Farbe (0 = schwarz, 1 = weiß). */
export function relativeLuminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex);
  return 0.2126 * channelLuminance(r) + 0.7152 * channelLuminance(g) + 0.0722 * channelLuminance(b);
}

/** Kontrastverhältnis zweier Farben (1:1 … 21:1). Reihenfolge egal. */
export function contrastRatio(foreground: string, background: string): number {
  const lf = relativeLuminance(foreground);
  const lb = relativeLuminance(background);
  const lighter = Math.max(lf, lb);
  const darker = Math.min(lf, lb);
  return (lighter + 0.05) / (darker + 0.05);
}
