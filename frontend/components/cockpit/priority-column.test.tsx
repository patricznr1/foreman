// ============================================================
//  FOREMAN Frontend — components/cockpit/priority-column.test.tsx
//  Zweck: Sichert die „braucht Blick jetzt"-Spalte (§4A): reale Querlink-Ziele
//         (kritisch → B Maschine, Drift → E, sonst → B), mehrkanalige Einträge, Leerzustand.
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { MachineStatusOut } from "@/lib/api/contracts";
import { buildPriorityEntries } from "@/lib/cockpit/priority";

import { PriorityColumn } from "./priority-column";

function machine(over: Partial<MachineStatusOut> = {}): MachineStatusOut {
  return {
    id: 1,
    label: "M",
    line_id: 1,
    machine_class: "Presse",
    status: "healthy",
    open_alarm_count: 0,
    open_by_severity: {},
    last_alarm_at: null,
    ...over,
  };
}

describe("PriorityColumn", () => {
  it("listet die dringendsten Einstiege mit ihren realen Querlink-Zielen", () => {
    const entries = buildPriorityEntries([
      machine({ id: 1, label: "Presse 1", status: "open_warning", open_alarm_count: 1, open_by_severity: { critical: 1 } }),
      machine({ id: 5, label: "Spindel 5", status: "drift_active", open_alarm_count: 1, open_by_severity: { warning: 1 } }),
      machine({ id: 9, label: "Bohrer 9", status: "open_warning", open_alarm_count: 1, open_by_severity: { warning: 1 } }),
    ]);
    render(<PriorityColumn entries={entries} />);
    expect(screen.getByRole("region", { name: "Braucht Blick jetzt" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Presse 1/ })).toHaveAttribute("href", "/machines/1"); // kritisch → B (Maschine im Kontext)
    expect(screen.getByRole("link", { name: /Spindel 5/ })).toHaveAttribute("href", "/insights/prediction?machine=5"); // Drift → E
    expect(screen.getByRole("link", { name: /Bohrer 9/ })).toHaveAttribute("href", "/machines/9"); // sonst → B
  });

  it("Leerzustand: ruhiger Hinweis (nichts Dringendes)", () => {
    render(<PriorityColumn entries={[]} />);
    expect(screen.getByRole("status")).toHaveTextContent("Nichts Dringendes");
  });
});
