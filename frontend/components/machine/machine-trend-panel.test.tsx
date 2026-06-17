// ============================================================
//  FOREMAN Frontend — components/machine/machine-trend-panel.test.tsx
//  Zweck: Integrationstest des Trend-Panels — historischer Pull (gemockter fetch) +
//         Live-WS (FakeTransport) zu einer Reihe verschmolzen, in der Fuenf-Zustaende-
//         Huelle. Transport-agnostisch: Chart liest nur den abgeleiteten State.
// ============================================================
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DataPointRead, MachineTrendOut } from "@/lib/api/contracts";
import { RealtimeProvider } from "@/lib/realtime/realtime-context";
import { RealtimeStore } from "@/lib/realtime/realtime-store";
import { FakeTransport } from "@/lib/realtime/testing/fake-transport";

import { MachineTrendPanel } from "./machine-trend-panel";

const NOW = Date.parse("2026-06-17T11:00:00Z");

const dataPoint: DataPointRead = {
  id: 42,
  machine_id: 7,
  component_id: null,
  name: "spindle_temp",
  kind: "analog",
  measurement_type: "temperature",
  unit: "°C",
  source: "simulation",
  address: null,
  normal_min: 10,
  normal_max: 20,
  created_at: "2026-06-01T00:00:00Z",
};

const historical: MachineTrendOut = {
  machine_id: 7,
  data_point_id: 42,
  data_point_name: "spindle_temp",
  unit: "°C",
  measurement_type: "temperature",
  normal_min: 10,
  normal_max: 20,
  truncated: false,
  profile_band: null,
  points: [
    { bucket: "2026-06-17T10:00:00Z", avg: 15, min: 14, max: 16, last: 15 },
    { bucket: "2026-06-17T10:30:00Z", avg: 16, min: 15, max: 17, last: 16 },
  ],
};

function renderPanel() {
  const transport = new FakeTransport();
  const store = new RealtimeStore(transport);
  return render(
    <RealtimeProvider store={store}>
      <MachineTrendPanel machineId={7} dataPoint={dataPoint} hours={24} nowMs={NOW} />
    </RealtimeProvider>,
  );
}

describe("MachineTrendPanel", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("lädt den historischen Trend und zeigt den Sensor-Chart", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => historical }),
    );
    renderPanel();
    const chart = await screen.findByRole("img");
    expect(chart.getAttribute("aria-label")).toContain("spindle_temp");
  });

  it("zeigt den Fehler-Zustand bei 403 ohne Live-Daten (kein weißer Schirm)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 403 }));
    renderPanel();
    expect(await screen.findByRole("alert")).toBeInTheDocument();
  });
});
