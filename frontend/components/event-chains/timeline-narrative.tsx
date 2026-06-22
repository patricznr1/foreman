// ============================================================
//  FOREMAN Frontend — components/event-chains/timeline-narrative.tsx
//  Zweck: Das Herzstück der Sektion D (Studie §4D): zweispaltig — LINKS die
//         vertikale Zeitachse (belegt), RECHTS die rekonstruierte Erzählung
//         (erzählt). GEKOPPELTES Hervorheben: Klick auf einen Knoten ↔ auf einen
//         Quell-Chip markiert beide Seiten. Anker-/Auslöser-Leiste oben (der Anker
//         IST ein Alarm — Querlink nach C). Schwesterketten + Pin als Querverweise.
//         Mobil gestapelt. KEINE Severity-Farbe in der Erzählung.
//  Architektur-Einordnung: Sektions-Herzstück (Schicht 2, client).
// ============================================================
"use client";

import Link from "next/link";
import { useState } from "react";
import { coupledHighlight } from "@/lib/event-chains/timeline";
import type { ChainCardModel } from "@/lib/event-chains/types";
import { alarmsHref, machineHref } from "@/lib/event-chains/url";
import { NarrativePanel } from "./narrative-panel";
import { PinChainAction } from "./pin-chain-action";
import { SiblingChains } from "./sibling-chains";
import { TimelineColumn } from "./timeline-column";

export interface TimelineNarrativeProps {
  card: ChainCardModel;
  /** Pin-Recht (Techniker/Schichtleiter) — der Aufrufer gated rollenbasiert. */
  canPin: boolean;
  /** Öffnet eine Schwesterkette (lädt die referenzierte Erklärung). */
  onOpenSibling: (explanationId: number) => void;
}

function formatRange(window: { startIso: string; endIso: string } | null): string | null {
  if (window === null) {
    return null;
  }
  const start = new Date(window.startIso);
  const end = new Date(window.endIso);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    return null;
  }
  const fmt = (date: Date) =>
    date.toLocaleString("de-DE", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
  return `${fmt(start)} – ${fmt(end)}`;
}

export function TimelineNarrative({ card, canPin, onOpenSibling }: TimelineNarrativeProps) {
  const [selected, setSelected] = useState<string | null>(null);
  const highlight = coupledHighlight(selected, card.narrativeSegments);

  function toggleSelect(sourceId: string) {
    setSelected((current) => (current === sourceId ? null : sourceId));
  }

  const range = formatRange(card.window);

  return (
    <article aria-label="Rekonstruierte Ereigniskette" className="flex flex-col gap-4">
      {/* Anker-/Auslöser-Leiste. Der Anker IST ein Alarm (Querlink nach C). */}
      <header className="flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-line-strong bg-surface-overlay p-3">
        <span className="text-body font-medium text-fg-primary">
          Anker · Alarm #{card.anchorAlarmId}
        </span>
        {card.machineId !== null ? (
          <Link
            href={machineHref(card.machineId)}
            className="text-caption text-fg-secondary underline decoration-dotted hover:text-fg-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
          >
            Maschine {card.machineId}
          </Link>
        ) : null}
        <Link
          href={alarmsHref()}
          className="text-caption text-fg-secondary underline decoration-dotted hover:text-fg-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
        >
          Zum Original-Alarm
        </Link>
        {range ? <span className="text-caption text-fg-muted">Fenster: {range}</span> : null}
      </header>

      {/* Zweispaltig auf Leitstand/Tablet, gestapelt auf Mobil. */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-2">
        <TimelineColumn
          nodes={card.nodes}
          selectedSourceId={highlight.nodeSourceId}
          onSelect={toggleSelect}
        />
        <NarrativePanel
          card={card}
          activeSegmentIndices={highlight.segmentIndices}
          onSelectCitation={toggleSelect}
        />
      </div>

      <SiblingChains siblings={card.siblings} onOpen={onOpenSibling} />

      {canPin ? <PinChainAction card={card} /> : null}
    </article>
  );
}
