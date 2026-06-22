// ============================================================
//  FOREMAN Frontend — lib/platform/topology-view-model.test.ts
//  Zweck: Sichert die EHRLICHE Topologie-Ableitung: reale Knoten korrekt gruppiert,
//         simulation als intern, fehlende Aktivität → 'unbekannt' (nie 'verbunden'),
//         [VISION]-Knoten strikt getrennt + nie verbunden, KEIN erfundener Knoten,
//         und ein fälschlich vision-markierter realer Knoten landet nie als real.
// ============================================================
import { describe, expect, it } from "vitest";
import {
  makeNode,
  makeSubstrateNode,
  makeMcpNode,
  makeTopologyView,
  makeVisionNode,
} from "./testing/fixtures";
import { assembleTopology, nodeDetailChips, realNodeCount } from "./topology-view-model";

describe("assembleTopology", () => {
  it("gruppiert reale Knoten nach Kategorie und trennt Vision", () => {
    const model = assembleTopology(makeTopologyView());
    expect(model.inputs).toHaveLength(2);
    expect(model.substrate).toHaveLength(1);
    expect(model.mcp).toHaveLength(1);
    expect(model.vision).toHaveLength(3);
    expect(realNodeCount(model)).toBe(4);
    expect(model.generatedAtIso).toBe("2026-06-22T17:30:00+00:00");
  });

  it("markiert die Simulationsquelle als intern", () => {
    const model = assembleTopology(
      makeTopologyView({ nodes: [makeNode({ id: "source:simulation", internal: true })] }),
    );
    expect(model.inputs[0]?.internal).toBe(true);
  });

  it("eine Quelle ohne jüngste Aktivität ist 'unbekannt' — nie 'verbunden'", () => {
    const model = assembleTopology(
      makeTopologyView({
        nodes: [makeNode({ status: "unbekannt", last_activity: null })],
        vision: [],
      }),
    );
    expect(model.inputs[0]?.status).toBe("unbekannt");
    expect(model.inputs[0]?.status).not.toBe("verbunden");
  });

  it("alle Vision-Knoten sind als vision markiert und nicht verbunden", () => {
    const model = assembleTopology(makeTopologyView());
    for (const node of model.vision) {
      expect(node.isVision).toBe(true);
      expect(node.status).not.toBe("verbunden");
      expect(node.direction).toBe("keine");
    }
  });

  it("erfindet keinen Knoten außerhalb von nodes/vision", () => {
    const view = makeTopologyView();
    const model = assembleTopology(view);
    const total =
      model.inputs.length + model.substrate.length + model.mcp.length + model.vision.length;
    expect(total).toBe(view.nodes.length + view.vision.length);
  });

  it("ein fälschlich vision-markierter Knoten in nodes landet NIE als reale Verbindung", () => {
    const model = assembleTopology(
      makeTopologyView({
        nodes: [makeNode({ id: "source:opcua", vision: true, status: "verbunden" })],
        vision: [],
      }),
    );
    expect(model.inputs).toHaveLength(0);
    expect(model.vision).toHaveLength(1);
    expect(model.vision[0]?.isVision).toBe(true);
  });

  it("leere Topologie → alle Kategorien leer (kein Platzhalter-Knoten)", () => {
    const model = assembleTopology(makeTopologyView({ nodes: [], vision: [] }));
    expect(realNodeCount(model)).toBe(0);
    expect(model.vision).toHaveLength(0);
  });

  it("der MCP-Knoten ohne Audit-Details (Schichtleiter-Sicht) bleibt ehrlich inaktiv/unbekannt", () => {
    const model = assembleTopology(
      makeTopologyView({
        nodes: [makeMcpNode({ status: "unbekannt", detail: { configured: true } })],
        vision: [],
      }),
    );
    expect(model.mcp[0]?.status).toBe("unbekannt");
    expect(model.mcp[0]?.detail).toEqual({ configured: true });
  });

  it("der Substrat-Knoten trägt die externe Bezeichnung 'Gedächtnis-Substrat'", () => {
    const model = assembleTopology(
      makeTopologyView({ nodes: [makeSubstrateNode()], vision: [makeVisionNode()] }),
    );
    expect(model.substrate[0]?.label).toBe("Gedächtnis-Substrat");
    expect(model.substrate[0]?.direction).toBe("beides");
  });
});

describe("nodeDetailChips", () => {
  it("übersetzt bekannte Detail-Felder in Hallensprache", () => {
    const [mcp] = assembleTopology(
      makeTopologyView({ nodes: [makeMcpNode({ detail: { configured: true, consumer_count: 1 } })], vision: [] }),
    ).mcp;
    expect(mcp ? nodeDetailChips(mcp) : []).toContain("1 Konsument");

    const [sub] = assembleTopology(
      makeTopologyView({ nodes: [makeSubstrateNode({ detail: { configured: true, latency_ms: 42 } })], vision: [] }),
    ).substrate;
    expect(sub ? nodeDetailChips(sub) : []).toContain("Antwortzeit 42 ms");
  });

  it("markiert nicht konfigurierte / fehlerhafte Knoten ehrlich", () => {
    const [mcp] = assembleTopology(
      makeTopologyView({ nodes: [makeMcpNode({ detail: { configured: false } })], vision: [] }),
    ).mcp;
    expect(mcp ? nodeDetailChips(mcp) : []).toContain("nicht konfiguriert");

    const [sub] = assembleTopology(
      makeTopologyView({
        nodes: [makeSubstrateNode({ status: "gestört", detail: { configured: true, probe_error: true } })],
        vision: [],
      }),
    ).substrate;
    expect(sub ? nodeDetailChips(sub) : []).toContain("Prüfung fehlgeschlagen");
  });

  it("markiert die interne Simulationsquelle und lässt Unbekanntes weg", () => {
    const [input] = assembleTopology(
      makeTopologyView({
        nodes: [makeNode({ internal: true, detail: { protocol: "simulation", foo: "bar" } })],
        vision: [],
      }),
    ).inputs;
    const chips = input ? nodeDetailChips(input) : [];
    expect(chips).toContain("interne Quelle");
    expect(chips.join(" ")).not.toContain("bar");
  });
});
