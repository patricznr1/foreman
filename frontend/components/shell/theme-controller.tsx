// ============================================================
//  FOREMAN Frontend — components/shell/theme-controller.tsx
//  Zweck: Initialisiert Theme/Dichte beim Mount aus gespeicherter Wahl bzw.
//         System-Präferenz (prefers-contrast). Default bleibt Dark (Halle).
//         Rendert nichts.
//  Architektur-Einordnung: Shell-Steuerung (Schicht 2, client).
// ============================================================
"use client";

import { useEffect } from "react";
import {
  DENSITY_STORAGE_KEY,
  THEME_STORAGE_KEY,
  applyDensity,
  applyTheme,
  isDensity,
  isThemeName,
} from "@/lib/ui/theme";

export function ThemeController() {
  useEffect(() => {
    try {
      const storedTheme = localStorage.getItem(THEME_STORAGE_KEY);
      if (isThemeName(storedTheme)) {
        applyTheme(storedTheme);
      } else if (window.matchMedia?.("(prefers-contrast: more)").matches) {
        applyTheme("hc-light");
      }
      const storedDensity = localStorage.getItem(DENSITY_STORAGE_KEY);
      if (isDensity(storedDensity)) {
        applyDensity(storedDensity);
      }
    } catch {
      // localStorage/matchMedia blockiert (Privacy-Modus) → Defaults behalten.
    }
  }, []);

  return null;
}
