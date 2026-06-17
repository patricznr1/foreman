// ============================================================
//  FOREMAN Frontend — components/machine/machine-alarms.test.tsx
//  Zweck: Sichert die maschinengefilterte Alarm-Einbettung über die WIEDERVERWENDETE
//         C-AlarmRow (kein dupliziertes Alarm-Rendering); fremde Maschinen-Alarme
//         erscheinen nicht.
// ============================================================
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { AlarmRead } from "@/lib/api/contracts";
import { RealtimeProvider } from "@/lib/realtime/realtime-context";
import { RealtimeStore } from "@/lib/realtime/realtime-store";
import { FakeTransport } from "@/lib/realtime/testing/fake-transport";

import { MachineAlarms } from "./machine-alarms";

function alarm(over: Partial<AlarmRead>): AlarmRead {
  return {
    id: 1,
    machine_id: 7,
    component_id: null,
    data_point_id: null,
    code: null,
    message: "Lager-Temperatur hoch",
    severity: "warning",
    category: "process",
    raised_at: "2026-06-17T10:00:00Z",
    cleared_at: null,
    acknowledged_at: null,
    acknowledged_by: null,
    created_at: "2026-06-17T10:00:00Z",
    ...over,
  };
}

function renderAlarms() {
  const transport = new FakeTransport();
  const store = new RealtimeStore(transport);
  return render(
    <RealtimeProvider store={store}>
      <MachineAlarms machineId={7} machineLabel="CNC-Fräse 7" lineId={3} canAcknowledge />
    </RealtimeProvider>,
  );
}

describe("MachineAlarms", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("zeigt nur die offenen Alarme dieser Maschine (gefiltert, C-AlarmRow)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [alarm({ id: 1, machine_id: 7 }), alarm({ id: 2, machine_id: 99, message: "Fremd-Alarm" })],
      }),
    );
    renderAlarms();
    expect(await screen.findByText(/Lager-Temperatur hoch/)).toBeInTheDocument();
    expect(screen.queryByText(/Fremd-Alarm/)).toBeNull();
  });
});
