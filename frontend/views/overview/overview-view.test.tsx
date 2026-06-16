// ============================================================
//  FOREMAN Frontend — views/overview/overview-view.test.tsx
//  Zweck: Durchstich-Integrationstest — Erstbild aus dem HTTP-Snapshot (als
//         gecacht), dann Live-Aktualisierung über das WS-Thema "overview"
//         (gegen FakeTransport, transport-agnostisch). Plus A11y-Smoke:
//         benannte Region, Überschrift, Maschinen-Liste.
//  Architektur-Einordnung: Quality-Gate (Akzeptanzkriterium Durchstich e2e).
// ============================================================
import { SessionProvider } from "@/lib/auth/use-session";
import { RealtimeProvider } from "@/lib/realtime/realtime-context";
import { RealtimeStore } from "@/lib/realtime/realtime-store";
import { FakeTransport } from "@/lib/realtime/testing/fake-transport";
import type { CurrentUser, FleetOverviewOut, MachineStatus } from "@/lib/api/contracts";
import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { OverviewView } from "./overview-view";

const MANAGER: CurrentUser = {
  id: 1,
  email: "manager@x.de",
  role: "manager",
  assigned_line_ids: [],
  assigned_machine_ids: [],
};

function makeOverview(openAlarms: number, status: MachineStatus = "healthy"): FleetOverviewOut {
  return {
    machines: [
      {
        id: 1,
        label: "Presse 1",
        line_id: 1,
        machine_class: "Presse",
        status,
        open_alarm_count: openAlarms,
        open_by_severity: {},
        last_alarm_at: null,
      },
    ],
    by_status: {
      healthy: status === "healthy" ? 1 : 0,
      drift_active: status === "drift_active" ? 1 : 0,
      open_warning: status === "open_warning" ? 1 : 0,
    },
    open_alarm_total: openAlarms,
  };
}

function setup(initialData?: FleetOverviewOut) {
  const transport = new FakeTransport();
  const store = new RealtimeStore(transport, { throttleMs: 50 });
  render(
    <SessionProvider user={MANAGER}>
      <RealtimeProvider store={store}>
        <OverviewView initialData={initialData} />
      </RealtimeProvider>
    </SessionProvider>,
  );
  return { transport, store };
}

describe("Durchstich: OverviewView", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("zeigt den HTTP-Snapshot beim Laden und ist barrierearm benannt", () => {
    setup(makeOverview(0));
    expect(screen.getByRole("heading", { name: "Flotten-Übersicht" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Flotten-Übersicht" })).toBeInTheDocument();
    expect(screen.getByRole("list", { name: "Maschinen-Status" })).toBeInTheDocument();
    expect(screen.getByText("Presse 1")).toBeInTheDocument();
  });

  it("aktualisiert per WS-Update (Snapshot → live)", () => {
    const { transport } = setup(makeOverview(0));

    act(() => {
      transport.emit("overview", makeOverview(3, "open_warning"));
      vi.advanceTimersByTime(50);
    });

    expect(screen.getByText("3")).toBeInTheDocument(); // offene Alarme aktualisiert
    expect(screen.getByText(/Live/)).toBeInTheDocument(); // Herkunft jetzt live
  });

  it("ohne Snapshot und ohne Daten: Lade-Zustand (kein weißer Screen)", () => {
    const transport = new FakeTransport();
    const store = new RealtimeStore(transport, { throttleMs: 50 });
    // Verbindung noch nicht offen → loading
    render(
      <SessionProvider user={MANAGER}>
        <RealtimeProvider store={store}>
          <OverviewView />
        </RealtimeProvider>
      </SessionProvider>,
    );
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});
