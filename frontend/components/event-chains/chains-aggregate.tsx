// ============================================================
//  FOREMAN Frontend — components/event-chains/chains-aggregate.tsx
//  Zweck: Die Manager-Variante (Studie §3.1 Zeile D / §4D): VERDICHTETE
//         Zusammenfassung — eine Kennzahl (Anzahl gespeicherter Ketten) + je Kette
//         EIN Satz, NICHT die volle Erzählung und keine Zeitachse. Fünf
//         Pflichtzustände (FiveState).
//  Architektur-Einordnung: Aggregat-Molekül (Schicht 2, client).
// ============================================================
"use client";

import { toSummary } from "@/lib/event-chains/view-model";
import { useSavedChains } from "@/lib/event-chains/use-saved-chains";
import { FiveState } from "@/lib/ui/five-states";

const MAX_SENTENCES = 8;

export function ChainsAggregate() {
  const { state } = useSavedChains(null);
  return (
    <section className="flex flex-col gap-4" aria-label="Ereignisketten — Überblick">
      <h1 className="text-h1 text-fg-primary">Ereignisketten</h1>
      <FiveState
        state={state}
        label="Ereignisketten"
        empty={
          <div role="status" className="rounded-lg border border-line-subtle bg-surface-raised p-4 text-body text-fg-muted">
            Noch keine Ketten gespeichert.
          </div>
        }
      >
        {(list) => {
          const summaries = list.map(toSummary);
          return (
            <div className="flex flex-col gap-4">
              <div className="flex flex-col gap-1 rounded-lg border border-line-subtle bg-surface-raised p-4">
                <span className="text-caption text-fg-muted">Gespeicherte Ketten</span>
                <span className="text-kpi font-semibold leading-none tabular-nums text-fg-primary">
                  {list.length}
                </span>
              </div>
              <ul className="flex flex-col gap-2">
                {summaries.slice(0, MAX_SENTENCES).map((summary) => (
                  <li
                    key={summary.explanationId}
                    className="rounded-lg border border-line-subtle bg-surface-raised p-3 text-body text-fg-secondary"
                  >
                    {summary.sentence}
                  </li>
                ))}
              </ul>
            </div>
          );
        }}
      </FiveState>
    </section>
  );
}
