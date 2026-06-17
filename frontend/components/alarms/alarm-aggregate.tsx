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
import { countByPriorityFromOverview } from "@/lib/alarms/counts";
import { PRIORITY_LABEL, PRIORITY_ORDER } from "@/lib/alarms/priority";
import { useRealtimeStore } from "@/lib/realtime/realtime-context";
import { useTopicState } from "@/lib/state/use-topic";
import { FiveState } from "@/lib/ui/five-states";
import { cx } from "@/lib/ui/cx";
import { PRIORITY_TEXT } from "./alarm-styles";

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
        {(overview, freshness) => {
          const counts = countByPriorityFromOverview(overview);
          const topSources = [...overview.machines]
            .filter((machine) => machine.open_alarm_count > 0)
            .sort((a, b) => b.open_alarm_count - a.open_alarm_count)
            .slice(0, 5);

          return (
            <div className="flex flex-col gap-6">
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                {PRIORITY_ORDER.map((priority) => (
                  <div
                    key={priority}
                    className="rounded-lg border border-line-subtle bg-surface-raised p-4"
                  >
                    <div className={cx("text-display font-semibold tabular-nums", PRIORITY_TEXT[priority])}>
                      {counts[priority]}
                    </div>
                    <div className="text-caption text-fg-secondary">{PRIORITY_LABEL[priority]}</div>
                  </div>
                ))}
              </div>

              <div>
                <h2 className="mb-2 text-body-l font-medium text-fg-primary">Häufigste Quellen</h2>
                {topSources.length === 0 ? (
                  <p className="text-body text-fg-muted">Keine offenen Alarme — Anlage ruhig.</p>
                ) : (
                  <ul className="flex flex-col gap-2">
                    {topSources.map((machine) => (
                      <li
                        key={machine.id}
                        className="flex items-center justify-between rounded-md border border-line-subtle bg-surface-raised px-3 py-2"
                      >
                        <span className="text-body text-fg-primary">{machine.label}</span>
                        <span className="text-body tabular-nums text-fg-secondary">
                          {machine.open_alarm_count} offen
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <ProvenanceStamp freshness={freshness} />
            </div>
          );
        }}
      </FiveState>
    </section>
  );
}
