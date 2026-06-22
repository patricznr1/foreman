// ============================================================
//  FOREMAN Frontend — lib/platform/url.test.ts
//  Zweck: Sichert, dass die BFF-Pfade exakt die realen Routen/Query-Parameter
//         treffen (GET /api/v1/topology mit probe/fresh_within_minutes; GET
//         /api/v1/audit mit gefilterter Query inkl. Pagination).
// ============================================================
import { describe, expect, it } from "vitest";
import { emptyAuditFilter } from "./audit-filter";
import { auditEndpoint, topologyEndpoint } from "./url";

describe("topologyEndpoint", () => {
  it("setzt probe immer explizit (bewusster, sichtbarer Refresh)", () => {
    expect(topologyEndpoint({ probe: true })).toBe("/api/v1/topology?probe=true");
    expect(topologyEndpoint({ probe: false })).toBe("/api/v1/topology?probe=false");
  });

  it("hängt fresh_within_minutes nur an, wenn gesetzt", () => {
    expect(topologyEndpoint({ probe: true, freshWithinMinutes: 120 })).toBe(
      "/api/v1/topology?probe=true&fresh_within_minutes=120",
    );
  });
});

describe("auditEndpoint", () => {
  it("der leere Filter ergibt nur Pagination", () => {
    expect(auditEndpoint(emptyAuditFilter())).toBe("/api/v1/audit?limit=50&offset=0");
  });

  it("kodiert gesetzte Filter URL-sicher", () => {
    const url = auditEndpoint({
      ...emptyAuditFilter(),
      actionType: "mcp_retrieval",
      actor: "v1:ab cd",
      machineId: 7,
    });
    expect(url.startsWith("/api/v1/audit?")).toBe(true);
    expect(url).toContain("action_type=mcp_retrieval");
    expect(url).toContain("actor=v1%3Aab+cd");
    expect(url).toContain("machine_id=7");
  });
});
