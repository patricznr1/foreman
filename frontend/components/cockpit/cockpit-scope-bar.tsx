// ============================================================
//  FOREMAN Frontend — components/cockpit/cockpit-scope-bar.tsx
//  Zweck: Die Geltungsbereichs-Leiste des Cockpits (§3.3/§4A) — der föderierte
//         Breadcrumb Flotte ▸ Klasse ▸ Linie (Klasse/Linie sind reale Felder,
//         client-gefiltert). Die Mehr-WERK-Ebene ist markiertes ZIELBILD (FOREMAN
//         ist Single-Tenant: eine Instanz = ein Werk) — sie wird dezent als Zielbild
//         gekennzeichnet, NICHT als funktionsloser Platzhalter vorgegaukelt.
//  Architektur-Einordnung: Persistentes Rahmenelement (Schicht 2/3, client).
// ============================================================
import { ScopeBreadcrumb } from "@/components/shell/scope-breadcrumb";
import { scopeCrumbs } from "@/lib/cockpit/scope";
import type { CockpitScope } from "@/lib/cockpit/types";

export interface CockpitScopeBarProps {
  scope: CockpitScope;
}

export function CockpitScopeBar({ scope }: CockpitScopeBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
      <ScopeBreadcrumb items={scopeCrumbs(scope)} />
      <span
        className="rounded-sm border border-line-subtle px-2 py-0.5 text-caption text-fg-muted"
        title="FOREMAN ist je Werk eine eigene Instanz. Die werksübergreifende Föderation ist das Zielbild."
      >
        Mehrere Werke · Zielbild
      </span>
    </div>
  );
}
