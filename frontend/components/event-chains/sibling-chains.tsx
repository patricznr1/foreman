// ============================================================
//  FOREMAN Frontend — components/event-chains/sibling-chains.tsx
//  Zweck: Die Schwesterketten-Querverweise (Studie §4D, §21-D): ehrlich aus realen
//         Recall-Treffern. Ein Verweis ist NUR dann klickbar („springe zur Kette der
//         Schwestermaschine"), wenn eine reale Ziel-Erklärung existiert; sonst ein
//         stiller, nicht-klickbarer Beleg-Hinweis (Basis + Auszug). Keine Treffer →
//         der Block erscheint GAR NICHT (graceful, kein Fake-Leerzustand).
//  Architektur-Einordnung: Querverweis-Molekül (Schicht 2).
// ============================================================
"use client";

import { siblingLabel } from "@/lib/event-chains/siblings";
import type { SiblingModel } from "@/lib/event-chains/types";

export interface SiblingChainsProps {
  siblings: SiblingModel[];
  /** Öffnet die Kette einer Schwestermaschine (nur für navigierbare Verweise). */
  onOpen: (explanationId: number) => void;
}

export function SiblingChains({ siblings, onOpen }: SiblingChainsProps) {
  // Keine realen Schwester-Treffer → der Block erscheint nicht (kein Fake).
  if (siblings.length === 0) {
    return null;
  }
  return (
    <section aria-label="Schwesterketten" className="flex flex-col gap-2">
      <h3 className="text-caption font-semibold uppercase tracking-wide text-fg-secondary">
        Schwesterketten
      </h3>
      <ul className="flex flex-col gap-2">
        {siblings.map((sibling, index) => {
          const label = siblingLabel(sibling);
          const inner = (
            <>
              <span className="flex flex-wrap items-baseline gap-x-2">
                <span className="text-body text-fg-primary">{label}</span>
                <span className="text-caption text-fg-muted">{sibling.basis}</span>
              </span>
              <span className="text-caption text-fg-secondary">{sibling.excerpt}</span>
            </>
          );
          return (
            <li key={sibling.explanationId ?? `${sibling.recallRef ?? "ref"}-${index}`}>
              {sibling.navigable && sibling.explanationId !== null ? (
                <button
                  type="button"
                  onClick={() => onOpen(sibling.explanationId as number)}
                  aria-label={`Zur Kette der ${label} springen`}
                  className="flex w-full flex-col gap-1 rounded-lg border border-line-strong bg-surface-raised p-3 text-left transition-colors duration-[var(--motion-base)] motion-reduce:transition-none hover:bg-surface-overlay focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
                >
                  {inner}
                </button>
              ) : (
                <div className="flex flex-col gap-1 rounded-lg border border-line-subtle bg-surface-raised p-3">
                  {inner}
                  <span className="text-caption text-fg-muted">
                    Keine gespeicherte Kette zum Anspringen — nur als ähnlicher Fall vermerkt.
                  </span>
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
