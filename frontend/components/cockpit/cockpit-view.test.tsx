// ============================================================
//  FOREMAN Frontend — components/cockpit/cockpit-view.test.tsx
//  Zweck: Integrationstest des Orchestrators (§4A): Erstbild aus dem HTTP-Snapshot,
//         Live-Aktualisierung über das WS-Thema "overview" (FakeTransport, transport-
//         agnostisch), Rollen-Varianten (Manager Flottenbild / Schichtleiter
//         Linienbild), Geltungsbereichs-Filter, Querlink Zelle → B, und die
//         Degradation (offline → gecacht, eingefroren). Föderiertes Mehr-Werk-Bild
//         als markiertes Zielbild.
// ============================================================
import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const push = vi.fn();
vi.mock("next/navigation", () => ({ useRouter: () => ({ push }) }));

import type { CurrentUser, FleetOverviewOut, MachineStatus, MachineStatusOut } from "@/lib/api/contracts";
import { RealtimeProvider } from "@/lib/realtime/realtime-context";
import { RealtimeStore } from "@/lib/realtime/realtime-store";
import { FakeTransport } from "@/lib/realtime/testing/fake-transport";
import type { CockpitScope } from "@/lib/cockpit/types";

import { CockpitView } from "./cockpit-view";

const MANAGER: CurrentUser = {
  id: 1,
  email: "m@x.de",
  role: "manager",
  assigned_line_ids: [],
  assigned_machine_ids: [],
};
const LEAD: CurrentUser = { ...MANAGER, role: "shift_lead", assigned_line_ids: [1] };

const FLEET: CockpitScope = { machineClass: null, lineId: null };

function overview(machines: Partial<MachineStatusOut>[]): FleetOverviewOut {
  const full: MachineStatusOut[] = machines.map((m, i) => ({
    id: i + 1,
    label: `M${i + 1}`,
    line_id: 1,
    machine_class: "Presse",
    status: "healthy",
    open_alarm_count: 0,
    open_by_severity: {},
    last_alarm_at: null,
    ...m,
  }));
  const byStatus: Record<MachineStatus, number> = {
    healthy: 0,
    drift_active: 0,
    open_warning: 0,
    critical: 0,
  };
  for (const m of full) {
    byStatus[m.status] += 1;
  }
  return {
    machines: full,
    by_status: byStatus,
    open_alarm_total: full.reduce((s, m) => s + m.open_alarm_count, 0),
    stream: { active: false, last_reading_at: null },
  };
}

function setup(user: CurrentUser, initialData?: FleetOverviewOut, scope: CockpitScope = FLEET) {
  const transport = new FakeTransport();
  const store = new RealtimeStore(transport, { throttleMs: 50 });
  render(
    <RealtimeProvider store={store}>
      <CockpitView user={user} scope={scope} initialData={initialData} />
    </RealtimeProvider>,
  );
  return { transport, store };
}

const TWO_CLASSES = overview([
  { id: 1, label: "Presse 1", machine_class: "Presse", status: "healthy" },
  { id: 2, label: "Spindel 1", machine_class: "Spindel", status: "open_warning", open_alarm_count: 2, open_by_severity: { critical: 1, warning: 1 } },
]);

describe("CockpitView", () => {
  it("baut das Cockpit aus dem HTTP-Snapshot auf (Scope, KPIs, Heatmap, Prioritätsspalte)", () => {
    setup(MANAGER, TWO_CLASSES);
    expect(screen.getByRole("region", { name: "Flotten-Cockpit" })).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Geltungsbereich" })).toHaveTextContent("Flotte");
    expect(screen.getByRole("group", { name: "Flotten-Kennzahlen" })).toBeInTheDocument();
    expect(screen.getByRole("grid")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Braucht Blick jetzt" })).toBeInTheDocument();
    expect(screen.getByText(/Zielbild/)).toBeInTheDocument(); // Mehr-Werk-Föderation markiert
  });

  it("Rollen-Varianten: Manager Flottenbild, Schichtleiter Linienbild", () => {
    const { unmount } = renderRole(MANAGER);
    expect(screen.getByText("Flottenbild — alle Werke und Klassen")).toBeInTheDocument();
    unmount();
    renderRole(LEAD);
    expect(screen.getByText("Linienbild — Ihre Linien")).toBeInTheDocument();
  });

  it("filtert die Heatmap auf den Geltungsbereich (Klasse)", () => {
    setup(MANAGER, TWO_CLASSES, { machineClass: "Presse", lineId: null });
    expect(screen.getByRole("gridcell", { name: /Presse 1/ })).toBeInTheDocument();
    expect(screen.queryByRole("gridcell", { name: /Spindel 1/ })).toBeNull();
  });

  it("Querlink: Klick auf eine Zelle navigiert ins Maschinen-Detail (B)", () => {
    setup(MANAGER, TWO_CLASSES);
    fireEvent.click(screen.getByRole("gridcell", { name: /Spindel 1/ }));
    expect(push).toHaveBeenCalledWith("/machines/2");
  });

  describe("Live & Degradation", () => {
    beforeEach(() => {
      vi.useFakeTimers();
    });
    afterEach(() => {
      vi.useRealTimers();
    });

    it("aktualisiert per WS-Update ohne Sprung (Snapshot → live, Stand-Stempel)", () => {
      const { transport } = setup(MANAGER, overview([{ id: 1, label: "Presse 1", status: "healthy" }]));
      act(() => {
        transport.emit(
          "overview",
          overview([{ id: 1, label: "Presse 1", status: "open_warning", open_alarm_count: 1, open_by_severity: { critical: 1 } }]),
        );
        vi.advanceTimersByTime(50);
      });
      expect(screen.getByText(/Live/)).toBeInTheDocument();
    });

    it("Degradation: Verbindung weg → gecacht, eingefroren (kein weißer Screen)", () => {
      const { transport } = setup(MANAGER, overview([{ id: 1, label: "Presse 1", status: "healthy" }]));
      act(() => {
        transport.emit("overview", overview([{ id: 1, label: "Presse 1", status: "healthy" }]));
        vi.advanceTimersByTime(50);
      });
      expect(screen.getByText(/Live/)).toBeInTheDocument();
      act(() => {
        transport.setStatus("closed");
      });
      expect(screen.getByText(/Gecacht/)).toBeInTheDocument();
      // Daten bleiben sichtbar (eingefroren), kein Leerlaufen
      expect(screen.getByRole("grid")).toBeInTheDocument();
    });
  });
});

function renderRole(user: CurrentUser) {
  const transport = new FakeTransport();
  const store = new RealtimeStore(transport, { throttleMs: 50 });
  return render(
    <RealtimeProvider store={store}>
      <CockpitView user={user} scope={FLEET} initialData={TWO_CLASSES} />
    </RealtimeProvider>,
  );
}
