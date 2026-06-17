// ============================================================
//  FOREMAN Frontend — components/machine/machine-alarms.tsx
//  Zweck: Offene Alarme DIESER Maschine, eingebettet über die WIEDERVERWENDETE
//         C-AlarmRow (kein dupliziertes Alarm-Rendering). Datenanbindung über das
//         geteilte useAlarms (Erstbild GET /alarms + WS-Signal machine:{id} → Nach-
//         laden + ID-Diff). Maschinen-Filter client-seitig (GET /alarms ist server-
//         seitig nicht scope-gefiltert — C-Anschlusspunkt; Sichtbarkeit ≤ Backend).
//         HITL: Quittieren ist eine Alarm-STATUS-Aktion (AlarmRow/AcknowledgeAction),
//         nie Anlagen-Aktorik; reale Quittier-Route nur für Drift.
//  Architektur-Einordnung: Sicht-Baustein (Schicht 3, client) — bettet C ein.
// ============================================================
"use client";

import { useState } from "react";

import { AlarmRow } from "@/components/alarms/alarm-row";
import { ProvenanceStamp } from "@/components/atoms/provenance-stamp";
import type { MachineMeta } from "@/lib/alarms/types";
import { useAlarms } from "@/lib/alarms/use-alarms";
import { buildAlarmViewModel } from "@/lib/alarms/view-model";
import { useOnline } from "@/lib/ondemand/use-online";
import { FiveState } from "@/lib/ui/five-states";

const SHELF_TTL_MS = 15 * 60 * 1000;

export interface MachineAlarmsProps {
  machineId: number;
  machineLabel: string;
  lineId: number | null;
  /** Quittieren erlaubt (Rolle) — AlarmRow gated die Drift-vs-generisch-Logik selbst. */
  canAcknowledge: boolean;
  nowMs?: number;
}

export function MachineAlarms({
  machineId,
  machineLabel,
  lineId,
  canAcknowledge,
  nowMs,
}: MachineAlarmsProps) {
  const online = useOnline();
  const { state, newIds, stampedAt, refetch } = useAlarms({ signalTopics: [`machine:${machineId}`] });
  const [shelf, setShelf] = useState<ReadonlyMap<number, number>>(new Map());

  const machines: ReadonlyMap<number, MachineMeta> = new Map([[machineId, { label: machineLabel, lineId }]]);
  const now = nowMs ?? Date.now();

  const onShelve = (id: number): void => {
    setShelf((prev) => new Map(prev).set(id, now + SHELF_TTL_MS));
  };
  const onUnshelve = (id: number): void => {
    setShelf((prev) => {
      const next = new Map(prev);
      next.delete(id);
      return next;
    });
  };

  return (
    <section
      aria-label="Offene Alarme dieser Maschine"
      className="flex flex-col gap-3 rounded-lg border border-line-subtle bg-surface-raised p-4"
    >
      <h2 className="text-h2 text-fg-primary">Offene Alarme</h2>
      <FiveState state={state} label="Alarme">
        {(alarms, freshness) => {
          const rows = alarms
            .filter((alarm) => alarm.machine_id === machineId)
            .map((alarm) => buildAlarmViewModel(alarm, { machines, shelf, now, newIds }))
            .filter((vm) => vm.baseLifecycle !== "cleared");

          if (rows.length === 0) {
            return <p className="text-body text-fg-muted">Keine offenen Alarme für diese Maschine.</p>;
          }

          return (
            <div className="flex flex-col gap-2">
              <ul className="flex flex-col">
                {rows.map((vm) => (
                  <AlarmRow
                    key={vm.id}
                    vm={vm}
                    canAcknowledge={canAcknowledge}
                    online={online}
                    onAcknowledged={refetch}
                    onShelve={onShelve}
                    onUnshelve={onUnshelve}
                  />
                ))}
              </ul>
              <div className="flex justify-end">
                <ProvenanceStamp freshness={freshness} stampedAt={stampedAt} />
              </div>
            </div>
          );
        }}
      </FiveState>
    </section>
  );
}
