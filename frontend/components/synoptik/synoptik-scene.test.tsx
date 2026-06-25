// ============================================================
//  FOREMAN Frontend — components/synoptik/synoptik-scene.test.tsx
//  Zweck: Prüft die ehrliche Degradation des Renderers ohne WebGL (jsdom hat
//         keinen WebGL-Kontext) — Fallback-Hinweis sichtbar, 3D-Region trägt eine
//         beschreibende Bezeichnung. Die datengetriebene Logik (Layout/Status/
//         Routing/Swap) ist render-agnostisch in lib/synoptic3d/* getestet.
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { buildLineLayout } from "@/lib/synoptic3d/layout";
import { makeParkMachines } from "@/lib/synoptic3d/testing/fixtures";

import { SynoptikScene } from "./synoptik-scene";

describe("SynoptikScene", () => {
  it("degradiert ehrlich, wenn WebGL fehlt", async () => {
    const placements = buildLineLayout(makeParkMachines());
    render(<SynoptikScene placements={placements} onSelectMachine={() => undefined} />);

    expect(await screen.findByRole("status")).toHaveTextContent(/WebGL/);
    expect(screen.getByRole("img", { name: /Montagelinie 1/ })).toBeInTheDocument();
  });
});
