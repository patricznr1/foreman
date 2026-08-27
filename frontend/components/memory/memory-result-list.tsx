// ============================================================
//  FOREMAN Frontend — components/memory/memory-result-list.tsx
//  Zweck: Die Ergebnisliste der ARCHIV-Suche (Paket 1c) — bewusst SCHLICHT: Treffer
//         nach Relevanz-Rang als flache Liste (kein Score, KEINE Verdichtung/
//         Verknüpfung — die assoziativen Komponenten result-cluster/relation-view/
//         relevance-mark bleiben für Paket 3 im Code, werden hier aber NICHT
//         gerendert). DARUNTER dieselben Treffer nach Quelle geordnet und je
//         Quelle aufklappbar (`SourceBlocks`) — die Rangliste beantwortet, was
//         das Beste ist, die Blöcke, woher die Antwort kommt. Höfliche Live-Region NUR beim frischen Treffer (`announce`).
//  Architektur-Einordnung: Sektions-Orchestrierung (Schicht 2, client).
// ============================================================
"use client";

import { useEffect, useRef, useState } from "react";
import { hitKey } from "@/lib/memory/source";
import type { MemoryRoleView } from "@/lib/memory/roles";
import type { ArchiveSearchResult } from "@/lib/memory/types";
import { ArchiveResultCard } from "./archive-result-card";
import { SourceBlocks } from "./source-blocks";

export interface MemoryResultListProps {
  result: ArchiveSearchResult;
  roleView: MemoryRoleView;
  /** Live-Region ansagen? Nur für frisch geholte Treffer true — nicht für ein
   *  beim Eintritt aus dem Cache rehydriertes oder degradiertes Ergebnis. */
  announce: boolean;
}

function countText(total: number): string {
  if (total === 0) {
    return "Keine Treffer im Archiv";
  }
  return total === 1 ? "1 Treffer im Archiv" : `${total} Treffer im Archiv`;
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

  return (
    <div className="flex flex-col gap-4">
      <p className="sr-only" role="status" aria-live="polite">
        {announceText}
      </p>

      {result.query ? (
        <p className="text-caption text-fg-muted">Treffer zu: {result.query}</p>
      ) : null}

      {result.total === 0 ? (
        <div
          role="status"
          className="flex min-h-24 items-center rounded-lg border border-line-subtle bg-surface-raised p-4 text-body text-fg-muted"
        >
          Keine Treffer im Archiv — versuchen Sie ein anderes Stichwort.
        </div>
      ) : (
        <>
          {/* Benannter Bereich, weil es seit den Quellen-Bloecken ZWEI Bereiche
              mit denselben Treffern gibt. Ohne Bezeichnung hoert ein
              Vorlesewerkzeug zweimal dieselbe Karte, ohne zu sagen, wo man
              gerade ist. (Im Browser bleibt der Inhalt eines zugeklappten
              <details> ohnehin aussen vor — die Bezeichnung ist trotzdem die
              ehrlichere Loesung als sich darauf zu verlassen.) */}
          <section aria-label="Treffer nach Relevanz" className="flex flex-col gap-3">
            {result.hits.map((hit) => (
              <ArchiveResultCard key={hitKey(hit)} hit={hit} largeCards={roleView.largeCards} />
            ))}
          </section>

          {/* Die Rangliste beantwortet „was ist das Beste", die Bloecke „woher
              kommt die Antwort". Beides zugleich, weil die Suche beide Fragen
              bekommt: Der Werker will einen Treffer, und er will wissen, ob das
              Wartungslog etwas dazu hat. Zugeklappt, damit die Seite nicht jeden
              Vorgang zweimal zeigt. */}
          <SourceBlocks hits={result.hits} largeCards={roleView.largeCards} />
        </>
      )}
    </div>
  );
}
