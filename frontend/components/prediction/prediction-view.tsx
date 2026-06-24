// ============================================================
//  FOREMAN Frontend — components/prediction/prediction-view.tsx
//  Zweck: Rollen-Split der Sektion E (Studie §3.1/§4E) OHNE bedingte Hooks:
//         Manager → aggregiertes Risikobild (nie Einzelempfehlung); Werker/
//         Techniker/Schichtleiter → On-Demand-Panel je Maschine. Sichtbarkeit
//         ≤ Backend-Autorisierung (der Server-Guard bleibt die Autorität).
//  Architektur-Einordnung: Sektions-Einstieg (Schicht 2, client).
// ============================================================
"use client";

import { useEffect, useState } from "react";
import type { CurrentUser } from "@/lib/api/contracts";
import { type PredictionRoleView, predictionRoleView } from "@/lib/prediction/roles";
import { useFleetMachines } from "@/lib/prediction/use-fleet-machines";
import { PredictionAggregate } from "./prediction-aggregate";
import { PredictionPanel } from "./prediction-panel";

export function PredictionView({ user }: { user: CurrentUser }) {
  const roleView = predictionRoleView(user.role);
  // aggregateOnly = restriktive Fallback-Sicht (unbekannte Rolle, default-deny);
  // der manager ist jetzt Vollzugriff (§21.10) mit eigenem Flotten-Zweig.
  if (roleView.aggregateOnly) {
    return <PredictionAggregate />;
  }
  if (user.role === "manager") {
    return <ManagerPredictionView roleView={roleView} />;
  }
  return <PredictionSingle user={user} roleView={roleView} />;
}

/** Manager (Werksleiter-/Vorführ-Vollzugriff, §21.10): das Risikobild als Überblicks-
 *  Kopf ÜBER der vollen Einzelsicht. Die Maschinen-Auswahl kommt aus der Flotte
 *  (GET /machines) — der manager hat keine zugewiesene Maschine, sieht aber alle.
 *  Anfordern (Trigger) und Entscheiden (HITL) erlaubt; KEINE Anlagen-Aktorik. */
function ManagerPredictionView({ roleView }: { roleView: PredictionRoleView }) {
  const fleet = useFleetMachines();
  const [selected, setSelected] = useState<number | null>(null);

  useEffect(() => {
    if (fleet.kind === "ready" && selected === null) {
      setSelected(fleet.machines[0]?.id ?? null);
    }
  }, [fleet, selected]);

  const selectedLabel =
    fleet.kind === "ready"
      ? (fleet.machines.find((machine) => machine.id === selected)?.label ?? `Maschine ${selected}`)
      : `Maschine ${selected}`;

  return (
    <div className="flex flex-col gap-6">
      {/* Überblick: Risikobild über die Flotte (Werksleiter sieht zuerst das Muster). */}
      <PredictionAggregate />

      {/* Detail: eine einzelne Maschine anfordern/lesen (Vollzugriff). */}
      {fleet.kind === "loading" ? (
        <div role="status" className="rounded-lg border border-line-subtle bg-surface-raised p-4 text-body text-fg-muted">
          Maschinen laden …
        </div>
      ) : fleet.kind === "error" ? (
        <div role="alert" className="rounded-lg border border-line-subtle bg-surface-raised p-4 text-body text-note-caveat">
          Maschinenliste derzeit nicht verfügbar.
        </div>
      ) : fleet.kind === "empty" || selected === null ? (
        <div role="status" className="rounded-lg border border-line-subtle bg-surface-raised p-4 text-body text-fg-muted">
          Keine Maschinen vorhanden.
        </div>
      ) : (
        <div className="flex flex-col gap-4">
          {fleet.machines.length > 1 ? (
            <div className="flex flex-wrap items-center gap-2">
              <label htmlFor="prediction-machine" className="text-caption text-fg-muted">
                Maschine
              </label>
              <select
                id="prediction-machine"
                value={selected}
                onChange={(event) => setSelected(Number(event.target.value))}
                className="min-h-[var(--touch-min)] rounded-md border border-line-strong bg-surface-overlay px-3 text-body text-fg-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
              >
                {fleet.machines.map((machine) => (
                  <option key={machine.id} value={machine.id}>
                    {machine.label}
                  </option>
                ))}
              </select>
            </div>
          ) : null}
          <PredictionPanel key={selected} machineId={selected} roleView={roleView} label={selectedLabel} />
        </div>
      )}
    </div>
  );
}

function PredictionSingle({ user, roleView }: { user: CurrentUser; roleView: PredictionRoleView }) {
  const machines = user.assigned_machine_ids;
  const [selected, setSelected] = useState<number | null>(machines[0] ?? null);

  if (machines.length === 0 || selected === null) {
    return (
      <div role="status" className="rounded-lg border border-line-subtle bg-surface-raised p-4 text-body text-fg-muted">
        Keine Maschine zugeordnet — die Maschinen-Auswahl folgt mit der Maschinensicht (B).
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-5">
      {machines.length > 1 ? (
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="prediction-machine" className="text-caption text-fg-muted">
            Maschine
          </label>
          <select
            id="prediction-machine"
            value={selected}
            onChange={(event) => setSelected(Number(event.target.value))}
            className="min-h-[var(--touch-min)] rounded-md border border-line-strong bg-surface-overlay px-3 text-body text-fg-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
          >
            {machines.map((id) => (
              <option key={id} value={id}>
                Maschine {id}
              </option>
            ))}
          </select>
        </div>
      ) : null}
      <PredictionPanel
        key={selected}
        machineId={selected}
        roleView={roleView}
        label={`Maschine ${selected}`}
      />
    </div>
  );
}
