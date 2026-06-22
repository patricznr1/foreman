// ============================================================
//  FOREMAN Frontend — lib/event-chains/narrative.test.ts
//  Zweck: Zerlegung der Erzählung an [source_id]-Zitaten (für Quell-Chips).
// ============================================================
import { describe, expect, it } from "vitest";
import { citedSourceIds, parseNarrative } from "./narrative";

describe("parseNarrative", () => {
  it("trennt Fließtext und Zitat-Segmente", () => {
    expect(parseNarrative("A [alarm:1] B")).toEqual([
      { text: "A ", citation: null },
      { text: "[alarm:1]", citation: "alarm:1" },
      { text: " B", citation: null },
    ]);
  });

  it("zitatfreier Text → ein einziges Segment", () => {
    expect(parseNarrative("nur Text")).toEqual([{ text: "nur Text", citation: null }]);
  });

  it("citedSourceIds: eindeutig und in Reihenfolge", () => {
    expect(citedSourceIds("[alarm:1] x [note:2] y [alarm:1]")).toEqual(["alarm:1", "note:2"]);
  });
});
