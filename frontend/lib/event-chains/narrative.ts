// ============================================================
//  FOREMAN Frontend — lib/event-chains/narrative.ts
//  Zweck: Zerlegt den ERZÄHLTEN Narrative-Text in Segmente an den [source_id]-
//         Zitaten. Die Zitate werden zu Quell-Chips, die an die Kettenknoten
//         koppeln (gekoppeltes Scrollen/Hervorheben, Studie §4D). Reine Funktion.
//  Architektur-Einordnung: reine Logik (Schicht 2), ohne UI testbar.
// ============================================================
import type { NarrativeSegment } from "./types";

// Zitat-Form: [<präfix>:<zahl>], identisch zur Backend-Zitat-Extraktion (alarm:12).
const CITATION_RE = /\[([a-z_]+:\d+)\]/g;

/**
 * Zerlegt die Erzählung in eine Folge aus Fließtext- und Zitat-Segmenten.
 * Ein Zitat-Segment trägt die referenzierte `source_id` in `citation` und den
 * sichtbaren Text (die Klammer-Notation bleibt als Marker erhalten). Reiner
 * Fließtext hat `citation=null`. Leerer/zitatfreier Text → ein einziges Segment.
 */
export function parseNarrative(narrative: string): NarrativeSegment[] {
  const segments: NarrativeSegment[] = [];
  let lastIndex = 0;
  // Frischer Lastindex pro Aufruf (globales Regex ist zustandsbehaftet).
  CITATION_RE.lastIndex = 0;
  let match = CITATION_RE.exec(narrative);
  while (match !== null) {
    const start = match.index;
    if (start > lastIndex) {
      segments.push({ text: narrative.slice(lastIndex, start), citation: null });
    }
    segments.push({ text: match[0], citation: match[1] ?? null });
    lastIndex = start + match[0].length;
    match = CITATION_RE.exec(narrative);
  }
  if (lastIndex < narrative.length) {
    segments.push({ text: narrative.slice(lastIndex), citation: null });
  }
  if (segments.length === 0) {
    segments.push({ text: narrative, citation: null });
  }
  return segments;
}

/** Die eindeutigen, in der Erzählung zitierten source_ids (in Reihenfolge). */
export function citedSourceIds(narrative: string): string[] {
  const seen: string[] = [];
  for (const segment of parseNarrative(narrative)) {
    if (segment.citation !== null && !seen.includes(segment.citation)) {
      seen.push(segment.citation);
    }
  }
  return seen;
}
