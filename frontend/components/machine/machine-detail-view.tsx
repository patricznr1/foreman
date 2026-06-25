// ============================================================
//  FOREMAN Frontend — components/machine/machine-detail-view.tsx
//  Zweck: Orchestrator der Maschinen-Detail-Sicht (Sektion B, [KERN]). Komponiert den
//         Kopf (Identität + FCSM + Schnellaktionen), den Sensortrend (Zeitfenster +
//         Sensorauswahl + gestapelte Panels), Stammdaten, Historie und offene Alarme.
//         Leserichtung (Studie §4B): Zustand jetzt (oben) → Verlauf (Mitte, größte
//         Fläche) → Kontext/Historie (unten). Rollen-Split OHNE bedingte Hooks: die
//         Hooks laufen immer, die Rolle gated über roleView (Schnellaktionen, Quittieren,
//         Sensordichte). Sichtbarkeit ≤ Server-Guard (requireSection("B") in der Route).
//         Manager: verdichtet (reduzierte Sensoren) + keine Einzelaktion (gated).
//  Architektur-Einordnung: Sicht (Schicht 3, client). Liest nur abgeleiteten State.
// ============================================================
"use client";

import { useState } from "react";

import type { CurrentUser, DataPointRead, MachineCardOut, MachineRead } from "@/lib/api/contracts";
import { machineRoleView } from "@/lib/machine/roles";
import { DEFAULT_TIME_WINDOW, type TimeWindowId, timeWindow } from "@/lib/machine/time-window";

import { MachineAlarms } from "./machine-alarms";
import { MachineCard } from "./machine-card";
import { MachineHeader } from "./machine-header";
import { MachineHistory } from "./machine-history";
import { PinnedChains } from "./pinned-chains";
import { MachineTrendPanel } from "./machine-trend-panel";
import { SensorPicker } from "./sensor-picker";
import { TimeWindowPicker } from "./time-window-picker";

export interface MachineDetailViewProps {
  user: CurrentUser;
  machine: MachineRead;
  dataPoints: DataPointRead[];
  /** Die lebende Maschinenkarte (Stammdaten + Datenpunkte mit Wert + Status). */
  card: MachineCardOut;
}

export function MachineDetailView({ user, machine, dataPoints, card }: MachineDetailViewProps) {
  const roleView = machineRoleView(user.role);
  const reduced = roleView.sensorDetail === "reduced";
  const maxSensors = reduced ? 1 : 4;

  // Aussagekräftige (analoge) Messkurven zuerst als Default — der digitale Laufzustand
  // (machine_running) ist als Erstbild wenig aussagekräftig. Stabiler Sort hält die
  // Reihenfolge innerhalb der Gruppen; ohne analoge Sensoren bleibt die Original-Folge.
  const meaningfulFirst = [...dataPoints].sort(
    (a, b) => Number(a.kind !== "analog") - Number(b.kind !== "analog"),
  );
  const initialSelected = meaningfulFirst
    .slice(0, reduced ? 1 : Math.min(2, dataPoints.length))
    .map((dp) => dp.id);

  const [windowId, setWindowId] = useState<TimeWindowId>(DEFAULT_TIME_WINDOW);
  const [selected, setSelected] = useState<number[]>(initialSelected);

  const hours = timeWindow(windowId).hours;
  const selectedDataPoints = dataPoints.filter((dp) => selected.includes(dp.id));

  const toggleSensor = (id: number): void => {
    setSelected((prev) => {
      if (prev.includes(id)) {
        return prev.filter((existing) => existing !== id);
      }
      if (prev.length >= maxSensors) {
        return prev;
      }
      return [...prev, id];
    });
  };

  return (
    <div className="flex flex-col gap-6">
      <MachineHeader machine={machine} roleView={roleView} />

      <section
        aria-label="Sensortrend"
        className="flex flex-col gap-3 rounded-lg border border-line-subtle bg-surface-raised p-4"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-h2 text-fg-primary">Sensortrend</h2>
          <TimeWindowPicker value={windowId} onChange={setWindowId} />
        </div>

        {dataPoints.length > 0 ? (
          <SensorPicker dataPoints={dataPoints} selected={selected} onToggle={toggleSensor} max={maxSensors} />
        ) : (
          <p className="text-body text-fg-muted">Keine Datenpunkte für diese Maschine hinterlegt.</p>
        )}

        <div className="flex flex-col gap-4">
          {selectedDataPoints.length > 0 ? (
            selectedDataPoints.map((dataPoint) => (
              <MachineTrendPanel
                key={dataPoint.id}
                machineId={machine.id}
                dataPoint={dataPoint}
                hours={hours}
                reduced={reduced}
              />
            ))
          ) : (
            <p className="text-body text-fg-muted">Kein Sensor ausgewählt.</p>
          )}
        </div>
      </section>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Die lebende Maschinenkarte trägt die Stammdaten-Sicht (ersetzt machine-specs):
            Steckbrief + Datenpunkte mit aktuellem Wert + Status, live über machine:{id}. */}
        <MachineCard initial={card} density="full" />
        <MachineAlarms
          machineId={machine.id}
          machineLabel={machine.label}
          lineId={machine.line_id}
          canAcknowledge={roleView.canAcknowledge}
        />
      </div>

      {/* Additiv (§4D): an diese Maschine angepinnte Ereignisketten mit eingefrorenem Stand. */}
      <PinnedChains machineId={machine.id} />

      <MachineHistory machineId={machine.id} />
    </div>
  );
}
