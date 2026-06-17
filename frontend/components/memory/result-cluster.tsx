// ============================================================
//  FOREMAN Frontend — components/memory/result-cluster.tsx
//  Zweck: Verdichtung der Trefferliste (Studie §4H: "verdichten statt zehn
//         Einzelzeilen"). Bündelt die Treffer EINER Maschine in einer aufklappbaren
//         Gruppe — die Verknüpfung ist der Wert, nicht die rohe Liste. Der
//         Auflösungs-Bezug ("alle gelöst durch …") ist graceful: das Gedächtnis
//         führt kein Auflösungsfeld → sichtbar als folgt markiert, nicht erfunden.
//         <details>/<summary> ist nativ tastaturbedienbar.
//  Architektur-Einordnung: Sektions-Molekül (Schicht 2). Rein präsentational.
// ============================================================
import type { MemoryRoleView } from "@/lib/memory/roles";
import type { MemoryCluster } from "@/lib/memory/types";
import { SearchResultCard } from "./search-result-card";

export interface ResultClusterProps {
  cluster: MemoryCluster;
  /** Gesamtzahl Treffer der Suche (für den Rang-Text der Karten). */
  total: number;
  roleView: MemoryRoleView;
  /** Aufgeklappt starten (z. B. Manager-Mustersicht). */
  defaultOpen?: boolean;
}

export function ResultCluster({ cluster, total, roleView, defaultOpen = false }: ResultClusterProps) {
  const count = cluster.hits.length;
  return (
    <details open={defaultOpen} className="rounded-lg border border-line-strong bg-surface-raised">
      <summary className="flex min-h-[var(--touch-min)] cursor-pointer flex-wrap items-center justify-between gap-2 px-4 py-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring">
        <span className="text-body font-medium text-fg-primary">
          {count} Hinweise an Maschine {cluster.machineId}
        </span>
        {cluster.sharedResolution ? (
          <span className="text-caption text-fg-secondary">
            alle gelöst durch {cluster.sharedResolution}
          </span>
        ) : (
          <span className="text-caption text-fg-muted">gemeinsame Auflösung folgt</span>
        )}
      </summary>
      <div className="flex flex-col gap-3 border-t border-line-subtle p-3">
        {cluster.hits.map((hit) => (
          <SearchResultCard key={hit.id} hit={hit} total={total} roleView={roleView} />
        ))}
      </div>
    </details>
  );
}
