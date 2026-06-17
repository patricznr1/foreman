// ============================================================
//  FOREMAN Frontend — components/shell/quick-capture-fab.tsx
//  Zweck: Persistente Schnellerfassung (§3.3) — Sprung zu Sektion J (Erfassung) von
//         ÜBERALL in einem Tap. Großes, handschuhsicheres Ziel (≥ 64 px) im unteren
//         Daumenbogen. Neutral gefärbt: Farbe bleibt der Statussemantik vorbehalten
//         (Prinzip 3). Kontext-Vorauswahl (Studie §4J): steht man auf einer
//         Maschinen-Detailseite (/machines/{id}), öffnet die Erfassung mit dieser
//         Maschine vorausgewählt (?machine={id}) — „maximaler Kontext".
//  Architektur-Einordnung: Persistentes Rahmenelement (Schicht 2, client).
// ============================================================
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** Leitet die Kontext-Vorauswahl aus der aktuellen Route ab (rein, testbar). */
export function captureHref(pathname: string | null): string {
  const match = pathname?.match(/^\/machines\/(\d+)(?:\/|$)/);
  return match && match[1] ? `/capture?machine=${match[1]}` : "/capture";
}

export function QuickCaptureFab() {
  const pathname = usePathname();
  return (
    <Link
      href={captureHref(pathname)}
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
