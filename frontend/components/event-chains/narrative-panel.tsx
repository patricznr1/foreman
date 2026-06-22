// ============================================================
//  FOREMAN Frontend — components/event-chains/narrative-panel.tsx
//  Zweck: Die rechte ERZÄHL-Spalte (Studie §4D). Die Erzählung ist klar als
//         „rekonstruiert" gekennzeichnet; `is_hypothesis` → Hypothese-Kennzeichnung;
//         `confidence` als VERBALE Stufe (nie Prozent); geflaggte/unbelegte Inhalte
//         werden SICHTBAR gemacht (Ehrlichkeit). Quell-Chips ([source_id]) koppeln
//         an die Zeitachse (gekoppeltes Hervorheben). KEINE Severity-Farbe.
//  Architektur-Einordnung: Erzähl-Molekül (Schicht 2).
// ============================================================
"use client";

import { CONFIDENCE_LABEL } from "@/lib/event-chains/confidence";
import type { ChainCardModel } from "@/lib/event-chains/types";
import { cx } from "@/lib/ui/cx";

export interface NarrativePanelProps {
  card: ChainCardModel;
  /** Indizes der aktuell hervorgehobenen Erzähl-Segmente (gekoppeltes Hervorheben). */
  activeSegmentIndices: number[];
  /** Auswahl einer zitierten Quelle (Klick auf Quell-Chip). */
  onSelectCitation: (sourceId: string) => void;
}

export function NarrativePanel({ card, activeSegmentIndices, onSelectCitation }: NarrativePanelProps) {
  const activeSet = new Set(activeSegmentIndices);
  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <h3 className="text-caption font-semibold uppercase tracking-wide text-fg-secondary">
          Erzählt — rekonstruiert
        </h3>
        {card.isHypothesis ? (
          <span className="rounded-full border border-note-caveat/50 bg-note-caveat/10 px-2 py-0.5 text-caption text-note-caveat">
            Hypothese
          </span>
        ) : null}
        <span className="text-caption text-fg-muted">{CONFIDENCE_LABEL[card.confidence]}</span>
      </div>

      <p className="text-body leading-relaxed text-fg-primary">
        {card.narrativeSegments.map((segment, index) => {
          if (segment.citation === null) {
            return <span key={`text-${index}`}>{segment.text}</span>;
          }
          const active = activeSet.has(index);
          const sourceId = segment.citation;
          return (
            <button
              key={`cite-${index}`}
              type="button"
              onClick={() => onSelectCitation(sourceId)}
              aria-label={`Quelle ${sourceId} auf der Zeitachse hervorheben`}
              aria-pressed={active}
              data-citation={sourceId}
              className={cx(
                "mx-0.5 rounded px-1 align-baseline font-mono text-caption",
                "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-focus-ring",
                active ? "bg-focus-ring/20 text-fg-primary ring-1 ring-focus-ring" : "text-fg-secondary underline decoration-dotted",
              )}
            >
              {segment.text}
            </button>
          );
        })}
      </p>

      {card.flagged.length > 0 ? (
        <div
          role="note"
          aria-label="Nicht belegte Inhalte"
          className="flex flex-col gap-1 rounded-lg border border-note-caveat/50 bg-note-caveat/10 p-3"
        >
          <span className="text-caption font-semibold uppercase tracking-wide text-note-caveat">
            Nicht belegt
          </span>
          <span className="text-caption text-fg-secondary">
            Folgende Inhalte sind durch keine Quelle gedeckt und nur als Hypothese zu lesen:{" "}
            {card.flagged.join(", ")}
          </span>
        </div>
      ) : null}
    </div>
  );
}
