// ============================================================
//  FOREMAN Frontend — components/platform/topology-graph.tsx
//  Zweck: Das ruhige, NICHT-animierte Lagebild der Systemtopologie (Studie §4I) als
//         maßgeschneidertes, token-getriebenes SVG (KEINE Graph-/Charting-Lib).
//         FOREMAN im Zentrum, die real abgeleiteten Knoten ringsum (Eingänge links,
//         Substrat + MCP-Grenze rechts); die [VISION]-Knoten in einer ABGESETZTEN,
//         gestrichelten Zone OHNE Verbindung zum Kern (nie als reale Verbindung).
//         Status mehrkanalig (Form-Glyph), Datenrichtung als Pfeil-FORM (nicht
//         Farbe); ein gestörter Konnektor ist klar, aber ruhig markiert (kein
//         Alarm-Drama, ISA-101). `role="img"` + aria-Label; die Substanz trägt die
//         zugängliche Knoten-Liste daneben. Statisch → reduced-motion neutral.
//  Architektur-Einordnung: bespoke SVG (Schicht 2, client).
// ============================================================
import { connectionStatusLabel, normalizeStatus } from "@/lib/platform/status";
import type { ConnectionStatus, TopologyModel, TopologyNodeModel } from "@/lib/platform/types";
import { statusShape } from "./topology-node-mark";

const VB_W = 760;
const NODE_W = 212;
const NODE_H = 54;
const V_GAP = 16;
const CORE_W = 150;
const CORE_H = 72;
const TITLE_SPACE = 40;
const LEFT_X = 24;
const RIGHT_X = VB_W - 24 - NODE_W;
const CORE_X = (VB_W - CORE_W) / 2;

/** Konnektor-Farbe: gestört ruhig markiert (state-check), sonst neutral. */
function connectorToken(status: ConnectionStatus): string {
  return status === "gestört" ? "state-check" : "line-strong";
}

function truncate(label: string, max = 24): string {
  return label.length > max ? `${label.slice(0, max - 1)}…` : label;
}

/** Kleine Pfeilspitze an (x,y), waagerecht. `dir`: Flussrichtung. */
function arrowHead(x: number, y: number, dir: "right" | "left", color: string) {
  const d = dir === "right" ? `M${x - 7} ${y - 5} L${x} ${y} L${x - 7} ${y + 5}`
                            : `M${x + 7} ${y - 5} L${x} ${y} L${x + 7} ${y + 5}`;
  return <path d={d} fill="none" stroke={color} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />;
}

interface PlacedNode {
  node: TopologyNodeModel;
  x: number;
  y: number;
  side: "left" | "right";
}

function NodeBox({ placed }: { placed: PlacedNode }) {
  const { node, x, y } = placed;
  const color = `var(--color-${statusName(node.status)})`;
  return (
    <g data-node-id={node.id}>
      <rect
        x={x}
        y={y}
        width={NODE_W}
        height={NODE_H}
        rx={8}
        fill="var(--color-surface-raised)"
        stroke="var(--color-line-subtle)"
        strokeWidth="1"
      />
      <svg x={x + 12} y={y + NODE_H / 2 - 9} width={18} height={18} viewBox="0 0 16 16">
        {statusShape(statusGlyphName(node.status), color)}
      </svg>
      <text
        x={x + 40}
        y={y + 22}
        fontSize="14"
        fontWeight="500"
        fill="var(--color-fg-primary)"
      >
        {truncate(node.label)}
      </text>
      <text x={x + 40} y={y + 40} fontSize="11.5" fill="var(--color-fg-muted)">
        {connectionStatusLabel(node.status, node.internal)}
        {" · "}
        {node.direction}
      </text>
    </g>
  );
}

/** Token-Name der Status-Farbe (für var(--color-*)). */
function statusName(status: ConnectionStatus): string {
  switch (status) {
    case "verbunden":
      return "state-ok";
    case "gestört":
      return "state-check";
    default:
      return "fg-muted";
  }
}

/** Form-Kanal des Status (Glyph). */
function statusGlyphName(status: ConnectionStatus): "filled" | "warning" | "hollow" | "question" {
  switch (status) {
    case "verbunden":
      return "filled";
    case "gestört":
      return "warning";
    case "inaktiv":
      return "hollow";
    default:
      return "question";
  }
}

function placeColumn(
  nodes: TopologyNodeModel[],
  x: number,
  side: "left" | "right",
  bandTop: number,
  bandH: number,
): PlacedNode[] {
  const colH = nodes.length * NODE_H + Math.max(0, nodes.length - 1) * V_GAP;
  const colTop = bandTop + (bandH - colH) / 2;
  return nodes.map((node, i) => ({ node, x, side, y: colTop + i * (NODE_H + V_GAP) }));
}

export interface TopologyGraphProps {
  model: TopologyModel;
}

