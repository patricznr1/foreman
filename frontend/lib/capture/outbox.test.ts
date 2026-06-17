// ============================================================
//  FOREMAN Frontend — lib/capture/outbox.test.ts
//  Zweck: Sichert die Offline-Queue — inkl. des Datenschutz-Hebels
//         „Lösch-nach-Senden" (kein dauerhafter Klartext-PII-Cache, §8).
// ============================================================
import { describe, expect, it } from "vitest";
import {
  OUTBOX_KEY,
  clearOutbox,
  enqueueNote,
  outboxCount,
  readOutbox,
  removeFromOutbox,
  writeOutbox,
} from "./outbox";
import { fakeStorage } from "./testing/fixtures";

const enqueueOpts = (storage: Storage, n: number) => ({
  storage,
  makeId: () => `id-${n}`,
  now: () => "2026-06-17T15:00:00+00:00",
});

describe("enqueueNote / readOutbox", () => {
  it("Happy-Path: puffert eine Notiz und liest sie zurück", () => {
    const storage = fakeStorage();
    const item = enqueueNote({ text: "Lager heiß", machine_id: 12 }, enqueueOpts(storage, 1));
    expect(item.localId).toBe("id-1");
    const queue = readOutbox(storage);
    expect(queue).toHaveLength(1);
    expect(queue[0]?.payload.text).toBe("Lager heiß");
  });

  it("hängt mehrere Notizen FIFO an (Reihenfolge bleibt)", () => {
    const storage = fakeStorage();
    enqueueNote({ text: "erste" }, enqueueOpts(storage, 1));
    enqueueNote({ text: "zweite" }, enqueueOpts(storage, 2));
    expect(readOutbox(storage).map((x) => x.payload.text)).toEqual(["erste", "zweite"]);
  });
});

describe("removeFromOutbox (Datenschutz: Lösch-nach-Senden)", () => {
  it("entfernt genau das gesendete Item — Klartext liegt nicht weiter", () => {
    const storage = fakeStorage();
    enqueueNote({ text: "behalten" }, enqueueOpts(storage, 1));
    enqueueNote({ text: "senden" }, enqueueOpts(storage, 2));
    const rest = removeFromOutbox("id-2", storage);
    expect(rest.map((x) => x.payload.text)).toEqual(["behalten"]);
    expect(readOutbox(storage)).toHaveLength(1);
  });

  it("räumt den Storage-Key vollständig ab, wenn die Queue leer wird", () => {
    const storage = fakeStorage();
    enqueueNote({ text: "letzte" }, enqueueOpts(storage, 1));
    removeFromOutbox("id-1", storage);
    expect(storage.getItem(OUTBOX_KEY)).toBeNull();
    expect(outboxCount(storage)).toBe(0);
  });
});

describe("Robustheit", () => {
  it("liefert eine leere Queue bei fehlendem oder kaputtem Speicher (nie throw)", () => {
    expect(readOutbox(null)).toEqual([]);
    const storage = fakeStorage();
    storage.setItem(OUTBOX_KEY, "kein-json{");
    expect(readOutbox(storage)).toEqual([]);
  });

  it("verwirft strukturell ungültige Einträge (z. B. ohne payload.text)", () => {
    const storage = fakeStorage();
    storage.setItem(OUTBOX_KEY, JSON.stringify([{ localId: "x", enqueuedAt: "t" }, { foo: 1 }]));
    expect(readOutbox(storage)).toEqual([]);
  });

  it("clearOutbox leert die gesamte Queue", () => {
    const storage = fakeStorage();
    enqueueNote({ text: "a" }, enqueueOpts(storage, 1));
    clearOutbox(storage);
    expect(outboxCount(storage)).toBe(0);
  });

  it("writeOutbox mit leerer Liste entfernt den Key (kein leeres Array-Artefakt)", () => {
    const storage = fakeStorage();
    writeOutbox([], storage);
    expect(storage.getItem(OUTBOX_KEY)).toBeNull();
  });
});
