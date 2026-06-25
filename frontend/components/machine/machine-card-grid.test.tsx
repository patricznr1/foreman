// ============================================================
//  FOREMAN Frontend — components/machine/machine-card-grid.test.tsx
//  Zweck: Das Karten-Grid unter „Linie & Maschinen" — Karten (kein Reiter),
//         gruppiert nach Synoptik-Stufe (Fördern/Pressen/…), in kanonischer
//         Reihenfolge; leerer Zugriff wird ehrlich benannt.
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { MachineCardOut } from "@/lib/api/contracts";
import { makeMachineCard } from "@/lib/machine/testing/card-fixture";
import { RealtimeProvider } from "@/lib/realtime/realtime-context";
import { RealtimeStore } from "@/lib/realtime/realtime-store";
import { FakeTransport } from "@/lib/realtime/testing/fake-transport";

import { MachineCardGrid } from "./machine-card-grid";

function card(id: number, machineClass: string, label: string): MachineCardOut {
  return makeMachineCard({ id, label, machine_class: machineClass, external_id: label });
}

function renderGrid(cards: MachineCardOut[]) {
  const store = new RealtimeStore(new FakeTransport());
  return render(
    <RealtimeProvider store={store}>
      <MachineCardGrid cards={cards} />
    </RealtimeProvider>,
  );
}

describe("MachineCardGrid", () => {
  it("gruppiert die Karten nach Synoptik-Stufe in kanonischer Reihenfolge", () => {
    renderGrid([card(1, "vision", "VS-01"), card(2, "feeder", "FD-01"), card(3, "servo_press", "PR-01")]);
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(["Fördern", "Pressen", "Endkontrolle"]);
  });

  it("rendert je Maschine eine Karte mit Sprung in die Detailsicht", () => {
    renderGrid([card(2, "feeder", "FD-01"), card(4, "feeder", "FD-02")]);
    expect(screen.getByRole("link", { name: "Maschine FD-01" })).toHaveAttribute(
      "href",
      "/machines/2",
    );
    expect(screen.getByRole("link", { name: "Maschine FD-02" })).toHaveAttribute(
      "href",
      "/machines/4",
    );
  });

  it("benennt leeren Zugriff ehrlich", () => {
    renderGrid([]);
    expect(screen.getByText(/Keine Maschinen/)).toBeInTheDocument();
  });
});
