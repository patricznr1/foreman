// ============================================================
//  FOREMAN Frontend — lib/event-chains/symbols.ts
//  Zweck: Abbildung Kettenereignis-Typ → formcodiertes Symbol (konsistent mit
//         Sektion B) + Hallensprache-Labels. Mehrkanalig (§5.8): die Form (nicht
//         Farbe) trägt die Bedeutung. Paraphrase-Disziplin (§21-D): „Drift" heißt
//         im Bedien-Wording „Abweichung" — kein interner Verfahrensname.
//  Architektur-Einordnung: reine Abbildung (Schicht 2).
// ============================================================
import type { ChainEventType } from "@/lib/api/contracts";
import type { ChainSymbolKind } from "./types";

/** Ereignis-Typ → Symbolklasse. Alarm = Dreieck, Drift abgesetzt, Notiz = Stift,
 *  Wartung = Schraube, Anker hervorgehoben. */
const EVENT_SYMBOL: Record<ChainEventType, ChainSymbolKind> = {
  anchor_alarm: "anchor",
  drift_alarm: "drift",
  prior_alarm: "alarm",
  worker_note: "note",
  maintenance: "maintenance",
};

export function symbolFor(eventType: ChainEventType): ChainSymbolKind {
  return EVENT_SYMBOL[eventType] ?? "alarm";
}

/** Label je Ereignis-Typ (Bedien-Wording). „drift_alarm" → „Abweichungs-Alarm". */
const EVENT_TYPE_LABEL: Record<ChainEventType, string> = {
  anchor_alarm: "Anker-Alarm",
  drift_alarm: "Abweichungs-Alarm",
  prior_alarm: "Alarm",
  worker_note: "Werkernotiz",
  maintenance: "Wartung",
};

export function eventTypeLabel(eventType: ChainEventType): string {
  return EVENT_TYPE_LABEL[eventType] ?? "Ereignis";
}

/** Label je Symbolklasse (für die Legende der Zeitachse). */
export const SYMBOL_LABEL: Record<ChainSymbolKind, string> = {
  anchor: "Anker",
  drift: "Abweichung",
  alarm: "Alarm",
  note: "Notiz",
  maintenance: "Wartung",
};
