// ============================================================
//  FOREMAN Frontend — components/memory/source-blocks.test.tsx
//  Zweck: Die Blöcke unter der Rangliste — Kopfzeilen, Aufklappzustand,
//         Bedingungen für ihr Erscheinen.
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ArchiveHitView, SourceType } from "@/lib/memory/types";
import { SourceBlocks } from "./source-blocks";

function treffer(
  source: SourceType,
  id: number,
  rank: number,
  foundBy: SourceType[] = [source],
): ArchiveHitView {
  return {
    source,
    id,
    machineId: 12,
    timestamp: "2026-08-20T09:00:00Z",
    excerpt: `Auszug ${id}`,
    detail: {},
    rank,
    foundBy,
  };
}

describe("SourceBlocks", () => {
  it("zeigt je Quelle eine Kopfzeile mit Trefferzahl", () => {
    render(
      <SourceBlocks
        hits={[treffer("note", 1, 0), treffer("note", 2, 1), treffer("maintenance", 3, 2)]}
        largeCards={false}
      />,
    );

    expect(screen.getByText("2 Treffer")).toBeInTheDocument();
    expect(screen.getByText("1 Treffer")).toBeInTheDocument();
  });

  it("ist zugeklappt, solange niemand aufklappt", () => {
    // Die Treffer stehen oben schon vollstaendig. Aufgeklappt zeigte die Seite
    // jeden Vorgang zweimal — dreissig Karten fuer fuenfzehn Treffer.
    const { container } = render(
      <SourceBlocks hits={[treffer("note", 1, 0), treffer("alarm", 2, 1)]} largeCards={false} />,
    );

    const bloecke = container.querySelectorAll("details");
    expect(bloecke).toHaveLength(2);
    for (const block of bloecke) {
      expect(block.open).toBe(false);
    }
  });

  it("nennt in der Kopfzeile, wie viele Treffer das Gedaechtnis bestaetigt hat", () => {
    render(
      <SourceBlocks
        hits={[
          treffer("note", 1, 0, ["note", "memory"]),
          treffer("note", 2, 1, ["note", "memory"]),
          treffer("maintenance", 3, 2),
        ]}
        largeCards={false}
      />,
    );

    expect(screen.getByText("2 davon auch im Gedächtnis")).toBeInTheDocument();
  });

  it("schweigt ueber Bestaetigungen, wenn es keine gibt", () => {
    // AUFBAU-KONTROLLE: „0 davon auch im Gedaechtnis" ist keine Auskunft,
    // sondern eine Zeile, die man nach zwei Suchen ueberliest.
    render(
      <SourceBlocks hits={[treffer("note", 1, 0), treffer("alarm", 2, 1)]} largeCards={false} />,
    );

    expect(screen.queryByText(/davon auch im Gedächtnis/)).not.toBeInTheDocument();
  });

  it("bleibt bei einer einzigen Quelle ganz weg", () => {
    // Eine Aufteilung in EINEN Block sagt nichts, was die Liste darueber nicht
    // schon sagt — sie taeuschte eine Gliederung vor, die keine ist.
    const { container } = render(
      <SourceBlocks hits={[treffer("note", 1, 0), treffer("note", 2, 1)]} largeCards={false} />,
    );

    expect(container).toBeEmptyDOMElement();
  });

  it("bleibt ohne Treffer ganz weg", () => {
    const { container } = render(<SourceBlocks hits={[]} largeCards={false} />);

    expect(container).toBeEmptyDOMElement();
  });

  it("sagt dazu, dass es dieselben Treffer sind", () => {
    // Ohne diesen Satz liest ein Werker die Bloecke als ZWEITE Suche und
    // wundert sich, warum dieselben Vorgaenge zweimal dastehen.
    render(
      <SourceBlocks hits={[treffer("note", 1, 0), treffer("alarm", 2, 1)]} largeCards={false} />,
    );

    expect(screen.getByText(/Dieselben Treffer wie oben/)).toBeInTheDocument();
  });
});
