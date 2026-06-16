// ============================================================
//  FOREMAN Frontend — components/shell/app-shell.tsx
//  Zweck: App-Shell (§3.3) — komponiert die persistenten Rahmenelemente:
//         globale Status-/Alarmleiste (oben, live), rollengefilterte
//         Primärnavigation (links am Leitstand/Tablet, unten am Mobil) und die
//         persistente Schnellerfassung. Mobile-first, durch Umbau statt Schrumpfen.
//  Architektur-Einordnung: Layout-Rahmen (Schicht 2, client).
// ============================================================
"use client";

import type { ReactNode } from "react";
import { AppShellSkipLink } from "./skip-link";
import { GlobalStatusBar } from "./global-status-bar";
import { PrimaryNav } from "./primary-nav";
import { QuickCaptureFab } from "./quick-capture-fab";
import type { ScopeCrumb } from "./scope-breadcrumb";

export function AppShell({ children, scope }: { children: ReactNode; scope?: ScopeCrumb[] }) {
  return (
    <div className="flex min-h-screen flex-col bg-surface-canvas">
      <AppShellSkipLink />
      <GlobalStatusBar scope={scope} />
      <div className="flex flex-1 flex-col md:flex-row">
        <aside className="hidden shrink-0 border-r border-line-subtle p-2 md:block md:w-56">
          <PrimaryNav ariaLabel="Hauptnavigation" />
        </aside>
        <main id="main" className="flex-1 p-4 md:p-6">
          {children}
        </main>
      </div>
      <div className="border-t border-line-subtle p-2 md:hidden">
        <PrimaryNav orientation="horizontal" ariaLabel="Hauptnavigation (mobil)" />
      </div>
      <QuickCaptureFab />
    </div>
  );
}
