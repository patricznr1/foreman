// ============================================================
//  FOREMAN Frontend — components/cockpit/priority-column.tsx
//  Zweck: Die rechte „braucht Blick jetzt"-Spalte (§4A) — die 3–5 dringendsten
//         Einstiege mit ihrem REALEN Querlink-Ziel (kritische Alarme → C, Drift →
//         Ausfallrisiko E, sonst Maschine B). Jeder Eintrag mehrkanalig (FCSM-Symbol
//         + Klartext + Grund). Handschuh-Höhe (touch-target). HITL: nur Navigation.
//  Architektur-Einordnung: Darstellung (Schicht 3). Liest nur abgeleiteten State.
// ============================================================
"use client";

import Link from "next/link";

import { StatusIndicator } from "@/components/atoms/status-indicator";
import type { PriorityEntry, PriorityTarget } from "@/lib/cockpit/priority";

const TARGET_LABEL: Record<PriorityTarget, string> = {
  alarms: "Alarme ansehen",
  prediction: "Ausfallrisiko ansehen",
  machine: "Maschine öffnen",
};

export interface PriorityColumnProps {
  entries: PriorityEntry[];
}

export function PriorityColumn({ entries }: PriorityColumnProps) {
  return (
    <section aria-label="Braucht Blick jetzt" className="flex flex-col gap-3">
      <h2 className="text-h2 text-fg-primary">Braucht Blick jetzt</h2>
      {entries.length === 0 ? (
        <p role="status" className="text-body text-fg-muted">
          Nichts Dringendes im Geltungsbereich.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {entries.map((entry) => (
            <li key={entry.machineId}>
              <Link
                href={entry.href}
                aria-label={`${entry.label}: ${entry.reason} — ${TARGET_LABEL[entry.target]}`}
                className="touch-target flex items-center gap-3 rounded-lg border border-line-subtle bg-surface-raised p-3 hover:border-line-strong focus-visible:outline-none"
              >
                <StatusIndicator status={entry.fcsm} size="s" showLabel={false} />
                <span className="flex flex-1 flex-col">
                  <span className="text-body text-fg-primary">{entry.label}</span>
                  <span className="text-caption text-fg-secondary">{entry.reason}</span>
                </span>
                <span className="text-caption text-fg-muted">{TARGET_LABEL[entry.target]}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
