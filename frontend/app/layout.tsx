// ============================================================
//  FOREMAN Frontend — app/layout.tsx
//  Zweck: Root-Layout. Setzt die Sprach- und Theme-/Dichte-Defaults auf <html>
//         (Dark primär), lädt die globale Token-CSS und initialisiert Theme/
//         Dichte beim Mount (ThemeController). Hallensprache, ruhige Grundfläche.
//  Architektur-Einordnung: App-Einstieg (Schicht 2/3).
// ============================================================
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { ThemeController } from "@/components/shell/theme-controller";
import "./globals.css";

export const metadata: Metadata = {
  title: "FOREMAN",
  description: "Production Intelligence mit Gedächtnis — ruhige, rollenbasierte Hallen-Oberfläche.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="de" data-theme="dark" data-density="standard" suppressHydrationWarning>
      <body>
        <ThemeController />
        {children}
      </body>
    </html>
  );
}
