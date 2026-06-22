// ============================================================
//  FOREMAN Frontend — components/event-chains/saved-chains-list.tsx
//  Zweck: Liste der GESPEICHERTEN Ketten (Studie §4D): jüngste zuerst, optional je
//         Maschine gefiltert. Fünf Pflichtzustände (FiveState). Klick öffnet die
//         eingefrorene Kette im Detail. Zustandsübergänge: leer → rekonstruiert →
//         gespeichert. On-Demand = Momentaufnahme → Frische „gecacht".
//  Architektur-Einordnung: Listen-Molekül (Schicht 2, client).
// ============================================================
"use client";

import { confidenceLabel } from "@/lib/event-chains/confidence";
import { useSavedChains } from "@/lib/event-chains/use-saved-chains";
import { FiveState } from "@/lib/ui/five-states";

function formatDate(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export interface SavedChainsListProps {
  machineId: number | null;
  selectedId: number | null;
  onOpen: (explanationId: number) => void;
}

export function SavedChainsList({ machineId, selectedId, onOpen }: SavedChainsListProps) {
  const { state } = useSavedChains(machineId);
  return (
    <FiveState
      state={state}
      label="Gespeicherte Ketten"
      empty={
        <div role="status" className="rounded-lg border border-line-subtle bg-surface-raised p-4 text-body text-fg-muted">
          Noch keine Kette gespeichert — eine Kette aus einem Alarm rekonstruieren.
        </div>
      }
    >
      {(list) => (
        <ul aria-label="Gespeicherte Ketten" className="flex flex-col gap-2">
          {list.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                onClick={() => onOpen(item.id)}
                aria-pressed={item.id === selectedId}
                className={`flex w-full flex-col gap-1 rounded-lg border p-3 text-left transition-colors duration-[var(--motion-base)] motion-reduce:transition-none hover:bg-surface-overlay focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring ${
                  item.id === selectedId
                    ? "border-line-strong bg-surface-overlay"
                    : "border-line-subtle bg-surface-raised"
                }`}
              >
                <span className="flex flex-wrap items-baseline gap-x-2">
                  <span className="text-body text-fg-primary">
                    Alarm #{item.anchor_alarm_id}
                    {item.machine_id !== null ? ` · Maschine ${item.machine_id}` : ""}
                  </span>
                  {item.is_hypothesis ? (
                    <span className="text-caption text-note-caveat">Hypothese</span>
                  ) : null}
                </span>
                <span className="flex flex-wrap items-baseline gap-x-2 text-caption text-fg-muted">
                  <span>{confidenceLabel(item.confidence)}</span>
                  <span className="tabular-nums">Stand {formatDate(item.created_at)}</span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </FiveState>
  );
}
