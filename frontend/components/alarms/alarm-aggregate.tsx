// ============================================================
//  FOREMAN Frontend — components/alarms/alarm-aggregate.tsx
//  Zweck: Manager-Variante (Matrix 3.1): NUR Zähler/Trends — Alarmrate je Priorität
//         + häufigste Quellen. KEIN Einzel-Quittieren (das wäre Mikromanagement,
//         verwischt Verantwortung). Liest das overview-Aggregat (live), fünf
//         Pflichtzustände über die Hülle, Stand-Stempel.
//  Architektur-Einordnung: Sicht-Komponente (Schicht 3, client).
// ============================================================
"use client";

import { ProvenanceStamp } from "@/components/atoms/provenance-stamp";
import type { FleetOverviewOut } from "@/lib/api/contracts";
import { useRealtimeStore } from "@/lib/realtime/realtime-context";
import { useTopicState } from "@/lib/state/use-topic";
import { FiveState } from "@/lib/ui/five-states";
import { AlarmSituationHeader } from "./alarm-situation-header";

export function AlarmAggregate() {
  const store = useRealtimeStore();
  const state = useTopicState<FleetOverviewOut>(store, "overview");

  return (
    <section className="p-4" aria-label="Alarm-Lagebild (aggregiert)">
      <header className="mb-4 flex items-center justify-between">
        <h1 className="text-h2 font-semibold text-fg-primary">Alarme — Lagebild</h1>
        <span className="text-caption text-fg-muted">Manager-Sicht · aggregiert</span>
      </header>

      <FiveState state={state} label="Lagebild">
        {(overview, freshness) => (
          <div className="flex flex-col gap-6">
            <AlarmSituationHeader overview={overview} />
            <ProvenanceStamp freshness={freshness} />
          </div>
        )}
      </FiveState>
    </section>
  );
}
