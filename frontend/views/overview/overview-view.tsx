// ============================================================
//  FOREMAN Frontend — views/overview/overview-view.tsx
//  Zweck: Vertikaler Durchstich — die schlanke Flotten-Übersicht. Erstbild aus
//         dem HTTP-Snapshot (SSR), danach Live-Aktualisierung über das WS-Thema
//         "overview" (transport-agnostisch über den Store). Trägt die fünf
//         Zustände, Atome (KpiTile/StatusIndicator) und den Herkunftsstempel.
//         KEIN Voll-Cockpit (A bleibt [VISION]) — nur der Architektur-Beweis.
//  Architektur-Einordnung: Sicht (Schicht 3, client). Liest nur abgeleiteten State.
// ============================================================
"use client";

import { KpiTile } from "@/components/atoms/kpi-tile";
import { ProvenanceStamp } from "@/components/atoms/provenance-stamp";
import { StatusIndicator } from "@/components/atoms/status-indicator";
import type { FleetOverviewOut, MachineStatusOut } from "@/lib/api/contracts";
import { useRealtimeStore } from "@/lib/realtime/realtime-context";
import type { DataState } from "@/lib/state/view-state";
import { useTopicState } from "@/lib/state/use-topic";
import { FiveState } from "@/lib/ui/five-states";
import { MACHINE_STATUS_LABEL, MACHINE_STATUS_TO_FCSM } from "@/lib/ui/wording";

export function OverviewView({ initialData }: { initialData?: FleetOverviewOut }) {
  const store = useRealtimeStore();
  const live = useTopicState<FleetOverviewOut>(store, "overview", {
    isEmpty: (overview) => overview.machines.length === 0,
  });

  // SSR-Snapshot überbrückt, bis der Live-Strom greift (sichtbar als „gecacht").
  const state: DataState<FleetOverviewOut> =
    live.kind === "loading" && initialData ? { kind: "cached", data: initialData } : live;

  return (
    <section aria-label="Flotten-Übersicht" className="flex flex-col gap-6">
      <h1 className="text-h1 text-fg-primary">Flotten-Übersicht</h1>
      <FiveState state={state} label="Übersicht">
        {(overview, freshness) => <OverviewContent overview={overview} freshness={freshness} />}
      </FiveState>
    </section>
  );
}

function OverviewContent({
  overview,
  freshness,
}: {
  overview: FleetOverviewOut;
  freshness: "live" | "cached";
}) {
  const healthy = overview.by_status.healthy ?? 0;
  // „Abweichung" = nicht im Normalbetrieb: Drift UND offene Warnungen (sonst fiele
  // eine open_warning-Maschine aus dem Statusbild — Review-Fix).
  const deviating = (overview.by_status.drift_active ?? 0) + (overview.by_status.open_warning ?? 0);
  const openAlarms = overview.open_alarm_total;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-end">
        <ProvenanceStamp freshness={freshness} />
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <KpiTile label="Maschinen im Normalbetrieb" value={healthy} status="ok" />
        <KpiTile
          label="Maschinen mit Abweichung"
          value={deviating}
          status={deviating > 0 ? "outofspec" : "ok"}
        />
        <KpiTile
          label="Offene Alarme"
          value={openAlarms}
          status={openAlarms > 0 ? "check" : "ok"}
        />
      </div>

      <ul
        aria-label="Maschinen-Status"
        className="divide-y divide-line-subtle rounded-lg border border-line-subtle bg-surface-raised"
      >
        {overview.machines.map((machine) => (
          <MachineRow key={machine.id} machine={machine} />
        ))}
      </ul>
    </div>
  );
}

function MachineRow({ machine }: { machine: MachineStatusOut }) {
  const fcsm = MACHINE_STATUS_TO_FCSM[machine.status];
  return (
    <li className="touch-target flex items-center justify-between gap-3 px-4 py-3">
      <div className="flex flex-col">
        <span className="text-body text-fg-primary">{machine.label}</span>
        {machine.machine_class ? (
          <span className="text-caption text-fg-muted">{machine.machine_class}</span>
        ) : null}
      </div>
      <div className="flex items-center gap-3">
        {machine.open_alarm_count > 0 ? (
          <span className="text-caption tabular-nums text-fg-secondary">
            {machine.open_alarm_count} Alarme
          </span>
        ) : null}
        <StatusIndicator status={fcsm} label={MACHINE_STATUS_LABEL[machine.status]} size="s" />
      </div>
    </li>
  );
}
