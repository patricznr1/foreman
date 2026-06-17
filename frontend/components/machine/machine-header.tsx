// ============================================================
//  FOREMAN Frontend — components/machine/machine-header.tsx
//  Zweck: Maschinen-Kopf (Studie §4B): Identität (Stammdaten-Pull, sofort), aktueller
//         FCSM-Status GROSS (StatusIndicator size l, live über das WS-Thema machine:{id})
//         + Schlüssel-KPI (offene Alarme), und die Schnellaktionen (Notiz → J,
//         Vorhersage → E, Ereigniskette → D) als Navigation/Anforderung — keine Aktorik.
//         Status in der Fünf-Zustände-Hülle (lädt → live/gecacht), kein weißer Schirm.
//  Architektur-Einordnung: Sicht-Baustein (Schicht 3, client).
// ============================================================
"use client";

import { KpiTile } from "@/components/atoms/kpi-tile";
import { StatusIndicator } from "@/components/atoms/status-indicator";
import type { MachineRead, MachineStatusOut } from "@/lib/api/contracts";
import type { MachineRoleView } from "@/lib/machine/roles";
import { useRealtimeStore } from "@/lib/realtime/realtime-context";
import { useTopicState } from "@/lib/state/use-topic";
import { FiveState } from "@/lib/ui/five-states";
import { MACHINE_STATUS_LABEL, MACHINE_STATUS_TO_FCSM } from "@/lib/ui/wording";

import { MachineCrossLinks } from "./machine-cross-links";

export interface MachineHeaderProps {
  machine: MachineRead;
  roleView: MachineRoleView;
}

export function MachineHeader({ machine, roleView }: MachineHeaderProps) {
  const store = useRealtimeStore();
  const statusState = useTopicState<MachineStatusOut>(store, `machine:${machine.id}`);

  const identity = [
    machine.machine_class,
    machine.line_id !== null ? `Linie ${machine.line_id}` : null,
    machine.location,
  ]
    .filter((part): part is string => Boolean(part))
    .join(" · ");

  return (
    <header className="flex flex-col gap-4 rounded-lg border border-line-subtle bg-surface-raised p-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="text-h1 text-fg-primary">{machine.label}</h1>
          {identity ? <p className="text-caption text-fg-muted">{identity}</p> : null}
        </div>

        <FiveState state={statusState} label="Status">
          {(status) => (
            <div className="flex flex-wrap items-center gap-4">
              <StatusIndicator
                status={MACHINE_STATUS_TO_FCSM[status.status]}
                label={MACHINE_STATUS_LABEL[status.status]}
                size="l"
              />
              <KpiTile
                label="Offene Alarme"
                value={status.open_alarm_count}
                status={status.open_alarm_count > 0 ? "check" : "ok"}
              />
            </div>
          )}
        </FiveState>
      </div>

      <MachineCrossLinks
        machineId={machine.id}
        canCaptureNote={roleView.canCaptureNote}
        canRequestPrediction={roleView.canRequestPrediction}
      />
    </header>
  );
}
