// ============================================================
//  FOREMAN Frontend — components/machine/machine-list.test.tsx
//  Zweck: Sichert die Maschinen-Liste (/machines) mit Link zur Detail-Sicht + Leerfall.
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { MachineRead } from "@/lib/api/contracts";

import { MachineList } from "./machine-list";

function machine(id: number, label: string): MachineRead {
  return {
    id,
    line_id: 3,
    external_id: null,
    label,
    machine_class: "cnc",
    manufacturer: null,
    location: "Halle A",
    created_at: "2026-06-01T00:00:00Z",
  };
}

describe("MachineList", () => {
  it("listet Maschinen mit Link zur Detail-Sicht", () => {
    render(<MachineList machines={[machine(7, "CNC-Fräse 7"), machine(8, "CNC-Fräse 8")]} />);
    expect(screen.getByRole("link", { name: /CNC-Fräse 7/ })).toHaveAttribute("href", "/machines/7");
  });

  it("leerer Zugriff: Hinweis statt Liste", () => {
    render(<MachineList machines={[]} />);
    expect(screen.getByText(/Keine Maschinen/)).toBeInTheDocument();
  });
});
