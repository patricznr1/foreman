// ============================================================
//  FOREMAN Frontend — lib/event-chains/view-model.test.ts
//  Zweck: Belegt/Erzählt-Split, Hypothese-/Konfidenz-/Flag-Durchreichung, graceful
//         ohne Snapshot, defensiver Fehler-Zustand, Manager-Verdichtung.
// ============================================================
import { describe, expect, it } from "vitest";
import { makeDetail, makeRead } from "./testing/fixtures";
import { ASSEMBLE_FAILURE_TEXT, assembleChainCard, toSummary } from "./view-model";

describe("assembleChainCard — Belegt/Erzählt-Split", () => {
  it("trennt belegte Knoten von der rekonstruierten Erzählung", () => {
    const result = assembleChainCard(makeDetail());
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.card.chainAvailable).toBe(true);
    expect(result.card.nodes.length).toBe(2);
    expect(result.card.narrativeSegments.some((segment) => segment.citation === "alarm:1")).toBe(true);
    expect(result.card.confidence).toBe("hoch");
    expect(result.card.isHypothesis).toBe(false);
  });

  it("reicht geflaggte Inhalte + Hypothese + verbale Konfidenz durch", () => {
    const result = assembleChainCard(
      makeDetail({ is_hypothesis: true, flagged_unsupported: ["evt:9999"], confidence: "low" }),
    );
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.card.isHypothesis).toBe(true);
    expect(result.card.flagged).toEqual(["evt:9999"]);
    expect(result.card.confidence).toBe("gering");
  });

  it("graceful ohne Snapshot: chain=null → keine erfundene Zeitachse, Erzählung bleibt", () => {
    const result = assembleChainCard(makeDetail({ chain: null }));
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.card.chainAvailable).toBe(false);
    expect(result.card.nodes).toEqual([]);
    expect(result.card.narrativeSegments.length).toBeGreaterThan(0);
  });

  it("ohne Erzähltext → defensiver Fehler-Zustand", () => {
    expect(assembleChainCard(makeDetail({ narrative: "" }))).toEqual({
      ok: false,
      reason: "empty-narrative",
    });
    expect(ASSEMBLE_FAILURE_TEXT["empty-narrative"]).toMatch(/Datenfehler/);
  });
});

describe("toSummary — Manager-Verdichtung (ein Satz, kein Prozent)", () => {
  it("verdichtet zu einem Satz mit Anker + Hypothese-Hinweis, ohne Prozent", () => {
    const summary = toSummary(makeRead({ is_hypothesis: true }));
    expect(summary.sentence).toContain("Alarm 1");
    expect(summary.sentence).toContain("Hypothese");
    expect(summary.sentence).not.toContain("%");
  });
});
