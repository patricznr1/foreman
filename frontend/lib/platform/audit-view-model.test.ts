// ============================================================
//  FOREMAN Frontend — lib/platform/audit-view-model.test.ts
//  Zweck: Sichert, dass der Akteur NUR als pseudonymer '#hex6'-Handle erscheint
//         (nie Klartext, nie der volle HMAC-Token), die Backend-Reihenfolge
//         (jüngste zuerst) erhalten bleibt und detail-JSONB defensiv flach
//         (keine tiefen Objekte) zu Strings wird.
// ============================================================
import { describe, expect, it } from "vitest";
import { assembleAuditRow, assembleAuditRows, detailPairs } from "./audit-view-model";
import { makeAuditEntry, makeMcpRetrievalEntry } from "./testing/fixtures";

describe("assembleAuditRow", () => {
  it("maskiert den Akteur zu #hex6 — nie der volle HMAC-Token", () => {
    const row = assembleAuditRow(
      makeAuditEntry({ actor: "v1:9f8e7d6c5b4a39281706f5e4d3c2b1a0" }),
    );
    expect(row.actorHandle).toBe("#9f8e7d");
    expect(row.actorHandle).not.toContain("v1:");
    expect(row.actorHandle?.length).toBe(7); // '#' + 6 hex
  });

  it("ein fehlender Akteur bleibt null (kein erfundener Handle)", () => {
    expect(assembleAuditRow(makeAuditEntry({ actor: null })).actorHandle).toBeNull();
  });

  it("reicht die strukturellen Felder unverändert durch", () => {
    const row = assembleAuditRow(makeMcpRetrievalEntry({ id: 99, target_id: 42, machine_id: 9 }));
    expect(row.id).toBe(99);
    expect(row.actionType).toBe("mcp_retrieval");
    expect(row.origin).toBe("mcp");
    expect(row.targetKind).toBe("explanation");
    expect(row.targetId).toBe(42);
    expect(row.machineId).toBe(9);
  });
});

describe("detailPairs", () => {
  it("flacht primitive Werte zu Strings", () => {
    expect(detailPairs({ tool: "recall", result_count: 3, ok: true })).toEqual([
      ["tool", "recall"],
      ["result_count", "3"],
      ["ok", "true"],
    ]);
  });

  it("null/undefined → '—' und verschachtelte Objekte → kompaktes JSON", () => {
    const pairs = new Map(detailPairs({ empty: null, nested: { a: 1 } }));
    expect(pairs.get("empty")).toBe("—");
    expect(pairs.get("nested")).toBe('{"a":1}');
  });

  it("null detail → leere Liste", () => {
    expect(detailPairs(null)).toEqual([]);
  });
});

describe("assembleAuditRows", () => {
  it("bewahrt die Backend-Reihenfolge (jüngste zuerst) — sortiert nicht um", () => {
    const entries = [
      makeAuditEntry({ id: 3, occurred_at: "2026-06-22T12:00:00+00:00" }),
      makeAuditEntry({ id: 2, occurred_at: "2026-06-21T12:00:00+00:00" }),
      makeAuditEntry({ id: 1, occurred_at: "2026-06-20T12:00:00+00:00" }),
    ];
    expect(assembleAuditRows(entries).map((r) => r.id)).toEqual([3, 2, 1]);
  });
});
