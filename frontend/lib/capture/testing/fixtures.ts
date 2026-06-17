// ============================================================
//  FOREMAN Frontend — lib/capture/testing/fixtures.ts
//  Zweck: Test-Fixtures der Erfassung. Bauen gegen den REALEN Vertrag
//         (contracts.ts: MachineRead/CurrentUser) und die J-View-Typen.
//  Architektur-Einordnung: Test-Hilfe (nur Tests).
// ============================================================
import type { CurrentUser, MachineRead } from "@/lib/api/contracts";
import type { CaptureDraft } from "../types";

let machineSeq = 0;

export function makeMachine(overrides: Partial<MachineRead> = {}): MachineRead {
  machineSeq += 1;
  return {
    id: machineSeq,
    line_id: 1,
    external_id: null,
    label: `CNC ${machineSeq}`,
    machine_class: "cnc",
    manufacturer: "ACME",
    location: "Halle 1",
    created_at: "2026-06-01T00:00:00+00:00",
    ...overrides,
  };
}

export function makeUser(overrides: Partial<CurrentUser> = {}): CurrentUser {
  return {
    id: 1,
    email: "werker@example.com",
    role: "worker",
    assigned_line_ids: [],
    assigned_machine_ids: [],
    ...overrides,
  };
}

export function makeDraft(overrides: Partial<CaptureDraft> = {}): CaptureDraft {
  return {
    text: "Lager läuft heiß nach Schichtwechsel.",
    machineId: null,
    shift: null,
    classification: null,
    ...overrides,
  };
}

/** Einfaches In-Memory-Storage-Double (Storage-Interface) für Outbox-Tests. */
export function fakeStorage(): Storage {
  const map = new Map<string, string>();
  return {
    get length() {
      return map.size;
    },
    clear: () => map.clear(),
    getItem: (key: string) => map.get(key) ?? null,
    key: (index: number) => Array.from(map.keys())[index] ?? null,
    removeItem: (key: string) => {
      map.delete(key);
    },
    setItem: (key: string, value: string) => {
      map.set(key, value);
    },
  };
}
