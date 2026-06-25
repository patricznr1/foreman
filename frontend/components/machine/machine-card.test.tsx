// ============================================================
//  FOREMAN Frontend — components/machine/machine-card.test.tsx
//  Zweck: Die EINE kanonische lebende Maschinenkarte. Sichert: Steckbrief + Wert
//         und Einheit je Datenpunkt + ehrlicher Status (Beobachtung), Live-Nachrücken
//         über machine:{id}, und ehrliche Stale-Anzeige bei gestopptem Stream.
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { MachineCardOut } from "@/lib/api/contracts";
import { makeMachineCard } from "@/lib/machine/testing/card-fixture";
import { RealtimeProvider } from "@/lib/realtime/realtime-context";
import { RealtimeStore } from "@/lib/realtime/realtime-store";
import { FakeTransport } from "@/lib/realtime/testing/fake-transport";

import { MachineCard } from "./machine-card";

function makeCard(overrides: Partial<MachineCardOut> = {}): MachineCardOut {
  return makeMachineCard({
    id: 7,
    label: "PR-02",
    manufacturer: "Bosch Rexroth",
    external_id: "PR-02",
    location: "Halle West",
    components: [{ id: 1, label: "Werkzeug", component_type: "tool" }],
    data_points: [
      {
        id: 20,
        component_id: 1,
        name: "press_force",
        kind: "analog",
        measurement_type: "force",
        unit: "kN",
        normal_min: 0,
        normal_max: 250,
        last_value: 212.4,
        last_value_at: "2026-06-25T11:59:00Z",
        status: "out_of_band",
      },
    ],
    stream: { active: true, last_reading_at: "2026-06-25T11:59:00Z" },
    ...overrides,
  });
}

function renderCard(initial: MachineCardOut, density?: "compact" | "full") {
  const transport = new FakeTransport();
  const store = new RealtimeStore(transport);
  const utils = render(
    <RealtimeProvider store={store}>
      <MachineCard initial={initial} density={density} />
    </RealtimeProvider>,
  );
  return { transport, ...utils };
}

describe("MachineCard", () => {
  it("zeigt Steckbrief sowie Wert und Einheit je Datenpunkt", () => {
    renderCard(makeCard());
    expect(screen.getByText("PR-02")).toBeInTheDocument();
    expect(screen.getByText("press_force")).toBeInTheDocument();
    expect(screen.getByText("212,4")).toBeInTheDocument();
    expect(screen.getByText("kN")).toBeInTheDocument();
  });

  it("zeigt den ehrlichen Datenpunkt-Status als Beobachtung in Hallensprache", () => {
    renderCard(makeCard());
    expect(screen.getByRole("img", { name: "Außerhalb Normalbereich" })).toBeInTheDocument();
  });

  it("rückt live nach, sobald ein machine:{id}-Push eintrifft", async () => {
    const { transport } = renderCard(makeCard());
    const base = makeCard();
    const firstDp = base.data_points[0];
    transport.emit("machine:7", {
      ...base,
      data_points: firstDp ? [{ ...firstDp, last_value: 188.0, status: "ok" }] : [],
    });
    expect(await screen.findByText("188")).toBeInTheDocument();
  });

  it("zeigt bei gestopptem Eingangs-Stream den Stand statt Frische vorzutäuschen", () => {
    renderCard(makeCard({ stream: { active: false, last_reading_at: "2026-06-25T11:59:00Z" } }));
    expect(screen.getByText(/Stand vor/)).toBeInTheDocument();
  });

  it("ist im Grid eine Karte mit Sprung in die Detailsicht (kein Reiter)", () => {
    renderCard(makeCard(), "compact");
    expect(screen.getByRole("link")).toHaveAttribute("href", "/machines/7");
  });
});
