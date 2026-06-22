// ============================================================
//  FOREMAN Frontend — lib/event-chains/types.ts
//  Zweck: View-Model-Typen der Sektion D (Ereignisketten). Trennen die
//         BELEGTEN Kettenereignisse (Knoten) von der ERZÄHLTEN, rekonstruierten
//         Erzählung (Segmente) — der Kern von §4D. Transport-agnostisch, ohne UI.
//  Architektur-Einordnung: View-State-Typen (Schicht 2).
// ============================================================
import type { Confidence } from "@/lib/api/contracts";

/** Formcodierte Symbolklasse eines Kettenknotens (konsistent mit Sektion B). */
export type ChainSymbolKind = "anchor" | "drift" | "alarm" | "note" | "maintenance";

/** Verbale Konfidenz-Stufe der Erzählung — NIE als Prozent (Studie §4D). */
export type ConfidenceLevel = "gering" | "mittel" | "hoch";

/**
 * Ein Knoten der Zeitachse (BELEGT). `trusted=false` markiert untrusted
 * Werkernotiz-Freitext (sichtbar als unsicherer). `isAnchor` hebt den Anker hervor.
 */
export interface ChainNode {
  sourceId: string;
  kind: ChainSymbolKind;
  occurredAtIso: string;
  occurredAtMs: number;
  /** Kurz-Label in Hallensprache (Symboltyp). */
  label: string;
  /** Backend-Zusammenfassung des Ereignisses (PII-frei / NER-maskiert). */
  summary: string;
  trusted: boolean;
  isAnchor: boolean;
}

/**
 * Ein Segment der ERZÄHLUNG. `citation` ist die referenzierte `source_id`
 * (Quell-Chip → koppelt an einen Knoten) oder null für reinen Fließtext.
 */
export interface NarrativeSegment {
  text: string;
  citation: string | null;
}

/** Eine ehrliche Schwester-Referenz fürs UI. `navigable` nur, wenn eine reale
 *  Ziel-Erklärung existiert (klickbarer Sprung zur Schwesterkette). */
export interface SiblingModel {
  recallRef: string | null;
  machineId: number | null;
  machineClass: string | null;
  explanationId: number | null;
  basis: string;
  excerpt: string;
  navigable: boolean;
}

/**
 * Das zusammengesetzte Karten-Modell einer Ereigniskette. Hält BELEGT (nodes,
 * window) und ERZÄHLT (narrativeSegments, isHypothesis, confidence, flagged)
 * hart getrennt; `chainAvailable=false` bei Altdatensätzen ohne Snapshot.
 */
export interface ChainCardModel {
  explanationId: number;
  anchorAlarmId: number;
  machineId: number | null;
  chainAvailable: boolean;
  nodes: ChainNode[];
  window: { startIso: string; endIso: string } | null;
  narrativeSegments: NarrativeSegment[];
  isHypothesis: boolean;
  confidence: ConfidenceLevel;
  /** Geflaggte, unbelegte Inhalte (sichtbar machen — Ehrlichkeit). */
  flagged: string[];
  recallUsed: boolean;
  grounded: boolean | null;
  /** Stand der Momentaufnahme (ISO) — für den ProvenanceStamp. */
  stampedAt: string;
  siblings: SiblingModel[];
}

/** Verdichtetes Listen-/Aggregat-Modell (Manager: ein Satz + Kennzahl). */
export interface ChainSummaryModel {
  explanationId: number;
  anchorAlarmId: number;
  machineId: number | null;
  confidence: ConfidenceLevel;
  isHypothesis: boolean;
  createdAtIso: string;
  /** Ein-Satz-Zusammenfassung in Hallensprache. */
  sentence: string;
}

export type { Confidence };
