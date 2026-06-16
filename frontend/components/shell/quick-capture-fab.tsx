// ============================================================
//  FOREMAN Frontend — components/shell/quick-capture-fab.tsx
//  Zweck: Persistente Schnellerfassung (§3.3) — Sprung zu Sektion J (Erfassung).
//         Großes, handschuhsicheres Ziel (≥ 64 px) im unteren Daumenbogen.
//         Neutral gefärbt: Farbe bleibt der Statussemantik vorbehalten (Prinzip 3).
//  Architektur-Einordnung: Persistentes Rahmenelement (Schicht 2, client).
// ============================================================
"use client";

import Link from "next/link";

export function QuickCaptureFab() {
  return (
    <Link
      href="/capture"
      aria-label="Schnellerfassung"
      title="Schnellerfassung"
      className="touch-target-safety fixed bottom-6 right-6 z-40 flex items-center justify-center rounded-full border border-line-strong bg-surface-overlay text-fg-primary shadow-lg"
    >
      <span aria-hidden="true" className="text-h2 leading-none">
        +
      </span>
    </Link>
  );
}
