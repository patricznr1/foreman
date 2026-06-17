// ============================================================
//  FOREMAN Frontend — components/cockpit/cockpit-scope-bar.test.tsx
//  Zweck: Sichert die Geltungsbereichs-Leiste (§3.3/§4A): Breadcrumb-Pfad und die
//         dezent markierte Mehr-WERK-Föderation als ZIELBILD (nicht funktionsloser
//         Platzhalter).
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CockpitScopeBar } from "./cockpit-scope-bar";

describe("CockpitScopeBar", () => {
  it("zeigt den Föderations-Breadcrumb (Flotte ▸ Klasse ▸ Linie)", () => {
    render(<CockpitScopeBar scope={{ machineClass: "Presse", lineId: 2 }} />);
    const nav = screen.getByRole("navigation", { name: "Geltungsbereich" });
    expect(nav).toHaveTextContent("Flotte");
    expect(nav).toHaveTextContent("Klasse: Presse");
    expect(nav).toHaveTextContent("Linie 2");
    // Flotte ist ein Sprung-Link, die aktuelle Ebene (Linie) nicht
    expect(screen.getByRole("link", { name: "Flotte" })).toHaveAttribute("href", "/overview");
  });

  it("markiert die Mehr-WERK-Föderation als Zielbild (kein Platzhalter-Geröll)", () => {
    render(<CockpitScopeBar scope={{ machineClass: null, lineId: null }} />);
    expect(screen.getByText(/Zielbild/)).toBeInTheDocument();
  });
});
