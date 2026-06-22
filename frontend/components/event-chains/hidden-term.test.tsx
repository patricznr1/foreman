// ============================================================
//  FOREMAN Frontend — components/event-chains/hidden-term.test.tsx
//  Zweck: Hidden-Term-Gate der Sektion D (Paraphrase-Disziplin §21-D): KEIN interner
//         Verfahrens-/Infrastruktur-Begriff und KEIN „Drift" im sichtbaren
//         Bedien-Wording — „Abweichung" statt „Drift", „Schwesterketten"/„ähnliche
//         Fälle" statt „Recall". Gescannt wird das von UNS gerenderte Chrome
//         (Fixture-Inhalte sind bewusst neutral, da Backend-Daten kein Wording sind).
// ============================================================
import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { makeDetail } from "@/lib/event-chains/testing/fixtures";
import type { ChainCardModel } from "@/lib/event-chains/types";
import { assembleChainCard } from "@/lib/event-chains/view-model";
import { TimelineNarrative } from "./timeline-narrative";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

// Interne Begriffe aus dem Innenleben (F6/F-SEM/Gedächtnis) + „Drift" im Bedien-Wording.
const FORBIDDEN = [
  "drift",
  "embedding",
  "vektor",
  "vector",
  "cosine",
  "kosinus",
  "hnsw",
  "pgvector",
  "bge-m3",
  "ollama",
  "presidio",
  "substrat",
  "recall",
  "grounding",
  "spotlighting",
  "gateway",
  "reasoner",
  "prompt",
];

/** Neutrale Karte: Backend-Datenfelder ohne Fachvokabular, damit der Scan das
 *  WORDING prüft, nicht durchgereichte Datenwerte (z. B. Alarm-Codes). */
function neutralCard(): ChainCardModel {
  const detail = makeDetail({
    narrative: "Vor dem Anker [alarm:1] meldete die Notiz [note:3] einen Hinweis.",
    chain: {
      anchor_alarm_id: 1,
      machine_id: 7,
      window: { start: "2026-06-07T12:00:00+00:00", end: "2026-06-14T12:00:00+00:00" },
      events: [
        {
          source_id: "note:3",
          event_type: "worker_note",
          occurred_at: "2026-06-14T10:00:00+00:00",
          machine_id: 7,
          summary: "Lager läuft heiß",
          trusted: false,
        },
        {
          source_id: "alarm:1",
          event_type: "drift_alarm",
          occurred_at: "2026-06-14T12:00:00+00:00",
          machine_id: 7,
          summary: "Alarm (Kategorie Prozess)",
          trusted: true,
        },
      ],
    },
    siblings: [
      {
        recall_ref: "mem-1",
        machine_id: 9,
        machine_class: "cnc",
        explanation_id: 42,
        similarity_basis: "Ähnlich anhand: Maschinenklasse cnc",
        excerpt: "Frühere Lager-Überhitzung an der Schwestermaschine",
      },
    ],
  });
  const result = assembleChainCard(detail);
  if (!result.ok) {
    throw new Error("Fixture ungültig");
  }
  return result.card;
}

describe("Hidden-Term-Scan (Sektion D)", () => {
  it("kein interner Verfahrensbegriff und kein 'Drift' im sichtbaren Output", () => {
    render(<TimelineNarrative card={neutralCard()} canPin onOpenSibling={() => {}} />);
    const text = (document.body.textContent ?? "").toLowerCase();
    for (const term of FORBIDDEN) {
      expect(text.includes(term), `verbotener Begriff im sichtbaren UI: ${term}`).toBe(false);
    }
  });

  it("keine Scheingenauigkeit: kein Prozentzeichen im sichtbaren Output", () => {
    render(<TimelineNarrative card={neutralCard()} canPin={false} onOpenSibling={() => {}} />);
    expect(document.body.textContent ?? "").not.toMatch(/%/);
  });
});
