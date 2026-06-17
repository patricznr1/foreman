// ============================================================
//  FOREMAN Frontend — components/machine/machine-header.test.tsx
//  Zweck: Sichert den Maschinen-Kopf: Identität (SSR), FCSM-Status groß (Live über
//         machine:{id}), Schnellaktionen je Rolle (Navigation/Anforderung, keine Aktorik).
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { MachineRead } from "@/lib/api/contracts";
import { machineRoleView } from "@/lib/machine/roles";
import { RealtimeProvider } from "@/lib/realtime/realtime-context";
import { RealtimeStore } from "@/lib/realtime/realtime-store";
import { FakeTransport } from "@/lib/realtime/testing/fake-transport";

import { MachineHeader } from "./machine-header";

const machine: MachineRead = {
  id: 7,
  line_id: 3,
  external_id: "EXT-7",
  label: "CNC-Fräse 7",
  machine_class: "cnc",
  manufacturer: "DMG",
  location: "Halle A",
  created_at: "2026-06-01T00:00:00Z",
};

function renderHeader(role: Parameters<typeof machineRoleView>[0]) {
  const transport = new FakeTransport();
  const store = new RealtimeStore(transport);
  const utils = render(
    <RealtimeProvider store={store}>
      <MachineHeader machine={machine} roleView={machineRoleView(role)} />
    </RealtimeProvider>,
  );
  return { transport, ...utils };
}

describe("MachineHeader", () => {
  it("zeigt die Identität und für den Schichtleiter die Vorhersage-Anforderung", () => {
    renderHeader("shift_lead");
    expect(screen.getByRole("heading", { name: /CNC-Fräse 7/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Vorhersage/ })).toBeInTheDocument();
  });

  it("Werker: kein Vorhersage-Trigger im Kopf", () => {
    renderHeader("worker");
    expect(screen.queryByRole("link", { name: /Vorhersage/ })).toBeNull();
  });

  it("zeigt den FCSM-Status groß, sobald das Live-Aggregat eintrifft", async () => {
    const { transport } = renderHeader("shift_lead");
    transport.emit("machine:7", {
      id: 7,
      label: "CNC-Fräse 7",
      line_id: 3,
      machine_class: "cnc",
      status: "drift_active",
      open_alarm_count: 1,
      open_by_severity: { warning: 1 },
      last_alarm_at: "2026-06-17T10:30:00Z",
    });
    expect(await screen.findByText(/Abweichung erkannt/)).toBeInTheDocument();
  });
});
