// ============================================================
//  FOREMAN Frontend — components/event-chains/timeline-column.tsx
//  Zweck: Die linke, vertikale Zeitachsen-Spalte (Studie §4D): die BELEGTEN
//         Ereignis-Knoten in zeitlicher Folge. Dezente Verbindungslinie = ZEITLICHE
//         Folge, NICHT behauptete Kausalität (Kausalität ist F vorbehalten).
//         Roving-Tastatur-Navigation (Pfeile/Home/End). Klick koppelt an die
//         Erzählung. Legende der formcodierten Symbole.
//  Architektur-Einordnung: Timeline-Molekül (Schicht 2).
// ============================================================
"use client";

import { useEffect, useRef, useState } from "react";
import { SYMBOL_LABEL } from "@/lib/event-chains/symbols";
import { nextRovingIndex } from "@/lib/event-chains/timeline";
import type { ChainNode, ChainSymbolKind } from "@/lib/event-chains/types";
import { ChainSymbol } from "./chain-symbol";
import { EventNode } from "./event-node";

export interface TimelineColumnProps {
  nodes: ChainNode[];
  selectedSourceId: string | null;
  onSelect: (sourceId: string) => void;
}

function distinctKinds(nodes: ChainNode[]): ChainSymbolKind[] {
  const seen: ChainSymbolKind[] = [];
  for (const node of nodes) {
    if (!seen.includes(node.kind)) {
      seen.push(node.kind);
    }
  }
  return seen;
}

export function TimelineColumn({ nodes, selectedSourceId, onSelect }: TimelineColumnProps) {
  const [activeIndex, setActiveIndex] = useState(0);
  const refs = useRef<(HTMLButtonElement | null)[]>([]);

  // Roving-Index bei Kartenwechsel klemmen: werden die Knoten kürzer, darf der
  // Index nicht aus dem Bereich fallen (sonst hätte kein Knoten tabIndex 0 — die
  // Tastatur-Navigation bräche).
  useEffect(() => {
    if (nodes.length === 0) {
      setActiveIndex(0);
      return;
    }
    setActiveIndex((current) => Math.min(current, nodes.length - 1));
  }, [nodes.length]);

  // Auswahl koppeln: wird eine Quelle (Quell-Chip) gewählt, folgt der Roving-Fokus.
  useEffect(() => {
    if (selectedSourceId === null) {
      return;
    }
    const index = nodes.findIndex((node) => node.sourceId === selectedSourceId);
    if (index >= 0) {
      setActiveIndex(index);
    }
  }, [selectedSourceId, nodes]);

  function handleKeyDown(event: React.KeyboardEvent<HTMLOListElement>) {
    const next = nextRovingIndex(activeIndex, event.key, nodes.length);
    if (next === activeIndex || next < 0) {
      return;
    }
    event.preventDefault();
    setActiveIndex(next);
    refs.current[next]?.focus();
  }

  if (nodes.length === 0) {
    return (
      <div role="status" className="rounded-lg border border-line-subtle bg-surface-raised p-4 text-body text-fg-muted">
        Ketten-Momentaufnahme nicht verfügbar (vor der Snapshot-Erweiterung erstellt).
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <h3 className="text-caption font-semibold uppercase tracking-wide text-fg-secondary">
          Belegt — Ereignisse
        </h3>
        <p className="text-caption text-fg-muted">
          Verbindung = zeitliche Folge, keine Ursache-Wirkung.
        </p>
      </div>
      {/* Zeitliche Folge-Linie: ruhige Schiene links hinter den Knoten. */}
      <ol
        aria-label="Zeitachse der belegten Ereignisse"
        onKeyDown={handleKeyDown}
        className="relative flex flex-col gap-3 before:absolute before:left-[10px] before:top-2 before:bottom-2 before:w-px before:bg-line-subtle before:content-['']"
      >
        {nodes.map((node, index) => (
          <li key={node.sourceId} className="relative pl-0">
            <EventNode
              ref={(element) => {
                refs.current[index] = element;
              }}
              node={node}
              active={node.sourceId === selectedSourceId}
              tabIndex={index === activeIndex ? 0 : -1}
              onSelect={(sourceId) => {
                setActiveIndex(index);
                onSelect(sourceId);
              }}
            />
          </li>
        ))}
      </ol>
      <ul className="flex flex-wrap gap-x-4 gap-y-1" aria-label="Legende der Symbole">
        {distinctKinds(nodes).map((kind) => (
          <li key={kind} className="flex items-center gap-1.5 text-caption text-fg-muted">
            <ChainSymbol kind={kind} className="h-4 w-4 text-fg-secondary" />
            {SYMBOL_LABEL[kind]}
          </li>
        ))}
      </ul>
    </div>
  );
}
