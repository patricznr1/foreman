// ============================================================
//  FOREMAN Frontend — components/machine/machine-history.test.tsx
//  Zweck: Integrationstest der Maschinen-Historie — Wartung + Notizen vereint,
//         chronologisch, PII maskiert (#hex6, NIE Klartext-Token).
// ============================================================
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { MaintenanceEventRead, WorkerNoteRead } from "@/lib/api/contracts";

import { MachineHistory } from "./machine-history";

const event: MaintenanceEventRead = {
  id: 1,
  machine_id: 7,
  component_id: null,
  type: "Inspektion",
  performed_at: "2026-06-17T08:00:00Z",
  description: "Lager geprüft, io",
  performed_by: "v1:abcdef1234567890",
  created_at: "2026-06-17T08:05:00Z",
};

const note: WorkerNoteRead = {
  id: 2,
  machine_id: 7,
  shift: "Frühschicht",
  text: "[PERSON] meldet Geräusch an der Spindel",
  classification: null,
  author: "v1:fedcba0987654321",
  created_at: "2026-06-17T09:00:00Z",
};

function mockFetch() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      const body = url.includes("maintenance_events") ? [event] : url.includes("worker_notes") ? [note] : [];
      return Promise.resolve({ ok: true, json: async () => body });
    }),
  );
}

describe("MachineHistory", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("zeigt Wartung + Notizen, PII maskiert (#hex6, kein Klartext-Token)", async () => {
    mockFetch();
    render(<MachineHistory machineId={7} />);
    expect(await screen.findByText("Inspektion")).toBeInTheDocument();
    expect(screen.getByText(/PERSON/)).toBeInTheDocument();
    expect(screen.getByText(/#abcdef/)).toBeInTheDocument();
    expect(screen.queryByText(/v1:/)).toBeNull();
  });
});
