// ============================================================
//  FOREMAN Frontend — components/memory/memory-result-list.tsx
//  Zweck: Die Ergebnisliste der Bedeutungssuche (Studie §4H): Treffer nach Nähe
//         sortiert, mit VERDICHTUNG (Cluster je Maschine) statt roher Liste, und
//         der Verknüpfungs-Ansicht daneben. Rollen-Layout: Werker flache große
//         Karten; Schichtleiter/Techniker Cluster + Verknüpfung; Manager Muster
//         zuerst, Einzelfälle eingeklappt. Höfliche Live-Region NUR beim frischen
//         Treffer (`announce`) — ein aus dem Cache rehydriertes Ergebnis beim
//         Seiteneintritt sagt NICHT ungefragt einen alten Stand an (§5.8).
//  Architektur-Einordnung: Sektions-Orchestrierung (Schicht 2, client).
// ============================================================
"use client";

import { useEffect, useRef, useState } from "react";
import type { MemoryRoleView } from "@/lib/memory/roles";
import type { MemorySearchResult } from "@/lib/memory/types";
import { cx } from "@/lib/ui/cx";
import { RelationView } from "./relation-view";
import { ResultCluster } from "./result-cluster";
import { SearchResultCard } from "./search-result-card";

export interface MemoryResultListProps {
  result: MemorySearchResult;
  roleView: MemoryRoleView;
  /** Live-Region ansagen? Nur für frisch geholte Treffer true — nicht für ein
   *  beim Eintritt aus dem Cache rehydriertes oder degradiertes Ergebnis. */
  announce: boolean;
}

function countText(total: number): string {
  if (total === 0) {
    return "Keine ähnlichen Fälle gefunden";
  }
  return total === 1 ? "1 ähnlicher Fall gefunden" : `${total} ähnliche Fälle gefunden`;
}

export function MemoryResultList({ result, roleView, announce }: MemoryResultListProps) {
  // Live-Region: bei jedem NEUEN frischen Ergebnis ansagen; Parity-Suffix sorgt
  // dafür, dass auch eine identische Folgemeldung als Textänderung erkannt wird.
  // Bei announce=false (Cache-/Degradations-Render) bleibt die Region still.
  const [announceText, setAnnounceText] = useState("");
  const nonce = useRef(0);
  useEffect(() => {
    if (!announce) {
      setAnnounceText("");
      return;
    }
    nonce.current += 1;
    const suffix = nonce.current % 2 === 0 ? "" : " ";
    setAnnounceText(`${countText(result.total)}${suffix}`);
  }, [result, announce]);

  const showClusters = !roleView.largeCards && result.clusters.length > 0;
  const clusteredIds = new Set(
    showClusters ? result.clusters.flatMap((cluster) => cluster.hits.map((hit) => hit.id)) : [],
  );
  const standalone = result.hits.filter((hit) => !clusteredIds.has(hit.id));

  return (
    <div className="flex flex-col gap-4">
      <p className="sr-only" role="status" aria-live="polite">
        {announceText}
      </p>

      {result.query ? (
        <p className="text-caption text-fg-muted">Ähnliche Fälle zu: {result.query}</p>
      ) : null}

      {result.total === 0 ? (
        <div
          role="status"
          className="flex min-h-24 items-center rounded-lg border border-line-subtle bg-surface-raised p-4 text-body text-fg-muted"
        >
          Keine ähnlichen Fälle gefunden — versuchen Sie eine andere Beschreibung.
        </div>
      ) : (
        <div className={cx(roleView.showRelations && "lg:grid lg:grid-cols-3 lg:gap-5")}>
          <div className={cx("flex flex-col gap-3", roleView.showRelations && "lg:col-span-2")}>
            {showClusters
              ? result.clusters.map((cluster) => (
                  <ResultCluster
                    key={cluster.machineId}
                    cluster={cluster}
                    total={result.total}
                    roleView={roleView}
                    defaultOpen={roleView.aggregateFirst}
                  />
                ))
              : null}

            {roleView.aggregateFirst && showClusters && standalone.length > 0 ? (
              <details className="rounded-lg border border-line-subtle bg-surface-raised">
                <summary className="flex min-h-[var(--touch-min)] cursor-pointer items-center px-4 py-3 text-body text-fg-secondary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring">
                  Einzelne Treffer ({standalone.length})
                </summary>
                <div className="flex flex-col gap-3 border-t border-line-subtle p-3">
                  {standalone.map((hit) => (
                    <SearchResultCard key={hit.id} hit={hit} total={result.total} roleView={roleView} />
                  ))}
                </div>
              </details>
            ) : (
              standalone.map((hit) => (
                <SearchResultCard key={hit.id} hit={hit} total={result.total} roleView={roleView} />
              ))
            )}
          </div>

          {roleView.showRelations ? (
            <div className="mt-4 lg:mt-0">
              <RelationView relations={result.relations} />
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
