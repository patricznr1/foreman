// ============================================================
//  FOREMAN Frontend — components/machine/machine-detail-view.test.tsx
//  Zweck: Sichert die Orchestrierung + den Rollen-Split (ohne bedingte Hooks):
//         voller Aufbau (Kopf/Trend/Stammdaten/Historie/Alarme) und Rollen-Gating
//         der Schnellaktionen (Werker: Notiz, kein Trigger; Schichtleiter: Vorhersage).
// ============================================================
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
    // Seit dem 02.09.2026 ein SCHALTER, kein Verweis: Die Vorhersage wird in
    // der Maschinensicht eingeblendet statt weggeführt.
    expect(screen.queryByRole("button", { name: /Vorhersage/ })).toBeNull();
  });

  it("Schichtleiter: Vorhersage-Anforderung vorhanden", () => {
    mockFetch();
    renderDetail("shift_lead");
    expect(screen.getByRole("button", { name: /Vorhersage/ })).toBeInTheDocument();
  });

  // ──────────────────────────────────────────────────────────────────
  //  Eingeblendet statt weggeführt (02.09.2026)
  // ──────────────────────────────────────────────────────────────────

  it("Vorhersage öffnet IN der Maschine — der Sensortrend bleibt daneben", async () => {
    // DAS IST DER GANZE PUNKT. Ein Test, der nur das Erscheinen der Vorhersage
    // prüft, bliebe auch dann grün, wenn die Sicht dabei weggesprungen wäre.
    // Geprüft wird deshalb BEIDES: die Vorhersage ist da UND die Maschinensicht
    // steht noch.
    mockFetch();
    renderDetail("shift_lead");
    expect(screen.queryByRole("region", { name: /Ausfallvorhersage/ })).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Vorhersage" }));

    expect(screen.getByRole("region", { name: /Ausfallvorhersage/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sensortrend" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /CNC-Fräse 7/ })).toBeInTheDocument();
  });

  it("Ereigniskette öffnet IN der Maschine — der Sensortrend bleibt daneben", async () => {
    mockFetch();
    renderDetail("shift_lead");
    await userEvent.click(screen.getByRole("button", { name: /Ereigniskette/ }));

    expect(
      screen.getByRole("region", { name: "Ereignisketten dieser Maschine" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Sensortrend" })).toBeInTheDocument();
  });

  it("derselbe Schalter schließt wieder", async () => {
    // Ohne das gäbe es keinen Weg zurück zur ungeteilten Sicht ausser über das
    // Neuladen der Seite.
    mockFetch();
    renderDetail("shift_lead");
    await userEvent.click(screen.getByRole("button", { name: "Vorhersage" }));
    expect(screen.getByRole("region", { name: /Ausfallvorhersage/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Vorhersage ausblenden" }));
    expect(screen.queryByRole("region", { name: /Ausfallvorhersage/ })).toBeNull();
  });

  it("immer nur EINE Einblendung — die zweite verdrängt die erste", async () => {
    // Zwei gleichzeitig offene Bereiche schöben den Sensorverlauf aus dem Bild,
    // und genau den will man beim Beurteilen daneben haben.
    mockFetch();
    renderDetail("shift_lead");
    await userEvent.click(screen.getByRole("button", { name: "Vorhersage" }));
    await userEvent.click(screen.getByRole("button", { name: /Ereigniskette/ }));

    expect(
      screen.getByRole("region", { name: "Ereignisketten dieser Maschine" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: /Ausfallvorhersage/ })).toBeNull();
  });

  it("Werker ohne Vorhersage-Recht kann die Ereigniskette trotzdem öffnen", async () => {
    // AUFBAU-KONTROLLE zum Gating: Es sperrt genau eine der beiden Einblendungen,
    // nicht die Einblendung als solche.
    mockFetch();
    renderDetail("worker");
    expect(screen.queryByRole("button", { name: /Vorhersage/ })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /Ereigniskette/ }));
    expect(
      screen.getByRole("region", { name: "Ereignisketten dieser Maschine" }),
    ).toBeInTheDocument();
  });
});
