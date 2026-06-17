// ============================================================
//  FOREMAN Frontend — components/prediction/prediction-aggregate.tsx
//  Zweck: Die Manager-Variante (Studie §4E): ein aggregiertes Risikobild über
//         Maschinen — NIE die Einzelempfehlung als Befehl, kein Trigger, kein
//         Empfehlungstext. Verbale Stufe statt Scheingenauigkeit, nach Risiko
//         sortiert (hoch oben). Herkunftsstempel (KI-erzeugt) + Sim-Hinweis, da E
//         eine erzeugte KI-Erkenntnis ist (AI-Act-Transparenz).
//  Architektur-Einordnung: Sektions-Orchestrierung (Schicht 2).
// ============================================================
"use client";

import { useEffect, useRef, useState } from "react";
import { ProvenanceStamp } from "@/components/atoms/provenance-stamp";
import type { FailurePredictionRead } from "@/lib/api/contracts";
import { type RiskAggregate, buildRiskAggregate } from "@/lib/prediction/aggregate";
import { dataRegimeLabel, validationStatusLabel } from "@/lib/prediction/caveat";
import { CONFIDENCE_LEVEL_LABEL } from "@/lib/prediction/confidence";
import { predictionsEndpoint } from "@/lib/prediction/url";

const AGG_LIMIT = 200;

export function PredictionAggregate() {
  const [aggregate, setAggregate] = useState<RiskAggregate | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stampedAt, setStampedAt] = useState<Date | null>(null);
  const inflight = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    inflight.current = controller;
    void (async () => {
      try {
        const response = await fetch(predictionsEndpoint(AGG_LIMIT), {
          credentials: "same-origin",
          signal: controller.signal,
        });
        if (!response.ok) {
          setError(response.status === 403 ? "Kein Zugriff auf diese Sicht" : "Daten derzeit nicht verfügbar");
          return;
        }
        const list = (await response.json()) as FailurePredictionRead[];
        setAggregate(buildRiskAggregate(list));
        setStampedAt(new Date());
        setError(null);
      } catch (caught) {
        if ((caught as Error).name !== "AbortError") {
          setError("Daten derzeit nicht verfügbar");
        }
      }
    })();
    return () => controller.abort();
  }, []);

  if (error !== null) {
    return (
      <div role="alert" className="rounded-lg border border-line-subtle bg-surface-raised p-4 text-body text-note-caveat">
        {error}
      </div>
    );
  }
  if (aggregate === null) {
    return (
      <div role="status" aria-busy className="rounded-lg border border-line-subtle bg-surface-raised p-4 text-body text-fg-muted">
        Risikobild lädt …
      </div>
    );
  }
  if (aggregate.total === 0) {
    return (
      <div role="status" className="rounded-lg border border-line-subtle bg-surface-raised p-4 text-body text-fg-muted">
        Keine Vorhersagen vorhanden.
      </div>
    );
  }

  return (
    <section aria-label="Aggregiertes Risikobild" className="flex w-full max-w-2xl flex-col gap-4">
      <div className="flex flex-wrap items-baseline gap-x-6 gap-y-1">
        <h2 className="text-h2 text-fg-primary">Risikobild</h2>
        <span className="text-body text-fg-secondary">
          {aggregate.elevated} von {aggregate.total} Maschinen mit erhöhtem Risiko
        </span>
      </div>
      <ul className="flex flex-col divide-y divide-line-subtle rounded-lg border border-line-subtle">
        {aggregate.rows.map((row) => (
          <li key={row.machineId} className="flex items-center justify-between gap-3 p-3">
            <span className="text-body text-fg-primary">Maschine {row.machineId}</span>
            <span className="flex items-center gap-2 text-body text-fg-secondary">
              <span aria-hidden="true" className="font-mono">{row.overThreshold ? "▲" : "—"}</span>
              {CONFIDENCE_LEVEL_LABEL[row.level]}
            </span>
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line-subtle pt-3">
        <ProvenanceStamp freshness="cached" stampedAt={stampedAt} aiGenerated caveat />
        <span className="text-caption text-fg-muted">
          {dataRegimeLabel("simulation")} — {validationStatusLabel("simulation_only")}
        </span>
      </div>
    </section>
  );
}
