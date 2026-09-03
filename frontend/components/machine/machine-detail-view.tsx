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

import { useId, useState } from "react";

import type { CurrentUser, DataPointRead, MachineCardOut, MachineRead } from "@/lib/api/contracts";
import { machineRoleView } from "@/lib/machine/roles";
import { useTimeViewport } from "@/lib/machine/use-time-viewport";

import { SavedChainsBrowser } from "@/components/event-chains/saved-chains-browser";
import { PredictionPanel } from "@/components/prediction/prediction-panel";
import { chainRoleView } from "@/lib/event-chains/roles";
import { predictionRoleView } from "@/lib/prediction/roles";

import { MachineAlarms } from "./machine-alarms";
import { MachineCard } from "./machine-card";
import type { MachineEinblendung } from "./machine-cross-links";
import { MachineHeader } from "./machine-header";
import { MachineHistory } from "./machine-history";
import { PinnedChains } from "./pinned-chains";
import { MachineTrendPanel } from "./machine-trend-panel";
import { SensorPicker } from "./sensor-picker";
import { ViewportBar } from "./viewport-bar";

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

  // Der Ausschnitt loest die feste Fensterwahl ab und wird von ALLEN gestapelten
  // Panels geteilt. Kein zweiter Zustand daneben: Zwei Kurven mit verschiedenen
  // Zeitachsen uebereinander behaupten eine Gleichzeitigkeit, die es nicht gibt —
  // und zwar unsichtbar, weil das Auge vertikale Buendigkeit als Zeit-Buendigkeit
  // liest.
  const vp = useTimeViewport();
  const [selected, setSelected] = useState<number[]>(initialSelected);

  // Vorhersage und Ereignisketten werden AN ORT UND STELLE gezeigt statt
  // weggeführt. Immer nur EINE von beiden: Zwei gleichzeitig geöffnete Bereiche
  // schöben den Sensorverlauf — den eigentlichen Gegenstand dieser Sicht — aus
  // dem Bild, und genau den will man beim Beurteilen daneben haben.
  const [offen, setOffen] = useState<MachineEinblendung>(null);
  const [ketteId, setKetteId] = useState<number | null>(null);
  const vorhersageId = useId();
  const kettenId = useId();
  // Die Ketten-Rolle ist eine ANDERE als die Maschinen-Rolle (Sektion D gegen B).
  const kettenRolle = chainRoleView(user.role);
  // Und die Vorhersage-Rolle wieder eine dritte (Sektion E). Drei Sektionen, drei
  // Rollensichten — sie hier zu vermischen waere die Stelle, an der eine Ansicht
  // mehr zeigte, als der Server der Rolle zugesteht.
  const vorhersageRolle = predictionRoleView(user.role);

  const toggleEinblendung = (was: Exclude<MachineEinblendung, null>): void => {
    // Nochmals derselbe Knopf schließt — sonst gäbe es keinen Weg zurück zur
    // ungeteilten Sicht ausser über das Neuladen der Seite.
    setOffen((vorher) => (vorher === was ? null : was));
  };

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
      <MachineHeader
        machine={machine}
        roleView={roleView}
        offen={offen}
        onToggle={toggleEinblendung}
        vorhersageId={vorhersageId}
        kettenId={kettenId}
      />

      {/* Die eingeblendeten Bereiche stehen DIREKT unter ihren Schaltern: Wer
          drückt, soll das Ergebnis sehen, ohne zu suchen oder zu scrollen. */}
      {offen === "vorhersage" ? (
        <div id={vorhersageId}>
          <PredictionPanel
            machineId={machine.id}
            roleView={vorhersageRolle}
            label={machine.label}
            heading="Ausfallvorhersage"
          />
        </div>
      ) : null}

      {offen === "ketten" ? (
        <section
          id={kettenId}
          aria-label="Ereignisketten dieser Maschine"
          className="flex flex-col gap-3 rounded-lg border border-line-subtle bg-surface-raised p-4"
        >
          <h2 className="text-h2 text-fg-primary">Ereignisketten</h2>
          {/* Ohne Anker-Alarm gibt es nichts zu REKONSTRUIEREN — eine Kette hängt
              an einem Alarm, nicht an einer Maschine. Gezeigt werden deshalb die
              gespeicherten; rekonstruieren lässt sich über den Querlink „Kette"
              an einer Alarmzeile weiter unten. */}
          <SavedChainsBrowser
            machineId={machine.id}
            selectedId={ketteId}
            onSelect={setKetteId}
            canPin={kettenRolle.canPin}
            showHeading={false}
          />
        </section>
      ) : null}

      <section
        aria-label="Sensortrend"
        className="flex flex-col gap-3 rounded-lg border border-line-subtle bg-surface-raised p-4"
      >
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-h2 text-fg-primary">Sensortrend</h2>
          <ViewportBar
            viewport={vp.viewport}
            announcement={vp.announcement}
            onQuickPick={vp.quickPick}
            onZoom={vp.zoom}
            onPan={vp.pan}
            onNow={vp.toNow}
          />
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
                viewport={vp.viewport}
                hours={vp.hours}
                onPan={vp.pan}
                onZoom={vp.zoom}
                onGestureEnd={vp.endGesture}
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
