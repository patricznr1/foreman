// ============================================================
//  FOREMAN Frontend — components/synoptik/synoptik-view.test.tsx
//  Zweck: Integrationstest des 3D-Linien-Orchestrators — Erstbild aus dem
//         HTTP-Snapshot (12 Maschinen), Ansichts-Umschalter aktiv, Klick →
//         kanonische Karte (loser Vertrag), Live-Umfärben per WS-Update. Der
//         Renderer ist gemockt (WebGL ist im Test irrelevant; geprüft wird der
//         Datenpfad + Klick-Vertrag).
// ============================================================
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

// Renderer mocken: legt die empfangenen Placements offen und löst onSelectMachine aus.
vi.mock("./synoptik-scene", () => ({
  SynoptikScene: ({
    placements,
    onSelectMachine,
  }: {
    placements: { machineId: number }[];
    onSelectMachine: (machineId: number) => void;
  }) => (
    <button
      type="button"
      data-testid="scene"
      onClick={() => {
        const first = placements[0];
        if (first !== undefined) {
          onSelectMachine(first.machineId);
        }
      }}
    >
      scene:{placements.length}
    </button>
  ),
}));

import type { CurrentUser, FleetOverviewOut, MachineStatus, MachineStatusOut } from "@/lib/api/contracts";
import { RealtimeProvider } from "@/lib/realtime/realtime-context";
import { RealtimeStore } from "@/lib/realtime/realtime-store";
import { FakeTransport } from "@/lib/realtime/testing/fake-transport";
import { makeParkMachines } from "@/lib/synoptic3d/testing/fixtures";

import { SynoptikView } from "./synoptik-view";

const MANAGER: CurrentUser = {
  id: 1,
  email: "m@x.de",
  role: "manager",
  assigned_line_ids: [],
  assigned_machine_ids: [],
};

function fleet(machines: MachineStatusOut[]): FleetOverviewOut {
  return {
    machines,
    by_status: { healthy: 0, drift_active: 0, open_warning: 0 },
    open_alarm_total: 0,
    stream: { active: true, last_reading_at: null },
  };
}

function parkWithStatus(overrides: Record<number, MachineStatus>): MachineStatusOut[] {
  return makeParkMachines().map((machine) => {
    const next = overrides[machine.id];
    return next === undefined ? machine : { ...machine, status: next };
  });
}

function setup(initialData?: FleetOverviewOut) {
  const transport = new FakeTransport();
  const store = new RealtimeStore(transport, { throttleMs: 50 });
  render(
    <RealtimeProvider store={store}>
      <SynoptikView user={MANAGER} initialData={initialData} />
    </RealtimeProvider>,
  );
  return { transport, store };
}

describe("SynoptikView", () => {
  it("baut die Linie aus dem Snapshot: 12 Maschinen, Umschalter aktiv, Legende, Leiste", () => {
    setup(fleet(makeParkMachines()));

    expect(screen.getByRole("region", { name: "Anlagen-Synoptik 3D" })).toBeInTheDocument();
    expect(screen.getByTestId("scene")).toHaveTextContent("scene:12");
    expect(screen.getByRole("link", { name: "3D-Linie" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByText("Status je Maschine:")).toBeInTheDocument();

    const list = screen.getByRole("navigation", { name: "Maschinen der Montagelinie 1" });
    expect(within(list).getAllByRole("link")).toHaveLength(12);
    expect(within(list).getByRole("link", { name: /Fuegepresse 2/ })).toHaveAttribute(
      "href",
      "/machines/8",
    );
    // Hallensprache: kein internes Akronym im sichtbaren UI.
    expect(screen.queryByText(/HITL/)).toBeNull();
  });

  it("Klick auf eine Maschine navigiert zur kanonischen Karte (loser Vertrag)", () => {
    setup(fleet(makeParkMachines()));
    // Erstes Placement der Sequenz = FD-01 (id 5).
    fireEvent.click(screen.getByTestId("scene"));
    expect(push).toHaveBeenCalledWith("/machines/5");
  });

  describe("Live-Update", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });
    afterEach(() => {
      vi.useRealTimers();
    });

    it("färbt eine Maschine bei WS-Update live um (Status wechselt)", () => {
      const { transport } = setup(fleet(makeParkMachines()));
      // Vorher: PR-02 (id 8) ist „Offene Warnung".
      expect(
        screen.getByRole("link", { name: /Fuegepresse 2, Offene Warnung/ }),
      ).toBeInTheDocument();

      act(() => {
        transport.emit("overview", fleet(parkWithStatus({ 8: "healthy" })));
        vi.advanceTimersByTime(60);
      });

      expect(
        screen.getByRole("link", { name: /Fuegepresse 2, Normalbetrieb/ }),
      ).toBeInTheDocument();
    });
  });
});
