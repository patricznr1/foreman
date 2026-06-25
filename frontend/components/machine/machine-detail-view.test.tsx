// ============================================================
//  FOREMAN Frontend — components/machine/machine-detail-view.test.tsx
//  Zweck: Sichert die Orchestrierung + den Rollen-Split (ohne bedingte Hooks):
//         voller Aufbau (Kopf/Trend/Stammdaten/Historie/Alarme) und Rollen-Gating
//         der Schnellaktionen (Werker: Notiz, kein Trigger; Schichtleiter: Vorhersage).
// ============================================================
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type {
  CurrentUser,
  DataPointRead,
  MachineCardOut,
  MachineRead,
  MachineTrendOut,
  Role,
} from "@/lib/api/contracts";
import { makeMachineCard } from "@/lib/machine/testing/card-fixture";
import { RealtimeProvider } from "@/lib/realtime/realtime-context";
import { RealtimeStore } from "@/lib/realtime/realtime-store";
import { FakeTransport } from "@/lib/realtime/testing/fake-transport";

import { MachineDetailView } from "./machine-detail-view";

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

const dataPoints: DataPointRead[] = [
  {
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
  },
];

const card: MachineCardOut = makeMachineCard({
  id: 7,
  label: "CNC-Fräse 7",
  line_id: 3,
  machine_class: "cnc",
  manufacturer: "DMG",
  external_id: "EXT-7",
  location: "Halle A",
  components: [{ id: 1, label: "Spindel", component_type: "spindle" }],
  data_points: [
    {
      id: 42,
      component_id: null,
      name: "spindle_temp",
      kind: "analog",
      measurement_type: "temperature",
      unit: "°C",
      normal_min: 10,
      normal_max: 20,
      last_value: 15,
      last_value_at: "2026-06-17T10:00:00Z",
      status: "ok",
    },
  ],
  stream: { active: true, last_reading_at: "2026-06-17T10:00:00Z" },
});

const trendData: MachineTrendOut = {
  machine_id: 7,
  data_point_id: 42,
  data_point_name: "spindle_temp",
  unit: "°C",
  measurement_type: "temperature",
  normal_min: 10,
  normal_max: 20,
  truncated: false,
  profile_band: null,
  points: [{ bucket: "2026-06-17T10:00:00Z", avg: 15, min: 14, max: 16, last: 15 }],
};

function mockFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (url.includes("/trend")) {
        return Promise.resolve({ ok: true, json: async () => trendData });
      }
      return Promise.resolve({ ok: true, json: async () => [] });
    }),
  );
}

function renderDetail(role: Role) {
  const user: CurrentUser = {
    id: 1,
    email: "u@example.com",
    role,
    assigned_line_ids: [3],
    assigned_machine_ids: [7],
  };
  const store = new RealtimeStore(new FakeTransport());
  return render(
    <RealtimeProvider store={store}>
      <MachineDetailView user={user} machine={machine} dataPoints={dataPoints} card={card} />
    </RealtimeProvider>,
  );
}

describe("MachineDetailView", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("Werker: voller Aufbau, Notiz-Aktion, kein Vorhersage-Trigger", () => {
    mockFetch();
    renderDetail("worker");
    expect(screen.getByRole("heading", { name: /CNC-Fräse 7/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sensortrend" })).toBeInTheDocument();
    // Die lebende Maschinenkarte trägt die Stammdaten-Sicht (ersetzt machine-specs).
    expect(screen.getByRole("region", { name: "Maschinenkarte CNC-Fräse 7" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Historie" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Offene Alarme" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Notiz/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Vorhersage/ })).toBeNull();
  });

  it("Schichtleiter: Vorhersage-Anforderung vorhanden", () => {
    mockFetch();
    renderDetail("shift_lead");
    expect(screen.getByRole("link", { name: /Vorhersage/ })).toBeInTheDocument();
  });
});
