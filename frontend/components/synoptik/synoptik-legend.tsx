// ============================================================
//  FOREMAN Frontend — components/synoptik/synoptik-legend.tsx
//  Zweck: Farb-Legende der 3D-Linie — die im /overview-Datenfluss erreichbaren
//         Maschinen-Zustände (Normalbetrieb / Abweichung / Offene Warnung) als
//         FCSM-Indikator. Mehrkanalig (Farbe + Kürzel + Label), nie nur Farbe.
//  Architektur-Einordnung: Atom-Komposition (Schicht 2), rein präsentational.
// ============================================================
import { StatusIndicator } from "@/components/atoms/status-indicator";
import type { MachineStatus } from "@/lib/api/contracts";
import { MACHINE_STATUS_LABEL, MACHINE_STATUS_TO_FCSM } from "@/lib/ui/wording";

// Die im Flotten-Status erreichbaren Zustände (inkl. „critical" → rot bei
// kritischer/Notfall-Severity). Wartung (M) bleibt im /overview-Pfad ungenutzt.
const STATUSES: readonly MachineStatus[] = ["healthy", "drift_active", "open_warning", "critical"];

export function SynoptikLegend() {
  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-2" aria-label="Status-Legende">
      <span className="text-caption text-fg-muted">Status je Maschine:</span>
      {STATUSES.map((status) => (
        <StatusIndicator
          key={status}
          status={MACHINE_STATUS_TO_FCSM[status]}
          label={MACHINE_STATUS_LABEL[status]}
          size="s"
        />
      ))}
    </div>
  );
}
