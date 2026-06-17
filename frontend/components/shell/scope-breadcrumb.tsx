// ============================================================
//  FOREMAN Frontend — components/shell/scope-breadcrumb.tsx
//  Zweck: Geltungsbereichs-Breadcrumb (§3.3) — Flotte ▸ Klasse ▸ Werk ▸ Maschine
//         als durchgehender, anklickbarer Pfad. Zugleich Navigation und Kontext.
//  Architektur-Einordnung: Persistentes Rahmenelement (Schicht 2, client).
// ============================================================
"use client";

import Link from "next/link";

export interface ScopeCrumb {
  label: string;
  href?: string;
}

export function ScopeBreadcrumb({ items }: { items: ScopeCrumb[] }) {
  return (
    <nav aria-label="Geltungsbereich" className="flex items-center gap-1 text-caption">
      {items.map((crumb, index) => {
        const isLast = index === items.length - 1;
        return (
          <span key={`${crumb.label}-${index}`} className="flex items-center gap-1">
            {index > 0 ? (
              <span aria-hidden="true" className="text-fg-muted">
                ▸
              </span>
            ) : null}
            {crumb.href && !isLast ? (
              <Link href={crumb.href} className="text-fg-secondary hover:text-fg-primary">
                {crumb.label}
              </Link>
            ) : (
              <span className="text-fg-primary" aria-current={isLast ? "page" : undefined}>
                {crumb.label}
              </span>
            )}
          </span>
        );
      })}
    </nav>
  );
}
