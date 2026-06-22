// ============================================================
//  FOREMAN Frontend — lib/platform/audit-filter.test.ts
//  Zweck: Sichert, dass die Filter NUR die realen Query-Parameter erzeugen,
//         leere/ungültige Felder herausfallen, limit/offset defensiv geklemmt
//         werden und die Aktiv-Zählung Pagination ausnimmt.
// ============================================================
import { describe, expect, it } from "vitest";
import {
  activeFilterCount,
  auditQueryEntries,
  AUDIT_LIMIT_MAX,
  clampLimit,
  clampOffset,
  emptyAuditFilter,
} from "./audit-filter";

describe("emptyAuditFilter", () => {
  it("setzt keine inhaltlichen Filter, nur Pagination", () => {
    const entries = auditQueryEntries(emptyAuditFilter());
    expect(entries.map(([k]) => k)).toEqual(["limit", "offset"]);
    expect(activeFilterCount(emptyAuditFilter())).toBe(0);
  });
});

describe("auditQueryEntries", () => {
  it("übernimmt alle gesetzten, gültigen Felder", () => {
    const entries = auditQueryEntries({
      actionType: "mcp_retrieval",
      targetKind: "explanation",
      targetId: 42,
      actor: "v1:abc",
      machineId: 9,
      since: "2026-06-01T00:00",
      until: "2026-06-22T00:00",
      limit: 25,
      offset: 50,
    });
    const map = new Map(entries);
    expect(map.get("action_type")).toBe("mcp_retrieval");
    expect(map.get("target_kind")).toBe("explanation");
    expect(map.get("target_id")).toBe("42");
    expect(map.get("actor")).toBe("v1:abc");
    expect(map.get("machine_id")).toBe("9");
    expect(map.get("since")).toBe("2026-06-01T00:00");
    expect(map.get("until")).toBe("2026-06-22T00:00");
    expect(map.get("limit")).toBe("25");
    expect(map.get("offset")).toBe("50");
  });

  it("lässt leere Strings und nicht-positive IDs heraus", () => {
    const entries = auditQueryEntries({
      ...emptyAuditFilter(),
      targetKind: "   ",
      actor: "",
      targetId: 0,
      machineId: -3,
    });
    const keys = entries.map(([k]) => k);
    expect(keys).not.toContain("target_kind");
    expect(keys).not.toContain("actor");
    expect(keys).not.toContain("target_id");
    expect(keys).not.toContain("machine_id");
  });

  it("trimmt gesetzte Textfilter", () => {
    const entries = auditQueryEntries({ ...emptyAuditFilter(), actor: "  v1:xyz  " });
    expect(new Map(entries).get("actor")).toBe("v1:xyz");
  });
});

describe("clampLimit / clampOffset", () => {
  it("hält das Limit im Backend-Bereich 1..1000", () => {
    expect(clampLimit(0)).toBe(1);
    expect(clampLimit(5000)).toBe(AUDIT_LIMIT_MAX);
    expect(clampLimit(25)).toBe(25);
    expect(clampLimit(Number.NaN)).toBe(50);
    expect(clampLimit(25.9)).toBe(25);
  });

  it("hält den Offset bei ≥ 0 (ganzzahlig)", () => {
    expect(clampOffset(-10)).toBe(0);
    expect(clampOffset(100)).toBe(100);
    expect(clampOffset(7.8)).toBe(7);
  });
});

describe("activeFilterCount", () => {
  it("zählt nur inhaltliche Filter, nicht Pagination", () => {
    expect(
      activeFilterCount({ ...emptyAuditFilter(), actionType: "hitl_acknowledge", machineId: 3 }),
    ).toBe(2);
  });
});
