// ============================================================
//  FOREMAN Frontend — components/synoptik/synoptik-machine-list.test.tsx
//  Zweck: Prüft die barrierefreie Maschinen-Leiste — alle Maschinen als Links auf
//         die kanonische Karte (loser Vertrag machine_id → Karte) und der Status
//         barrierefrei im Link-Namen.
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { buildLineLayout } from "@/lib/synoptic3d/layout";
import { makeParkMachines } from "@/lib/synoptic3d/testing/fixtures";

import { SynoptikMachineList } from "./synoptik-machine-list";

describe("SynoptikMachineList", () => {
  const placements = buildLineLayout(makeParkMachines());

  it("listet alle Maschinen als Links auf die kanonische Karte (machineHref)", () => {
    render(<SynoptikMachineList placements={placements} />);
    expect(screen.getAllByRole("link")).toHaveLength(12);
    expect(screen.getByRole("link", { name: /Fuegepresse 2/ })).toHaveAttribute("href", "/machines/8");
    expect(screen.getByRole("link", { name: /Teilezufuehrung A/ })).toHaveAttribute("href", "/machines/5");
  });

  it("trägt den Maschinen-Status barrierefrei im Link-Namen", () => {
    render(<SynoptikMachineList placements={placements} />);
    expect(
      screen.getByRole("link", { name: /Fuegepresse 2, Offene Warnung/ }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /Teilezufuehrung A, Normalbetrieb/ }),
    ).toBeInTheDocument();
  });

  it("erfüllt die Handschuh-Mindesthöhe (Touch-Ziel) auf jedem Link", () => {
    render(<SynoptikMachineList placements={placements} />);
    for (const link of screen.getAllByRole("link")) {
      expect(link).toHaveClass("touch-target");
    }
  });
});
