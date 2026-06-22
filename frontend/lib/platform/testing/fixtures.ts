// ============================================================
//  FOREMAN Frontend — lib/platform/testing/fixtures.ts
//  Zweck: Test-Bausteine der Sektion I (Topologie + Audit) im Builder-Muster:
//         sinnvolle Defaults, alles per Partial überschreibbar. Die Defaults
//         spiegeln den realen Backend-Vertrag (§22) — echte Knoten-Shapes,
//         pseudonyme Akteure, PII-freie detail-JSONB.
//  Architektur-Einordnung: Test-Hilfen (nicht im Produktiv-Bundle).
// ============================================================
import type { AuditEntryRead, TopologyNodeRead, TopologyViewRead } from "../types";

const GENERATED_AT = "2026-06-22T17:30:00+00:00";

export function makeNode(over: Partial<TopologyNodeRead> = {}): TopologyNodeRead {
  return {
    id: "source:opcua",
    label: "OPC UA",
    kind: "ingest_source",
    direction: "liefert",
    status: "verbunden",
    last_activity: "2026-06-22T17:28:00+00:00",
    internal: false,
    vision: false,
    detail: { protocol: "opcua" },
    ...over,
  };
}

export function makeSubstrateNode(over: Partial<TopologyNodeRead> = {}): TopologyNodeRead {
  return makeNode({
    id: "substrate",
    label: "Gedächtnis-Substrat",
    kind: "substrate",
    direction: "beides",
    status: "verbunden",
    detail: { configured: true, latency_ms: 42 },
    ...over,
  });
}

export function makeMcpNode(over: Partial<TopologyNodeRead> = {}): TopologyNodeRead {
  return makeNode({
    id: "mcp",
    label: "MCP-Schnittstelle (F7)",
    kind: "mcp_boundary",
    direction: "liest",
    status: "inaktiv",
    last_activity: null,
    detail: { configured: true, consumer_count: 1 },
    ...over,
  });
}

export function makeVisionNode(over: Partial<TopologyNodeRead> = {}): TopologyNodeRead {
  return makeNode({
    id: "vision:erp",
    label: "ERP",
    kind: "vision",
    direction: "keine",
    status: "unbekannt",
    last_activity: null,
    vision: true,
    detail: { note: "geplant — nicht verbunden ([VISION])" },
    ...over,
  });
}

export function makeTopologyView(over: Partial<TopologyViewRead> = {}): TopologyViewRead {
  return {
    nodes: [
      makeNode(),
      makeNode({
        id: "source:simulation",
        label: "Simulation (intern)",
        status: "verbunden",
        internal: true,
        detail: { protocol: "simulation" },
      }),
      makeSubstrateNode(),
      makeMcpNode(),
    ],
    vision: [
      makeVisionNode(),
      makeVisionNode({ id: "vision:energy_management", label: "Energiemanagement" }),
      makeVisionNode({
        id: "vision:simulation_software",
        label: "Simulationssoftware (extern)",
      }),
    ],
    generated_at: GENERATED_AT,
    ...over,
  };
}

let auditSeq = 5000;

export function makeAuditEntry(over: Partial<AuditEntryRead> = {}): AuditEntryRead {
  const id = over.id ?? ++auditSeq;
  return {
    id,
    occurred_at: "2026-06-22T17:25:00+00:00",
    created_at: "2026-06-22T17:25:00+00:00",
    action_type: "hitl_acknowledge",
    actor: "v1:9f8e7d6c5b4a39281706f5e4d3c2b1a09f8e7d6c5b4a39281706f5e4d3c2b1a0",
    actor_role: "shift_lead",
    origin: "dashboard",
    target_kind: "alarm",
    target_id: 1234,
    machine_id: 7,
    detail: { decision: "acknowledged" },
    ...over,
  };
}

export function makeMcpRetrievalEntry(over: Partial<AuditEntryRead> = {}): AuditEntryRead {
  return makeAuditEntry({
    action_type: "mcp_retrieval",
    actor: "v1:1111111111111111111111111111111111111111111111111111111111111111",
    actor_role: null,
    origin: "mcp",
    target_kind: "explanation",
    target_id: 42,
    machine_id: 9,
    detail: { tool: "recall_machine_context", result_count: 3 },
    ...over,
  });
}
