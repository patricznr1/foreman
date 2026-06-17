// ============================================================
//  FOREMAN Frontend — components/cockpit/cockpit-view.tsx
//  Zweck: Der Orchestrator von Sektion A (Studie §4A) — setzt auf den FE1-Übersicht-
//         Durchstich auf (SSR-Snapshot → WS-Live über das Thema "overview", über den
//         Store, transport-agnostisch) und baut ihn zum vollen Cockpit aus:
//         Geltungsbereich (ScopeBreadcrumb + Föderations-Zielbild), KPI-Zeile,
//         DriftHeatmap (Anker, ~60 %) und die rechte Prioritätsspalte. Live ohne
//         Sprung (Zellen aktualisieren in-place; Kipp-Puls einmalig), Stand-Stempel,
//         fünf Pflichtzustände + Degradation (offline → gecacht, eingefroren).
//         Rollen-Split OHNE bedingte Hooks (Manager Flottenbild, Schichtleiter
//         Linienbild — Daten serverseitig scope-gefiltert). HITL: nur Navigation.
//  Architektur-Einordnung: Sicht (Schicht 3, client). Liest nur abgeleiteten State.
// ============================================================
"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { ProvenanceStamp } from "@/components/atoms/provenance-stamp";
import type { CurrentUser, FleetOverviewOut } from "@/lib/api/contracts";
import { detectKipps, snapshotKinds } from "@/lib/cockpit/flip";
import { pushSample } from "@/lib/cockpit/history";
import { buildCockpitKpis } from "@/lib/cockpit/kpis";
import { buildHeatmapMatrix } from "@/lib/cockpit/matrix";
import { buildPriorityEntries } from "@/lib/cockpit/priority";
import { filterByScope } from "@/lib/cockpit/scope";
import type { CellKind, CockpitScope, HeatmapCell } from "@/lib/cockpit/types";
import { machineHref } from "@/lib/cockpit/url";
import { useRealtimeStore } from "@/lib/realtime/realtime-context";
import { useTopicState } from "@/lib/state/use-topic";
import type { DataState } from "@/lib/state/view-state";
import { FiveState } from "@/lib/ui/five-states";

import { CockpitKpiRow, type KpiHistory } from "./cockpit-kpi-row";
import { CockpitScopeBar } from "./cockpit-scope-bar";
import { DriftHeatmap } from "./drift-heatmap";
import { PriorityColumn } from "./priority-column";

export interface CockpitViewProps {
  user: CurrentUser;
  scope: CockpitScope;
  initialData?: FleetOverviewOut;
}

/** Rollen-Untertitel (Matrix 3.1) — Manager: ganze Flotte, Schichtleiter: seine Linien. */
function roleSubtitle(role: CurrentUser["role"]): string {
  return role === "manager"
    ? "Flottenbild — alle Werke und Klassen"
    : "Linienbild — Ihre Linien";
}

export function CockpitView({ user, scope, initialData }: CockpitViewProps) {
  const store = useRealtimeStore();
  const live = useTopicState<FleetOverviewOut>(store, "overview", {
    isEmpty: (overview) => overview.machines.length === 0,
  });

  // SSR-Snapshot überbrückt, bis der Live-Strom greift (sichtbar als „gecacht").
  const state: DataState<FleetOverviewOut> =
    live.kind === "loading" && initialData ? { kind: "cached", data: initialData } : live;

  return (
    <section aria-label="Flotten-Cockpit" className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <CockpitScopeBar scope={scope} />
        <h1 className="text-h1 text-fg-primary">Flotten-Cockpit</h1>
        <p className="text-body text-fg-secondary">{roleSubtitle(user.role)}</p>
      </header>
      <FiveState state={state} label="Cockpit">
        {(overview, freshness) => (
          <CockpitContent overview={overview} freshness={freshness} scope={scope} />
        )}
      </FiveState>
    </section>
  );
}

function CockpitContent({
  overview,
  freshness,
  scope,
}: {
  overview: FleetOverviewOut;
  freshness: "live" | "cached";
  scope: CockpitScope;
}) {
  const router = useRouter();

  const { machineClass, lineId } = scope;
  const machines = useMemo(
    () => filterByScope(overview.machines, { machineClass, lineId }),
    [overview.machines, machineClass, lineId],
  );
  const matrix = useMemo(() => buildHeatmapMatrix(machines), [machines]);
  const kpis = useMemo(() => buildCockpitKpis(machines), [machines]);
  const priority = useMemo(() => buildPriorityEntries(machines), [machines]);

  // Live-Verlaufsspur der Kennzahlen (Spark) — beginnt leer, wächst pro neuer Lage.
  const [history, setHistory] = useState<KpiHistory>({
    availability: [],
    criticalOpen: [],
    driftCount: [],
  });
  useEffect(() => {
    setHistory((prev) => ({
      availability: pushSample(prev.availability, kpis.availabilityPct),
      criticalOpen: pushSample(prev.criticalOpen, kpis.criticalOpen),
      driftCount: pushSample(prev.driftCount, kpis.driftCount),
    }));
  }, [kpis.availabilityPct, kpis.criticalOpen, kpis.driftCount]);

  // Kipp-Puls: Zellen, die NEU in eine Abweichung kippen, pulsen einmal (§5.6).
  const prevKinds = useRef<Map<number, CellKind>>(new Map());
  const [kipped, setKipped] = useState<ReadonlySet<number>>(new Set());
  useEffect(() => {
    const cells = matrix.rows.flatMap((row) => row.cells);
    setKipped(detectKipps(prevKinds.current, cells));
    prevKinds.current = snapshotKinds(cells);
  }, [matrix]);

  // Stand-Stempel: clientseitig bei jeder neuen Lage (kein SSR-Hydration-Mismatch).
  const [stampedAt, setStampedAt] = useState<Date | null>(null);
  useEffect(() => {
    setStampedAt(new Date());
  }, [overview]);

  const handleSelectCell = (cell: HeatmapCell): void => {
    router.push(machineHref(cell.machineId));
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-end">
        <ProvenanceStamp freshness={freshness} stampedAt={stampedAt} />
      </div>

      <CockpitKpiRow kpis={kpis} history={history} />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[2fr_1fr]">
        <DriftHeatmap matrix={matrix} kippedMachineIds={kipped} onSelectCell={handleSelectCell} />
        <PriorityColumn entries={priority} />
      </div>
    </div>
  );
}
