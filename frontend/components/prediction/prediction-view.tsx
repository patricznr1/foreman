// ============================================================
//  FOREMAN Frontend — components/prediction/prediction-view.tsx
//  Zweck: Rollen-Split der Sektion E (Studie §3.1/§4E) OHNE bedingte Hooks:
//         Manager → aggregiertes Risikobild (nie Einzelempfehlung); Werker/
//         Techniker/Schichtleiter → On-Demand-Panel je Maschine. Sichtbarkeit
//         ≤ Backend-Autorisierung (der Server-Guard bleibt die Autorität).
//  Architektur-Einordnung: Sektions-Einstieg (Schicht 2, client).
// ============================================================
"use client";

import { useState } from "react";
import type { CurrentUser } from "@/lib/api/contracts";
import { type PredictionRoleView, predictionRoleView } from "@/lib/prediction/roles";
import { PredictionAggregate } from "./prediction-aggregate";
import { PredictionPanel } from "./prediction-panel";

export function PredictionView({ user }: { user: CurrentUser }) {
  const roleView = predictionRoleView(user.role);
  // Manager sieht NUR das Aggregat — eigener Zweig, damit keine bedingten Hooks fallen.
  if (roleView.aggregateOnly) {
    return <PredictionAggregate />;
  }
  return <PredictionSingle user={user} roleView={roleView} />;
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
