// ============================================================
//  FOREMAN Frontend — lib/realtime/realtime-store.test.ts
//  Zweck: Stream-Ebene — Ref-Counting der Abos, Drosselung/Coalescing von Bursts
//         (Backpressure → Anzeigeauflösung), stabile Snapshot-Referenz für
//         useSyncExternalStore, Statuswechsel-Propagation und Cache-Erhalt bei
//         Fehler. Beweist die Transport-Entkopplung gegen den FakeTransport.
//  Architektur-Einordnung: Quality-Gate (Akzeptanzkriterium Echtzeit-Schicht).
// ============================================================
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RealtimeStore } from "./realtime-store";
import { FakeTransport } from "./testing/fake-transport";

describe("RealtimeStore — Stream-Ebene", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  it("Abo/Abmeldung steuert das Transport-Abo (Ref-Counting)", () => {
    const transport = new FakeTransport();
    const store = new RealtimeStore(transport);
    store.connect();

    const off1 = store.subscribeTopic("overview", () => {});
    expect(transport.hasTopic("overview")).toBe(true);
    const off2 = store.subscribeTopic("overview", () => {});

    off1();
    expect(transport.hasTopic("overview")).toBe(true); // noch ein Listener
    off2();
    expect(transport.hasTopic("overview")).toBe(false); // letzter weg → Transport-Abo zu
  });

  it("drosselt Bursts auf EINEN Flush und behält den letzten Wert", () => {
    const transport = new FakeTransport();
    const store = new RealtimeStore(transport, { throttleMs: 100 });
    store.connect();

    let notifications = 0;
    store.subscribeTopic("overview", () => {
      notifications += 1;
    });

    transport.emit("overview", { n: 1 });
    transport.emit("overview", { n: 2 });
    transport.emit("overview", { n: 3 });
    expect(notifications).toBe(0); // noch im Drosselfenster

    vi.advanceTimersByTime(100);
    expect(notifications).toBe(1); // genau ein Flush
    expect((store.getTopicView("overview").data as { n: number }).n).toBe(3);
    expect(store.getTopicView("overview").loaded).toBe(true);
  });

  it("liefert eine stabile Snapshot-Referenz zwischen Flushes", () => {
    const transport = new FakeTransport();
    const store = new RealtimeStore(transport, { throttleMs: 0 });
    store.connect();
    store.subscribeTopic("overview", () => {});

    transport.emit("overview", { n: 1 });
    const a = store.getTopicView("overview");
    const b = store.getTopicView("overview");
    expect(a).toBe(b); // identische Referenz → kein Endlos-Rerender
  });

  it("Statuswechsel benachrichtigt Themen-Listener (live ↔ gecacht)", () => {
    const transport = new FakeTransport();
    const store = new RealtimeStore(transport, { throttleMs: 0 });
    store.connect();

    let notifications = 0;
    store.subscribeTopic("overview", () => {
      notifications += 1;
    });
    transport.emit("overview", { n: 1 }); // 1. Notify (Daten)
    const before = notifications;

    transport.setStatus("reconnecting");
    expect(notifications).toBe(before + 1); // Statuswechsel → erneute Benachrichtigung
  });

  it("behält den letzten Cache bei Fehler (Degradation leert nicht)", () => {
    const transport = new FakeTransport();
    const store = new RealtimeStore(transport, { throttleMs: 0 });
    store.connect();
    store.subscribeTopic("machine:1", () => {});

    transport.emit("machine:1", { n: 1 });
    transport.emitError("machine:1", "forbidden");

    const stored = store.getTopicView("machine:1");
    expect(stored.error).toBe("forbidden");
    expect((stored.data as { n: number }).n).toBe(1); // Cache bleibt erhalten
  });

  it("ein Fehler bricht einen geplanten Flush ab (kein Overwrite des Fehlerzustands)", () => {
    const transport = new FakeTransport();
    const store = new RealtimeStore(transport, { throttleMs: 100 });
    store.connect();
    store.subscribeTopic("machine:1", () => {});

    transport.emit("machine:1", { n: 1 });
    vi.advanceTimersByTime(100); // erster Wert geflusht → Cache {n:1}

    transport.emit("machine:1", { n: 2 }); // plant einen Flush in 100 ms
    transport.emitError("machine:1", "offline"); // muss den geplanten Flush abbrechen
    vi.advanceTimersByTime(100); // der abgebrochene Flush darf NICHT überschreiben

    const stored = store.getTopicView("machine:1");
    expect(stored.error).toBe("offline");
    expect((stored.data as { n: number }).n).toBe(1); // Cache bleibt, kein n:2, kein null
  });
});
