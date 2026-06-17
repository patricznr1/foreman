// ============================================================
//  FOREMAN Frontend — components/machine/machine-specs.test.tsx
//  Zweck: Sichert die lesbare Stammdaten-/Spezifikations-Darstellung.
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { ComponentRead, DataPointRead, MachineRead } from "@/lib/api/contracts";

import { MachineSpecs } from "./machine-specs";

const machine: MachineRead = {
  id: 7,
  line_id: 3,
  external_id: "EXT-7",
  label: "CNC-Fräse 7",
  machine_class: "cnc",
  manufacturer: "DMG",
  location: "Halle A",
  created_at: "2026-06-01T00:00:00Z",
};

const components: ComponentRead[] = [
  { id: 1, machine_id: 7, label: "Spindel", component_type: "spindle", created_at: "2026-06-01T00:00:00Z" },
];

const dataPoints: DataPointRead[] = [
  {
    id: 42,
    machine_id: 7,
    component_id: 1,
    name: "spindle_temp",
    kind: "analog",
    measurement_type: "temperature",
    unit: "°C",
    source: "simulation",
    address: null,
    normal_min: 10,
    normal_max: 20,
    created_at: "2026-06-01T00:00:00Z",
  },
];

describe("MachineSpecs", () => {
  it("zeigt Stammdaten lesbar (Klasse, Hersteller, Standort)", () => {
    render(<MachineSpecs machine={machine} components={components} dataPoints={dataPoints} />);
    expect(screen.getByText("cnc")).toBeInTheDocument();
    expect(screen.getByText("DMG")).toBeInTheDocument();
    expect(screen.getByText("Halle A")).toBeInTheDocument();
  });

  it("listet Komponenten und Datenpunkte", () => {
    render(<MachineSpecs machine={machine} components={components} dataPoints={dataPoints} />);
    expect(screen.getByText(/Spindel/)).toBeInTheDocument();
    expect(screen.getByText(/spindle_temp/)).toBeInTheDocument();
  });
});
