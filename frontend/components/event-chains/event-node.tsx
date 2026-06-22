// ============================================================
//  FOREMAN Frontend — components/event-chains/event-node.tsx
//  Zweck: Ein Knoten der BELEGTEN Zeitachse (Studie §4D). Formcodiertes Symbol +
//         Zeit + Label + Kurztext. `trusted=false` (Werkernotiz-Freitext) wird
//         SICHTBAR als unsicherer markiert (gestrichelter Rand + „unsicher"-Hinweis,
//         note/caveat-Farbe — KEINE Alarm-Severity). Der Anker ist hervorgehoben.
//         Klick koppelt an die Erzählung (gekoppeltes Hervorheben).
//  Architektur-Einordnung: Timeline-Atom (Schicht 2).
// ============================================================
"use client";

import { forwardRef } from "react";
import type { ChainNode } from "@/lib/event-chains/types";
import { cx } from "@/lib/ui/cx";
import { ChainSymbol } from "./chain-symbol";

function formatMoment(iso: string): string {
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

export interface EventNodeProps {
  node: ChainNode;
  active: boolean;
  tabIndex: number;
  onSelect: (sourceId: string) => void;
}

export const EventNode = forwardRef<HTMLButtonElement, EventNodeProps>(function EventNode(
  { node, active, tabIndex, onSelect },
  ref,
) {
  const moment = formatMoment(node.occurredAtIso);
  // Entsättigte Symbol-/Textfarbe: Anker betont, untrusted im ruhigen Vorbehalt-Ton,
  // sonst sekundär. NIE Severity-Farbe (die lebt am Original-Alarm in C).
  const tone = node.isAnchor
    ? "text-fg-primary"
    : node.trusted
      ? "text-fg-secondary"
      : "text-note-caveat";
  const accessibleName = [
    node.isAnchor ? "Anker" : null,
    node.label,
    moment,
    node.trusted ? null : "unsicher belegt",
  ]
    .filter(Boolean)
    .join(", ");

  return (
    <button
      ref={ref}
      type="button"
      tabIndex={tabIndex}
      aria-pressed={active}
      aria-label={accessibleName}
      onClick={() => onSelect(node.sourceId)}
      data-source-id={node.sourceId}
      data-anchor={node.isAnchor ? "true" : undefined}
      data-trusted={node.trusted ? "true" : "false"}
      className={cx(
        "flex w-full items-start gap-3 rounded-lg border p-3 text-left",
        "min-h-[var(--touch-min)]",
        "transition-colors duration-[var(--motion-base)] motion-reduce:transition-none",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring",
        node.isAnchor ? "border-line-strong bg-surface-overlay" : "border-line-subtle bg-surface-raised",
        !node.trusted && "border-dashed",
        active && "ring-2 ring-focus-ring",
      )}
    >
      <ChainSymbol kind={node.kind} className={tone} />
      <span className="flex min-w-0 flex-col gap-1">
        <span className="flex flex-wrap items-baseline gap-x-2">
          <span className={cx("text-body", node.isAnchor ? "font-semibold text-fg-primary" : "text-fg-primary")}>
            {node.isAnchor ? `Anker · ${node.label}` : node.label}
          </span>
          <span className="text-caption text-fg-muted tabular-nums">{moment}</span>
          {node.trusted ? null : (
            <span className="text-caption text-note-caveat">unsicher</span>
          )}
        </span>
        <span className="text-caption text-fg-secondary">{node.summary}</span>
      </span>
    </button>
  );
});
