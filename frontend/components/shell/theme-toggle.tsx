// ============================================================
//  FOREMAN Frontend — components/shell/theme-toggle.tsx
//  Zweck: Umschalter Dark ↔ High-Contrast-Light (Streulicht-Arbeitsplatz).
//         Persistiert die Wahl; Tastatur-bedienbar mit sichtbarem Fokus.
//  Architektur-Einordnung: Shell-Bedienelement (Schicht 2, client).
// ============================================================
"use client";

import { useEffect, useState } from "react";
import { THEME_STORAGE_KEY, type ThemeName, applyTheme, isThemeName } from "@/lib/ui/theme";

export function ThemeToggle() {
  const [theme, setTheme] = useState<ThemeName>("dark");

  useEffect(() => {
    const current = document.documentElement.dataset.theme;
    if (isThemeName(current)) {
      setTheme(current);
    }
  }, []);

  function toggle(): void {
    const next: ThemeName = theme === "dark" ? "hc-light" : "dark";
    setTheme(next);
    applyTheme(next);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, next);
    } catch {
      // Persistenz blockiert (Privacy-Modus) — Theme gilt für die Sitzung.
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className="touch-target rounded-md px-3 text-caption text-fg-secondary hover:bg-surface-raised"
      aria-label={`Thema wechseln (aktuell ${theme === "dark" ? "Dunkel" : "Hoher Kontrast"})`}
    >
      {theme === "dark" ? "◐ Dunkel" : "◑ Kontrast"}
    </button>
  );
}
