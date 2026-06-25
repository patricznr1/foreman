// ============================================================
//  FOREMAN Frontend — components/synoptik/synoptik-machine-list.tsx
//  Zweck: Barrierefreie Maschinen-Leiste der Linie (in Sequenz-Reihenfolge) —
//         tastaturbedienbarer Zwilling zum 3D-Klick: jede Maschine ist ein Link auf
//         dieselbe kanonische Karte (machineHref, loser Vertrag machine_id → Karte).
//         Trägt zugleich als Fallback, wenn WebGL fehlt, und macht die Navigation
//         testbar (Rolle link/href). HITL: navigiert nur.
//  Architektur-Einordnung: Sicht-Komposition (Schicht 2/3), präsentational.
// ============================================================
import Link from "next/link";

import { StatusIndicator } from "@/components/atoms/status-indicator";
import { machineHref } from "@/lib/cockpit/url";
import type { MachinePlacement } from "@/lib/synoptic3d/types";
import { MACHINE_STATUS_LABEL, MACHINE_STATUS_TO_FCSM } from "@/lib/ui/wording";

export interface SynoptikMachineListProps {
  placements: MachinePlacement[];
}

export function SynoptikMachineList({ placements }: SynoptikMachineListProps) {
  return (
    <nav aria-label="Maschinen der Montagelinie 1">
      <ol className="flex flex-wrap gap-2">
        {placements.map((placement) => (
          <li key={placement.machineId}>
            <Link
              href={machineHref(placement.machineId)}
              aria-label={`Maschine ${placement.label}, ${MACHINE_STATUS_LABEL[placement.status]}`}
              className="touch-target flex items-center gap-3 rounded-md border border-line-subtle bg-surface-raised px-3 hover:border-line-strong focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
            >
              <StatusIndicator
                status={MACHINE_STATUS_TO_FCSM[placement.status]}
                label={placement.label}
                size="s"
              />
              <span className="text-caption text-fg-muted">{placement.stage}</span>
            </Link>
          </li>
        ))}
      </ol>
    </nav>
  );
}
