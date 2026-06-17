// ============================================================
//  FOREMAN Frontend — lib/machine/history.test.ts
//  Zweck: Sichert die vereinte, chronologische Maschinen-Historie (Wartung + Notizen)
//         mit PII-Maskierung — kein Klartext-Akteur, maskierter Notiztext bleibt.
// ============================================================
import { describe, expect, it } from "vitest";

import type { MaintenanceEventRead, WorkerNoteRead } from "@/lib/api/contracts";

import { buildHistory } from "./history";

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

describe("buildHistory", () => {
  it("vereint Wartung + Notizen, jüngste zuerst", () => {
    const items = buildHistory([event], [note]);
    expect(items.map((i) => i.kind)).toEqual(["note", "maintenance"]);
  });

  it("Wartung: Typ als Titel, Beschreibung als Text (Sachtext, unmaskiert), Akteur #hex6", () => {
    const [item] = buildHistory([event], []);
    expect(item?.kind).toBe("maintenance");
    expect(item?.title).toBe("Inspektion");
    expect(item?.body).toBe("Lager geprüft, io");
    expect(item?.actorMasked).toBe("#abcdef");
  });

  it("Notiz: maskierter Text bleibt, Akteur als #hex6, kein Klartext-Token", () => {
    const [item] = buildHistory([], [note]);
    expect(item?.kind).toBe("note");
    expect(item?.body).toBe("[PERSON] meldet Geräusch an der Spindel");
    expect(item?.shift).toBe("Frühschicht");
    expect(item?.actorMasked).toBe("#fedcba");
    expect(JSON.stringify(item)).not.toContain("v1:");
  });

  it("leere Eingabe → leere Historie", () => {
    expect(buildHistory([], [])).toEqual([]);
  });
});
