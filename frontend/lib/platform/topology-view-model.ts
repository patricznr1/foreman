// ============================================================
//  FOREMAN Frontend — lib/platform/topology-view-model.ts
//  Zweck: Formt die rohe Topologie-Antwort (TopologyViewRead, §22.2) in ein
//         geordnetes View-Modell: reale Knoten nach Kategorie (Eingänge → Substrat
//         → MCP-Grenze), die [VISION]-Knoten strikt getrennt. EHRLICH: es wird
//         NICHTS erfunden (nur vorhandene Knoten gruppiert); ein als `vision`
//         markierter Knoten landet IMMER in der Vision-Spalte (nie als reale
//         Verbindung), Status/Richtung werden defensiv normalisiert (fremder Wert
//         → „unbekannt"/„keine", nie grün geraten).
//  Architektur-Einordnung: reine Logik (Schicht 2), ohne UI testbar.
// ============================================================
import { normalizeDirection, normalizeStatus } from "./status";
import type {
  NodeCategory,
  NodeKind,
  TopologyModel,
  TopologyNodeModel,
  TopologyNodeRead,
  TopologyViewRead,
} from "./types";

const KNOWN_KINDS: ReadonlySet<string> = new Set([
  "ingest_source",
  "substrate",
  "mcp_boundary",
  "vision",
]);

function normalizeKind(raw: string, isVision: boolean): NodeKind {
  if (isVision) {
    return "vision";
  }
  if (KNOWN_KINDS.has(raw)) {
    return raw as NodeKind;
  }
  // Unerwartete Klasse: als Eingang einordnen (sichtbar, nicht verschluckt) —
  // der Status trägt die Ehrlichkeit (normalisiert → „unbekannt").
  return "ingest_source";
}

function categoryForKind(kind: NodeKind): NodeCategory {
  switch (kind) {
    case "ingest_source":
      return "input";
    case "substrate":
      return "substrate";
    case "mcp_boundary":
      return "mcp";
    case "vision":
      return "vision";
  }
}

/** Normalisiert einen rohen Knoten; `forceVision` erzwingt die Vision-Kategorie. */
function toNodeModel(node: TopologyNodeRead, forceVision: boolean): TopologyNodeModel {
  const isVision = forceVision || node.vision === true;
  const kind = normalizeKind(node.kind, isVision);
  return {
    id: node.id,
    label: node.label,
    kind,
    category: categoryForKind(kind),
    status: normalizeStatus(node.status),
    direction: normalizeDirection(node.direction),
    lastActivityIso: node.last_activity,
    internal: node.internal === true,
    isVision,
    detail: node.detail,
  };
}

/**
 * Baut das geordnete Topologie-Modell. Reale Knoten aus `nodes` werden nach
 * Kategorie verteilt; ein dort fälschlich `vision`-markierter Knoten wird
 * sicherheitshalber in die Vision-Spalte umgeleitet (nie als real). Alle Knoten
 * aus `vision` sind Vision.
 */
export function assembleTopology(view: TopologyViewRead): TopologyModel {
  const inputs: TopologyNodeModel[] = [];
  const substrate: TopologyNodeModel[] = [];
  const mcp: TopologyNodeModel[] = [];
  const vision: TopologyNodeModel[] = [];

  for (const raw of view.nodes) {
    const model = toNodeModel(raw, false);
    switch (model.category) {
      case "input":
        inputs.push(model);
        break;
      case "substrate":
        substrate.push(model);
        break;
      case "mcp":
        mcp.push(model);
        break;
      case "vision":
        // Sicherheits-Default: als vision markiert → nie als reale Verbindung.
        vision.push(model);
        break;
    }
  }

  for (const raw of view.vision) {
    vision.push(toNodeModel(raw, true));
  }

  return {
    inputs,
    substrate,
    mcp,
    vision,
    generatedAtIso: view.generated_at,
  };
}

/** Anzahl realer (nicht-vision) Knoten — für die Leer-Erkennung der Sicht. */
export function realNodeCount(model: TopologyModel): number {
  return model.inputs.length + model.substrate.length + model.mcp.length;
}

function readBool(detail: Record<string, unknown> | null, key: string): boolean | null {
  const value = detail?.[key];
  return typeof value === "boolean" ? value : null;
}

function readNumber(detail: Record<string, unknown> | null, key: string): number | null {
  const value = detail?.[key];
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

/**
 * Kuratierte Detail-Chips eines Knotens in HALLENSPRACHE — bewusst NICHT die rohe
 * detail-JSONB (kein internes Vokabular im UI, §8). Nur die bekannten, sprechenden
 * Felder; Unbekanntes wird weggelassen (kein Datenfriedhof). Reine Funktion.
 */
export function nodeDetailChips(node: TopologyNodeModel): string[] {
  const chips: string[] = [];
  const detail = node.detail;

  if (readBool(detail, "configured") === false) {
    chips.push("nicht konfiguriert");
  }
  if (readBool(detail, "probe_error") === true) {
    chips.push("Prüfung fehlgeschlagen");
  }
  const latency = readNumber(detail, "latency_ms");
  if (latency !== null) {
    chips.push(`Antwortzeit ${latency} ms`);
  }
  const consumers = readNumber(detail, "consumer_count");
  if (consumers !== null) {
    chips.push(consumers === 1 ? "1 Konsument" : `${consumers} Konsumenten`);
  }
  if (node.internal) {
    chips.push("interne Quelle");
  }
  return chips;
}
