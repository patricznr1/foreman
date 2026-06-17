// ============================================================
//  FOREMAN Frontend — components/machine/machine-history.tsx
//  Zweck: Chronologische Ereignis-/Wartungshistorie der Maschine (Pull, blätterbar).
//         PII maskiert (Akteur als #hex6 — nie Klartext; §8). Werker-Notiztext ist
//         backend-seitig bereits NER-maskiert, Wartungs-Beschreibung ist Sachtext.
//         Fünf-Zustände-Hülle + Herkunftsstempel („gecacht, Stand X").
//  Architektur-Einordnung: Sicht-Baustein (Schicht 3, client).
// ============================================================
"use client";

import { ProvenanceStamp } from "@/components/atoms/provenance-stamp";
import type { MachineHistoryItem } from "@/lib/machine/history";
import { useMachineHistory } from "@/lib/machine/use-machine-history";
import { FiveState } from "@/lib/ui/five-states";

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString("de-DE", { dateStyle: "short", timeStyle: "short" });
}

function HistoryRow({ item }: { item: MachineHistoryItem }) {
  const kindLabel = item.kind === "maintenance" ? "Wartung" : "Notiz";
  return (
    <li className="flex flex-col gap-1 border-b border-line-subtle py-2 last:border-b-0">
      <div className="flex items-center justify-between gap-3">
        <span className="text-body text-fg-primary">{item.title}</span>
        <span className="text-caption tabular-nums text-fg-muted">{formatDateTime(item.at)}</span>
      </div>
      {item.body ? <p className="text-body text-fg-secondary">{item.body}</p> : null}
      <div className="flex flex-wrap gap-2 text-caption text-fg-muted">
        <span>{kindLabel}</span>
        {item.shift ? <span>· {item.shift}</span> : null}
        {item.actorMasked ? <span>· erfasst von {item.actorMasked}</span> : null}
      </div>
    </li>
  );
}

export function MachineHistory({ machineId }: { machineId: number }) {
  const { state, loadMore, hasMore, loadingMore, stampedAt } = useMachineHistory({ machineId });

  return (
    <section
      aria-label="Ereignis- und Wartungshistorie"
      className="flex flex-col gap-3 rounded-lg border border-line-subtle bg-surface-raised p-4"
    >
      <h2 className="text-h2 text-fg-primary">Historie</h2>
      <FiveState state={state} label="Historie">
        {(items, freshness) => (
          <div className="flex flex-col gap-3">
            <ul className="flex flex-col">
              {items.map((item) => (
                <HistoryRow key={item.key} item={item} />
              ))}
            </ul>
            <div className="flex items-center justify-between gap-3">
              <ProvenanceStamp freshness={freshness} stampedAt={stampedAt} />
              {hasMore ? (
                <button
                  type="button"
                  onClick={loadMore}
                  disabled={loadingMore}
                  className="touch-target rounded-md border border-line-subtle px-3 text-body text-fg-primary disabled:opacity-60"
                >
                  {loadingMore ? "Lädt …" : "Mehr laden"}
                </button>
              ) : null}
            </div>
          </div>
        )}
      </FiveState>
    </section>
  );
}
