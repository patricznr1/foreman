// ============================================================
//  FOREMAN Frontend — components/cockpit/cockpit-view-switch.tsx
//  Zweck: Ansichts-Umschalter innerhalb von Sektion A — zwischen der Heatmap
//         (/overview) und der Live-3D-Linie (/synoptik). Beide Sichten lesen denselben
//         Flotten-Strom; der Umschalter ist KEIN achter Nav-Eintrag (Studie §3.3,
//         ≤ 7), sondern der Einstieg in die 3D-Sektion aus dem Cockpit heraus.
//  Architektur-Einordnung: Atom (Schicht 2), rein präsentational (nur Navigation).
// ============================================================
import Link from "next/link";

import { cx } from "@/lib/ui/cx";

export type CockpitViewKind = "heatmap" | "synoptik";

const ITEMS: readonly { kind: CockpitViewKind; label: string; href: string }[] = [
  { kind: "heatmap", label: "Heatmap", href: "/overview" },
  { kind: "synoptik", label: "3D-Linie", href: "/synoptik" },
];

export interface CockpitViewSwitchProps {
  active: CockpitViewKind;
}

export function CockpitViewSwitch({ active }: CockpitViewSwitchProps) {
  return (
    <nav
      aria-label="Cockpit-Ansicht"
      className="inline-flex gap-0.5 rounded-md border border-line-subtle bg-surface-raised p-0.5"
    >
      {ITEMS.map((item) => {
        const isActive = item.kind === active;
        return (
          <Link
            key={item.kind}
            href={item.href}
            aria-current={isActive ? "page" : undefined}
            className={cx(
              "rounded px-3 py-1 text-caption transition-colors",
              isActive
                ? "bg-surface-overlay text-fg-primary"
                : "text-fg-muted hover:text-fg-primary",
            )}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
