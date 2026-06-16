// ============================================================
//  FOREMAN Frontend — components/shell/skip-link.tsx
//  Zweck: „Zum Hauptinhalt springen" — Tastatur-Sprungmarke (§5.8). Sichtbar nur
//         bei Fokus, führt direkt zu <main id="main">.
//  Architektur-Einordnung: A11y-Rahmenelement (Schicht 2).
// ============================================================
export function AppShellSkipLink() {
  return (
    <a
      href="#main"
      className="sr-only rounded-md bg-surface-overlay px-3 py-2 text-fg-primary focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50"
    >
      Zum Hauptinhalt springen
    </a>
  );
}