export function TopologyGraph({ model }: TopologyGraphProps) {
  const left = model.inputs;
  const right = [...model.substrate, ...model.mcp];
  const rows = Math.max(left.length, right.length, 1);
  const bandH = rows * NODE_H + (rows - 1) * V_GAP;
  const bandTop = TITLE_SPACE;
  const coreCY = bandTop + bandH / 2;
  const coreY = coreCY - CORE_H / 2;

  const placedLeft = placeColumn(left, LEFT_X, "left", bandTop, bandH);
  const placedRight = placeColumn(right, RIGHT_X, "right", bandTop, bandH);

  const visionTop = bandTop + bandH + 32;
  // Höhe aus der tatsächlichen Zeilenzahl (3 Knoten/Zeile) — skaliert mit der
  // Knotenanzahl, statt bei vielen [VISION]-Knoten aus der Zone zu laufen.
  const visionRows = model.vision.length > 0 ? Math.ceil(model.vision.length / 3) : 0;
  const visionH = visionRows > 0 ? Math.max(92, 48 + (visionRows - 1) * 22 + 18) : 0;
  const svgH = visionTop + visionH + 16;

  return (
    <svg
      viewBox={`0 0 ${VB_W} ${svgH}`}
      role="img"
      aria-label={`Systemtopologie: FOREMAN im Zentrum, ${left.length} Eingangsquelle(n), ${right.length} verbundene Schnittstelle(n), ${model.vision.length} geplante (nicht verbundene) Drittsysteme.`}
      className="w-full"
      data-testid="topology-graph"
    >
      <text x={LEFT_X} y={24} fontSize="13" fontWeight="600" fill="var(--color-fg-secondary)">
        Eingänge
      </text>
      <text x={RIGHT_X} y={24} fontSize="13" fontWeight="600" fill="var(--color-fg-secondary)">
        Substrat &amp; Schnittstelle
      </text>

      {/* Konnektoren zuerst (hinter den Knoten). */}
      {placedLeft.map((p) => (
        <Connector key={`c-${p.node.id}`} placed={p} coreX={CORE_X} coreCY={coreCY} />
      ))}
      {placedRight.map((p) => (
        <Connector key={`c-${p.node.id}`} placed={p} coreX={CORE_X + CORE_W} coreCY={coreCY} />
      ))}

      {/* FOREMAN-Kern. */}
      <rect
        x={CORE_X}
        y={coreY}
        width={CORE_W}
        height={CORE_H}
        rx={10}
        fill="var(--color-surface-overlay)"
        stroke="var(--color-line-strong)"
        strokeWidth="1.5"
      />
      <text
        x={CORE_X + CORE_W / 2}
        y={coreCY + 1}
        textAnchor="middle"
        fontSize="17"
        fontWeight="700"
        fill="var(--color-fg-primary)"
      >
        FOREMAN
      </text>
      <text
        x={CORE_X + CORE_W / 2}
        y={coreCY + 20}
        textAnchor="middle"
        fontSize="11"
        fill="var(--color-fg-muted)"
      >
        Plattform-Kern
      </text>

      {placedLeft.map((p) => (
        <NodeBox key={p.node.id} placed={p} />
      ))}
      {placedRight.map((p) => (
        <NodeBox key={p.node.id} placed={p} />
      ))}

      {/* [VISION]-Zone: abgesetzt, gestrichelt, OHNE Verbindung zum Kern. */}
      {model.vision.length > 0 && (
        <g data-testid="vision-zone">
          <rect
            x={LEFT_X}
            y={visionTop}
            width={VB_W - 2 * LEFT_X}
            height={visionH}
            rx={8}
            fill="none"
            stroke="var(--color-line-subtle)"
            strokeWidth="1"
            strokeDasharray="5 4"
          />
          <text x={LEFT_X + 12} y={visionTop + 22} fontSize="12" fontWeight="600" fill="var(--color-fg-muted)">
            [VISION] — geplant, nicht verbunden
          </text>
          {model.vision.map((node, i) => (
            <text
              key={node.id}
              x={LEFT_X + 12 + (i % 3) * 230}
              y={visionTop + 48 + Math.floor(i / 3) * 22}
              fontSize="12.5"
              fill="var(--color-fg-secondary)"
            >
              ◌ {truncate(node.label, 26)}
            </text>
          ))}
        </g>
      )}
    </svg>
  );
}

function Connector({ placed, coreX, coreCY }: { placed: PlacedNode; coreX: number; coreCY: number }) {
  const { node, x, y, side } = placed;
  const status = normalizeStatus(node.status);
  const color = `var(--color-${connectorToken(status)})`;
  const nodeAnchorX = side === "left" ? x + NODE_W : x;
  const nodeY = y + NODE_H / 2;
  const dashed = status !== "verbunden";

  const flowToCore = node.direction === "liefert" || node.direction === "beides";
  const flowFromCore = node.direction === "liest" || node.direction === "beides";

  return (
    <g aria-hidden="true">
      <line
        x1={nodeAnchorX}
        y1={nodeY}
        x2={coreX}
        y2={coreCY}
        stroke={color}
        strokeWidth="1.5"
        strokeDasharray={dashed ? "5 4" : undefined}
      />
      {/* Pfeilspitze am Kern-Ende, wenn Fluss zum Kern (Eingang: nach rechts in den Kern). */}
      {flowToCore &&
        arrowHead(coreX, coreCY, side === "left" ? "right" : "left", color)}
      {/* Pfeilspitze am Knoten-Ende, wenn Fluss vom Kern weg (MCP liest → nach außen). */}
      {flowFromCore &&
        arrowHead(nodeAnchorX, nodeY, side === "left" ? "left" : "right", color)}
    </g>
  );
}
