// ============================================================
//  FOREMAN Frontend — lib/event-chains/timeline.test.ts
//  Zweck: Ketten-Mapping (Knoten, Ordnung, Anker, untrusted), gekoppeltes
//         Hervorheben als reine Funktion, Roving-Tastatur als reine Funktion.
// ============================================================
import { describe, expect, it } from "vitest";
import { parseNarrative } from "./narrative";
import { makeChain } from "./testing/fixtures";
import { anchorNode, buildNodes, coupledHighlight, nextRovingIndex } from "./timeline";

describe("buildNodes — Ketten-Mapping", () => {
  it("ordnet zeitlich (jüngste zuletzt) und hebt den Anker hervor", () => {
    const nodes = buildNodes(makeChain());
    expect(nodes.map((node) => node.sourceId)).toEqual(["note:3", "alarm:1"]);
    expect(anchorNode(nodes)?.sourceId).toBe("alarm:1");
  });

  it("markiert untrusted Werkernotizen", () => {
    const nodes = buildNodes(makeChain());
    expect(nodes.find((node) => node.sourceId === "note:3")?.trusted).toBe(false);
    expect(nodes.find((node) => node.sourceId === "alarm:1")?.trusted).toBe(true);
  });
});

describe("coupledHighlight — gekoppeltes Hervorheben (reine Funktion)", () => {
  const segments = parseNarrative("Vor [alarm:1] meldete [note:3] etwas, siehe [alarm:1].");

  it("null → nichts markiert", () => {
    expect(coupledHighlight(null, segments)).toEqual({ nodeSourceId: null, segmentIndices: [] });
  });

  it("eine Quelle markiert ihren Knoten und ALLE ihre Zitate (symmetrisch)", () => {
    const result = coupledHighlight("alarm:1", segments);
    expect(result.nodeSourceId).toBe("alarm:1");
    expect(result.segmentIndices.length).toBe(2);
  });
});

describe("nextRovingIndex — Tastatur (reine Funktion)", () => {
  it("bewegt, klemmt, Home/End, ignoriert Fremdtasten, leere Liste", () => {
    expect(nextRovingIndex(0, "ArrowDown", 3)).toBe(1);
    expect(nextRovingIndex(2, "ArrowDown", 3)).toBe(2);
    expect(nextRovingIndex(0, "ArrowUp", 3)).toBe(0);
    expect(nextRovingIndex(1, "Home", 3)).toBe(0);
    expect(nextRovingIndex(1, "End", 3)).toBe(2);
    expect(nextRovingIndex(1, "x", 3)).toBe(1);
    expect(nextRovingIndex(0, "ArrowDown", 0)).toBe(-1);
  });
});
