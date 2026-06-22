// ============================================================
//  FOREMAN Frontend — components/platform/audit-table.test.tsx
//  Zweck: Sichert die unveränderlich-lesende Audit-Tabelle: jüngste zuerst
//         (Reihenfolge unangetastet), Akteur NUR als pseudonymer '#hex6'-Handle
//         (nie der volle HMAC-Token), IDs in Monospace, und KEINE Mutations-
//         Affordance (keine Buttons in der Tabelle).
// ============================================================
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { assembleAuditRows } from "@/lib/platform/audit-view-model";
import { makeAuditEntry, makeMcpRetrievalEntry } from "@/lib/platform/testing/fixtures";
import { AuditTable } from "./audit-table";

describe("AuditTable", () => {
  it("rendert die Zeilen in der gelieferten Reihenfolge (jüngste zuerst)", () => {
    const rows = assembleAuditRows([
      makeAuditEntry({ id: 3, target_id: 30 }),
      makeAuditEntry({ id: 2, target_id: 20 }),
      makeMcpRetrievalEntry({ id: 1, target_id: 10 }),
    ]);
    render(<AuditTable rows={rows} />);
    const bodyRows = screen.getAllByRole("row").slice(1); // ohne Kopfzeile
    expect(bodyRows).toHaveLength(3);
    expect(bodyRows[0]).toHaveAttribute("data-audit-id", "3");
    expect(bodyRows[2]).toHaveAttribute("data-audit-id", "1");
  });

  it("zeigt den Akteur nur als #hex6 — nie den vollen HMAC-Token", () => {
    render(
      <AuditTable
        rows={assembleAuditRows([
          makeAuditEntry({ actor: "v1:9f8e7d6c5b4a39281706f5e4d3c2b1a0" }),
        ])}
      />,
    );
    expect(screen.getByText("#9f8e7d")).toBeInTheDocument();
    expect(screen.queryByText(/v1:/)).toBeNull();
  });

  it("rendert IDs in Monospace", () => {
    render(<AuditTable rows={assembleAuditRows([makeAuditEntry({ actor: "v1:abcdef0123" })])} />);
    const handle = screen.getByText("#abcdef");
    expect(handle.className).toContain("font-mono");
  });

  it("ist rein lesend — keine Buttons/Mutations-Affordance in der Tabelle", () => {
    render(<AuditTable rows={assembleAuditRows([makeAuditEntry(), makeMcpRetrievalEntry()])} />);
    const table = screen.getByRole("table");
    expect(within(table).queryAllByRole("button")).toHaveLength(0);
    expect(within(table).queryAllByRole("textbox")).toHaveLength(0);
  });
});
