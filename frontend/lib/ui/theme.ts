// ============================================================
//  FOREMAN Frontend — lib/ui/theme.ts
//  Zweck: Theme- (dark / hc-light) und Dichte-Modi (comfortable/standard/compact)
//         — Konstanten + Anwendungs-Helfer. Theme wird über [data-theme] und
//         [data-density] auf <html> gesteuert (Tokens lösen automatisch auf).
//  Architektur-Einordnung: Darstellungs-Steuerung (Schicht 1).
//  Quelle: Designstudie §5.2 (Dark primär + HC-Light), §5.4 (Dichte).
// ============================================================
import { THEME_NAMES, type ThemeName } from "../../tokens/themes";

export type { ThemeName };
export { THEME_NAMES, DEFAULT_THEME } from "../../tokens/themes";

export const DENSITIES = ["comfortable", "standard", "compact"] as const;
export type Density = (typeof DENSITIES)[number];
export const DEFAULT_DENSITY: Density = "standard";

export const THEME_STORAGE_KEY = "foreman.theme";
export const DENSITY_STORAGE_KEY = "foreman.density";

export function isThemeName(value: string | null | undefined): value is ThemeName {
  return value != null && (THEME_NAMES as readonly string[]).includes(value);
}

export function isDensity(value: string | null | undefined): value is Density {
  return value != null && (DENSITIES as readonly string[]).includes(value);
}

export function applyTheme(theme: ThemeName): void {
  if (typeof document !== "undefined") {
    document.documentElement.dataset.theme = theme;
  }
}

export function applyDensity(density: Density): void {
  if (typeof document !== "undefined") {
    document.documentElement.dataset.density = density;
  }
}
