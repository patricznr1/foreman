// ============================================================
//  FOREMAN Frontend — lib/event-chains/testing/fixtures.ts
//  Zweck: Test-Fixtures der Sektion D (Ereignisketten) — gegen den realen
//         Backend-Vertrag geformt. Nur für Tests.
// ============================================================
import type {
  ChainEvent,
  EventChain,
  ReasonerExplanationDetailRead,
  ReasonerExplanationRead,
  SiblingReference,
} from "@/lib/api/contracts";

const ANCHOR_TIME = "2026-06-14T12:00:00+00:00";

export function makeEvent(over: Partial<ChainEvent> = {}): ChainEvent {
  return {
    source_id: "alarm:1",
    event_type: "anchor_alarm",
    occurred_at: ANCHOR_TIME,
    machine_id: 7,
    summary: "Alarm (Schwere warning, Kategorie process, Code DRIFT)",
    trusted: true,
    ...over,
  };
}

export function makeChain(over: Partial<EventChain> = {}): EventChain {
  return {
    anchor_alarm_id: 1,
    machine_id: 7,
    window: { start: "2026-06-07T12:00:00+00:00", end: ANCHOR_TIME },
    events: [
      makeEvent({ source_id: "note:3", event_type: "worker_note", occurred_at: "2026-06-14T10:00:00+00:00", summary: "Lager läuft heiß", trusted: false }),
      makeEvent(),
    ],
    ...over,
  };
}

export function makeSibling(over: Partial<SiblingReference> = {}): SiblingReference {
  return {
    recall_ref: "mem-1",
    machine_id: null,
    machine_class: null,
    explanation_id: null,
    similarity_basis: "Ähnlich anhand: Maschinenklasse cnc, Signatur DRIFT",
    excerpt: "Frühere Lager-Überhitzung an der Schwestermaschine",
    ...over,
  };
}

export function makeDetail(
  over: Partial<ReasonerExplanationDetailRead> = {},
): ReasonerExplanationDetailRead {
  return {
    id: 10,
    anchor_alarm_id: 1,
    machine_id: 7,
    reasoner: "event_chain",
    narrative: "Vor dem Anker [alarm:1] meldete die Notiz [note:3] einen Hinweis.",
    referenced_source_ids: ["alarm:1", "note:3"],
    flagged_unsupported: [],
    is_hypothesis: false,
    confidence: "high",
    grounded: true,
    recall_used: false,
    created_at: "2026-06-14T12:05:00+00:00",
    chain: makeChain(),
    siblings: [],
    ...over,
  };
}

export function makeRead(over: Partial<ReasonerExplanationRead> = {}): ReasonerExplanationRead {
  return {
    id: 10,
    anchor_alarm_id: 1,
    machine_id: 7,
    reasoner: "event_chain",
    narrative: "Vor dem Anker [alarm:1] meldete die Notiz [note:3] einen Hinweis.",
    referenced_source_ids: ["alarm:1", "note:3"],
    flagged_unsupported: [],
    is_hypothesis: false,
    confidence: "high",
    grounded: true,
    recall_used: false,
    created_at: "2026-06-14T12:05:00+00:00",
    ...over,
  };
}
