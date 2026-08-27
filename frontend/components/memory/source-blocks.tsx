// ============================================================
//  FOREMAN Frontend — components/memory/source-blocks.tsx
//  Zweck: Unter der Rangliste dieselben Treffer noch einmal, nach QUELLE
//         geordnet und je Quelle aufklappbar. Beantwortet die Frage, die eine
//         gemischte Liste nicht beantwortet: „Was hat das Wartungslog dazu?"
//  Architektur-Einordnung: Sektions-Molekül (Schicht 2). Rein präsentational.
//
//  ZUGEKLAPPT PER DEFAULT, und das ist kein Geschmack: Die Treffer stehen oben
//  schon vollständig. Aufgeklappt zeigte die Seite jeden Vorgang zweimal — und
//  der Werker müsste dreißig Karten scrollen, um fünfzehn zu lesen. Die
//  Kopfzeilen allein tragen die Auskunft, um die es geht: wie sich die Antwort
//  auf die Quellen verteilt.
//
//  `<details>`/`<summary>` statt eigenem Zustand: Aufklappen, Tastaturbedienung
//  und die Ansage an Vorlesewerkzeuge kommen vom Browser. Ein nachgebauter
//  Umschalter müsste all das selbst richtig machen, und meistens tut er es nicht.
// ============================================================
import { anzahlBestaetigt, gruppiereNachQuelle } from "@/lib/memory/gruppen";
import { hitKey } from "@/lib/memory/source";
import type { ArchiveHitView } from "@/lib/memory/types";
import { ArchiveResultCard } from "./archive-result-card";
import { SourceGlyph } from "./source-glyph";

export interface SourceBlocksProps {
  hits: ArchiveHitView[];
  /** Werker: große, knappe Karten (wird an die Trefferkarten durchgereicht). */
  largeCards: boolean;
}

function trefferText(anzahl: number): string {
  return anzahl === 1 ? "1 Treffer" : `${anzahl} Treffer`;
}

export function SourceBlocks({ hits, largeCards }: SourceBlocksProps) {
  const gruppen = gruppiereNachQuelle(hits);
  // Bei einer einzigen Quelle sagt die Aufteilung nichts, was die Liste darüber
  // nicht schon sagt — dann bleibt der Abschnitt ganz weg, statt eine
  // Gliederung vorzutäuschen, die keine ist.
  if (gruppen.length < 2) {
    return null;
  }

  return (
    <section aria-labelledby="quellen-aufteilung" className="flex flex-col gap-2">
      <h2 id="quellen-aufteilung" className="text-caption text-fg-muted">
        Nach Quelle
      </h2>

      {gruppen.map((gruppe) => {
        const bestaetigt = anzahlBestaetigt(gruppe.hits);
        return (
          <details
            key={gruppe.source}
            className="rounded-lg border border-line-subtle bg-surface-raised"
          >
            <summary className="flex cursor-pointer flex-wrap items-center gap-x-3 gap-y-1 p-3 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring">
              <SourceGlyph source={gruppe.source} />
              <span className="text-caption text-fg-secondary">
                {trefferText(gruppe.hits.length)}
              </span>
              {/* Nur wenn es etwas zu sagen gibt: „0 bestätigt" ist keine Auskunft. */}
              {bestaetigt > 0 ? (
                <span className="text-caption text-fg-muted">
                  {bestaetigt} davon auch im Gedächtnis
                </span>
              ) : null}
            </summary>

            <div className="flex flex-col gap-3 border-t border-line-subtle p-3">
              {gruppe.hits.map((hit) => (
                <ArchiveResultCard key={hitKey(hit)} hit={hit} largeCards={largeCards} />
              ))}
            </div>
          </details>
        );
      })}

      <p className="text-caption text-fg-muted">
        Dieselben Treffer wie oben, nur nach Herkunft sortiert — die Aufteilung ist keine zweite
        Suche.
      </p>
    </section>
  );
}
