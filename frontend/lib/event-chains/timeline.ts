// ============================================================
//  FOREMAN Frontend — lib/event-chains/timeline.ts
//  Zweck: Baut die BELEGTE Zeitachse aus der Kette (Knoten, zeitlich geordnet,
//         Anker hervorgehoben) und die reine Kopplungs-Funktion fürs gekoppelte
//         Hervorheben (Knoten ↔ Erzählstelle, Studie §4D). Alles reine Logik,
//         ohne UI/Netz testbar.
//  Architektur-Einordnung: View-State-Logik (Schicht 2).
// ============================================================
import type { ChainEvent, EventChain } from "@/lib/api/contracts";
import { eventTypeLabel, symbolFor } from "./symbols";
import type { ChainNode, NarrativeSegment } from "./types";

function toNode(event: ChainEvent): ChainNode {
  const ms = Date.parse(event.occurred_at);
  return {
    sourceId: event.source_id,
    kind: symbolFor(event.event_type),
    occurredAtIso: event.occurred_at,
    occurredAtMs: Number.isNaN(ms) ? 0 : ms,
    label: eventTypeLabel(event.event_type),
    summary: event.summary,
    trusted: event.trusted,
    isAnchor: event.event_type === "anchor_alarm",
  };
}

/**
 * Knoten der Zeitachse, zeitlich geordnet (stabiler Tiebreak über die source_id —
 * deterministisch, spiegelt die Backend-Ordnung). Reine Funktion.
 */
export function buildNodes(chain: EventChain): ChainNode[] {
  return chain.events
    .map(toNode)
    .sort((a, b) => a.occurredAtMs - b.occurredAtMs || a.sourceId.localeCompare(b.sourceId));
}

/** Das (eine) Anker-Knoten, falls vorhanden. */
export function anchorNode(nodes: ChainNode[]): ChainNode | null {
  return nodes.find((node) => node.isAnchor) ?? null;
}

export interface CoupledHighlight {
  /** Der hervorgehobene Knoten (oder null). */
  nodeSourceId: string | null;
  /** Indizes der Erzähl-Segmente, die genau diese Quelle zitieren. */
  segmentIndices: number[];
}

/**
 * Gekoppeltes Hervorheben (Studie §4D): eine gewählte `source_id` markiert ihren
 * Knoten UND alle Erzähl-Segmente, die sie zitieren — symmetrisch (Klick auf
 * Knoten ODER auf Quell-Chip setzt dieselbe Auswahl). `null` = nichts markiert.
 * Reine Funktion (kein DOM, kein Scroll-Seiteneffekt).
 */
export function coupledHighlight(
  selectedSourceId: string | null,
  segments: NarrativeSegment[],
): CoupledHighlight {
  if (selectedSourceId === null) {
    return { nodeSourceId: null, segmentIndices: [] };
  }
  const segmentIndices: number[] = [];
  segments.forEach((segment, index) => {
    if (segment.citation === selectedSourceId) {
      segmentIndices.push(index);
    }
  });
  return { nodeSourceId: selectedSourceId, segmentIndices };
}

/**
 * Reiner Roving-Tabindex-Schritt für die Tastatur-Navigation der Zeitachse: aus
 * aktuellem Index + Taste der nächste fokussierte Index (geklemmt). Pfeil-hoch/
 * links zurück, runter/rechts vor, Home/End an die Ränder; sonst unverändert.
 */
export function nextRovingIndex(current: number, key: string, count: number): number {
  if (count <= 0) {
    return -1;
  }
  switch (key) {
    case "ArrowDown":
    case "ArrowRight":
      return Math.min(current + 1, count - 1);
    case "ArrowUp":
    case "ArrowLeft":
      return Math.max(current - 1, 0);
    case "Home":
      return 0;
    case "End":
      return count - 1;
    default:
      return current;
  }
}
