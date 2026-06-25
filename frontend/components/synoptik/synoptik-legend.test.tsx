// ============================================================
//  FOREMAN Frontend — components/synoptik/synoptik-legend.test.tsx
//  Zweck: Prüft, dass die Legende die erreichbaren Maschinen-Zustände mehrkanalig
//         (FCSM-Indikator) zeigt.
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SynoptikLegend } from "./synoptik-legend";

describe("SynoptikLegend", () => {
  it("zeigt die drei erreichbaren Maschinen-Zustände als FCSM-Indikator", () => {
    render(<SynoptikLegend />);
    expect(screen.getByRole("img", { name: "Normalbetrieb" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Abweichung erkannt" })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Offene Warnung" })).toBeInTheDocument();
  });
});
