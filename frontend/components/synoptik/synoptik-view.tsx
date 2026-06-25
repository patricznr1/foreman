// ============================================================
//  FOREMAN Frontend — components/synoptik/synoptik-view.tsx
//  Zweck: Orchestrator der Live-3D-Linie (Sektion-A-Sub-Ansicht). Setzt auf den
//         SSR-Snapshot von /overview auf, geht live über das WS-Thema "overview"
//         (gleiche Quelle wie Cockpit/Stream-Kachel), leitet das reine Linien-Layout
//         ab und reicht es an Renderer, Legende und barrierefreie Maschinenliste.
//         Klick/Hover → kanonische Maschinenkarte (machineHref). Fünf Pflichtzustände
//         + Degradation über FiveState; Sim-Vorbehalt sichtbar. HITL: navigiert nur.
//  Architektur-Einordnung: Sicht (Schicht 3, client). Liest nur abgeleiteten State.
// ============================================================
"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { ProvenanceStamp } from "@/components/atoms/provenance-stamp";
import { CockpitViewSwitch } from "@/components/cockpit/cockpit-view-switch";
import type { CurrentUser, FleetOverviewOut } from "@/lib/api/contracts";
import { machineHref } from "@/lib/cockpit/url";
import { useRealtimeStore } from "@/lib/realtime/realtime-context";
import { useTopicState } from "@/lib/state/use-topic";
import type { DataState } from "@/lib/state/view-state";
import { buildLineLayout } from "@/lib/synoptic3d/layout";
import { FiveState } from "@/lib/ui/five-states";

import { SynoptikLegend } from "./synoptik-legend";
import { SynoptikMachineList } from "./synoptik-machine-list";
import { SynoptikScene } from "./synoptik-scene";

export interface SynoptikViewProps {
  user: CurrentUser;
  initialData?: FleetOverviewOut;
}

/** Rollen-Untertitel — Manager: ganze Linie/Flotte, Schichtleiter: seine Linie. */
function roleSubtitle(role: CurrentUser["role"]): string {
  return role === "manager" ? "Montagelinie 1 — Flottenbild" : "Montagelinie 1 — Ihre Linie";
}

export function SynoptikView({ user, initialData }: SynoptikViewProps) {
  const store = useRealtimeStore();
  const live = useTopicState<FleetOverviewOut>(store, "overview", {
    isEmpty: (overview) => overview.machines.length === 0,
  });

  // SSR-Snapshot überbrückt, bis der Live-Strom greift (sichtbar als „gecacht").
  const state: DataState<FleetOverviewOut> =
    live.kind === "loading" && initialData ? { kind: "cached", data: initialData } : live;

  return (
    <section aria-label="Anlagen-Synoptik 3D" className="flex flex-col gap-6">
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <h1 className="text-h1 text-fg-primary">Anlagen-Synoptik 3D</h1>
          <CockpitViewSwitch active="synoptik" />
        </div>
        <p className="text-body text-fg-secondary">{roleSubtitle(user.role)}</p>
      </header>
      <FiveState state={state} label="3D-Linie">
        {(overview, freshness) => <SynoptikContent overview={overview} freshness={freshness} />}
      </FiveState>
    </section>
  );
}

function SynoptikContent({
  overview,
  freshness,
}: {
  overview: FleetOverviewOut;
  freshness: "live" | "cached";
}) {
  const router = useRouter();
  const placements = useMemo(() => buildLineLayout(overview.machines), [overview.machines]);

  // Stand-Stempel clientseitig bei jeder neuen Lage (kein SSR-Hydration-Mismatch).
  const [stampedAt, setStampedAt] = useState<Date | null>(null);
  useEffect(() => {
    setStampedAt(new Date());
  }, [overview]);

  // Loser Vertrag machine_id → kanonische Karte (gleiche Route wie Heatmap-Klick).
  const handleSelectMachine = (machineId: number): void => {
    router.push(machineHref(machineId));
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <SynoptikLegend />
        <ProvenanceStamp freshness={freshness} stampedAt={stampedAt} caveat />
      </div>
      <SynoptikScene placements={placements} onSelectMachine={handleSelectMachine} />
      <p className="text-caption text-note-caveat">
        Digitaler Zwilling (Simulation, intern). Eine kranke Maschine sticht räumlich zwischen
        ihren gesunden Schwestern heraus. Diese Ansicht zeigt nur an und navigiert — sie steuert
        keine Maschine.
      </p>
      <SynoptikMachineList placements={placements} />
    </div>
  );
}
