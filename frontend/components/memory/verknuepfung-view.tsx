// ============================================================
//  FOREMAN Frontend — components/memory/verknuepfung-view.tsx
//  Zweck: Die VERKNÜPFUNG über den Treffern des Gedächtnisses (Studie §4H:
//         „die Verknüpfung ist der Wert, nicht die rohe Trefferliste") — Beziehungen
//         zwischen den Fällen plus Verdichtung nach Maschine.
//  Warum sie erst jetzt erscheint: Die Logik (cluster.ts / relations.ts) liegt seit
//         Paket 1c gebaut und geprüft im Code, war aber bewusst NICHT gerendert —
//         das Versprechen „Hatten wir das schon mal" hatte keine Substanz. Seit dem
//         27.08.2026 hängt die vierte Quelle dran und seit dem 28.08.2026 trägt jede
//         Erinnerung ihr Bauteil; damit gibt es etwas zu verknüpfen.
//  Warum NICHT ResultCluster/SearchResultCard (die eingefrorenen Bausteine): Beide
//         sind auf Schichtnotizen zugeschnitten — die Karte beschriftet JEDEN Treffer
//         als „Schichtnotiz", und die Gruppe keyt auf `hit.id`, den Erinnerungen
//         nicht haben (alle 0). Über vier Quellen gerendert wäre beides falsch, das
//         eine sichtbar, das andere still. Die reine LOGIK wird wiederverwendet, die
//         Darstellung nimmt die quellenbewusste ArchiveResultCard.
//  Architektur-Einordnung: Sicht-Baustein (Schicht 3, client). Read-only.
// ============================================================
"use client";

import { clusterByMachine } from "@/lib/memory/cluster";
import { deriveRelations } from "@/lib/memory/relations";
import type { MemoryRoleView } from "@/lib/memory/roles";
import type { ArchiveSearchResult } from "@/lib/memory/types";
import { alsGedaechtnisTreffer, zurueck } from "@/lib/memory/verknuepfung";
import { ArchiveResultCard } from "./archive-result-card";
import { RelationView } from "./relation-view";

export interface VerknuepfungViewProps {
  result: ArchiveSearchResult;
  roleView: MemoryRoleView;
}

export function VerknuepfungView({ result, roleView }: VerknuepfungViewProps) {
  // EINE Übersetzung für beide Ableitungen: Zwei getrennte Aufrufe wären zwei
  // Gelegenheiten, unterschiedlich zu übersetzen.
  const treffer = alsGedaechtnisTreffer(result.hits);
  const relations = deriveRelations(treffer);
  const cluster = clusterByMachine(treffer);

  // Ein einzelner Treffer ist kein Muster, und ohne Beziehungen gibt es nichts zu
  // zeigen. Dann bleibt der Block ganz weg, statt eine leere Überschrift zu setzen:
  // eine Verknüpfungs-Ansicht, die nichts verknüpft, ist ein leeres Versprechen.
  if (relations.length === 0 && cluster.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col gap-4">
      {relations.length > 0 ? <RelationView relations={relations} /> : null}

      {cluster.map((gruppe) => {
        const hits = zurueck(gruppe.hits, result.hits);
        return (
          <details
            key={gruppe.machineId}
            className="rounded-lg border border-line-strong bg-surface-raised"
          >
            <summary className="flex min-h-[var(--touch-min)] cursor-pointer flex-wrap items-center justify-between gap-2 px-4 py-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring">
              <span className="text-body font-medium text-fg-primary">
                {hits.length} Hinweise an Maschine {gruppe.machineId}
              </span>
              {/* Das Gedächtnis führt kein Auflösungsfeld — die gemeinsame Auflösung
                  wird NICHT erfunden, sondern als offen benannt. */}
              <span className="text-caption text-fg-muted">gemeinsame Auflösung folgt</span>
            </summary>
            <div className="flex flex-col gap-3 border-t border-line-subtle p-3">
              {hits.map((hit) => (
                <ArchiveResultCard
                  key={`${hit.source}:${hit.id}:${hit.rank}`}
                  hit={hit}
                  largeCards={roleView.largeCards}
                />
              ))}
            </div>
          </details>
        );
      })}
    </div>
  );
}
