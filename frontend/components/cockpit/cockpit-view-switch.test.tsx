// ============================================================
//  FOREMAN Frontend — components/cockpit/cockpit-view-switch.test.tsx
//  Zweck: Prüft den Ansichts-Umschalter (Heatmap ⇆ 3D-Linie): korrekte Ziele,
//         aktive Markierung (aria-current) für die laufende Sicht.
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CockpitViewSwitch } from "./cockpit-view-switch";

describe("CockpitViewSwitch", () => {
  it("verlinkt beide Sichten und markiert die aktive (3D-Linie)", () => {
    render(<CockpitViewSwitch active="synoptik" />);
    const heatmap = screen.getByRole("link", { name: "Heatmap" });
    const synoptik = screen.getByRole("link", { name: "3D-Linie" });
    expect(heatmap).toHaveAttribute("href", "/overview");
    expect(synoptik).toHaveAttribute("href", "/synoptik");
    expect(synoptik).toHaveAttribute("aria-current", "page");
    expect(heatmap).not.toHaveAttribute("aria-current");
  });

  it("markiert die Heatmap als aktiv, wenn sie läuft", () => {
    render(<CockpitViewSwitch active="heatmap" />);
    expect(screen.getByRole("link", { name: "Heatmap" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "3D-Linie" })).not.toHaveAttribute("aria-current");
  });
});
