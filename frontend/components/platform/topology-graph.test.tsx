// ============================================================
//  FOREMAN Frontend — components/platform/topology-graph.test.tsx
//  Zweck: Sichert die EHRLICHE Topologie-Darstellung: reale Knoten gerendert,
//         [VISION]-Zone getrennt + als nicht-verbunden markiert, eine Quelle ohne
//         Aktivität als 'unbekannt' (nie 'verbunden'/grün), simulation als intern.
//         Geprüft an TopologyGraph (Lagebild) + TopologyNodeMark (Knoten-Karte).
// ============================================================
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import {
  makeNode,
  makeMcpNode,
  makeTopologyView,
  makeVisionNode,
} from "@/lib/platform/testing/fixtures";
import { assembleTopology } from "@/lib/platform/topology-view-model";
import { TopologyGraph } from "./topology-graph";
import { TopologyNodeMark } from "./topology-node-mark";

describe("TopologyGraph", () => {
  it("rendert das Lagebild mit FOREMAN im Zentrum und einer beschreibenden aria-Rolle", () => {
    render(<TopologyGraph model={assembleTopology(makeTopologyView())} />);
    const graph = screen.getByTestId("topology-graph");
    expect(graph).toHaveAttribute("role", "img");
    expect(within(graph).getByText("FOREMAN")).toBeInTheDocument();
  });

  it("zeigt die [VISION]-Zone getrennt und als nicht verbunden", () => {
    render(<TopologyGraph model={assembleTopology(makeTopologyView())} />);
    expect(screen.getByTestId("vision-zone")).toBeInTheDocument();
    expect(screen.getByText(/\[VISION\] — geplant, nicht verbunden/)).toBeInTheDocument();
  });

  it("blendet die [VISION]-Zone aus, wenn keine Vision-Knoten kommen", () => {
    render(
      <TopologyGraph model={assembleTopology(makeTopologyView({ vision: [] }))} />,
    );
    expect(screen.queryByTestId("vision-zone")).toBeNull();
  });
});

describe("TopologyNodeMark", () => {
  it("eine Quelle ohne Aktivität ist 'unbekannt' — der Status-Glyph ist nicht grün/ok", () => {
    const [node] = assembleTopology(
      makeTopologyView({ nodes: [makeNode({ status: "unbekannt", last_activity: null })], vision: [] }),
    ).inputs;
    render(<TopologyNodeMark node={node!} />);
    expect(screen.getByText("unbekannt")).toBeInTheDocument();
    expect(screen.getByText("keine Aktivität gemessen")).toBeInTheDocument();
    // Der Form-Kanal trägt 'question' — NICHT der 'filled'/ok-Glyph.
    const glyph = document.querySelector("svg[data-status]");
    expect(glyph).toHaveAttribute("data-status", "unbekannt");
  });

  it("markiert die interne Simulationsquelle als intern", () => {
    const [node] = assembleTopology(
      makeTopologyView({ nodes: [makeNode({ internal: true })], vision: [] }),
    ).inputs;
    render(<TopologyNodeMark node={node!} />);
    expect(screen.getByText("intern")).toBeInTheDocument();
  });

  it("markiert einen Vision-Knoten als nicht verbunden", () => {
    const [node] = assembleTopology(
      makeTopologyView({ nodes: [], vision: [makeVisionNode()] }),
    ).vision;
    render(<TopologyNodeMark node={node!} />);
    expect(screen.getByText(/\[VISION\] · nicht verbunden/)).toBeInTheDocument();
  });

  it("ein gestörter Knoten wird mit der ruhigen Warn-Form gezeigt (kein Alarm-Glyph)", () => {
    const [node] = assembleTopology(
      makeTopologyView({ nodes: [makeMcpNode({ status: "gestört" })], vision: [] }),
    ).mcp;
    render(<TopologyNodeMark node={node!} />);
    expect(screen.getByText("gestört")).toBeInTheDocument();
    const glyph = document.querySelector("svg[data-status]");
    expect(glyph).toHaveAttribute("data-status", "gestört");
  });
});
