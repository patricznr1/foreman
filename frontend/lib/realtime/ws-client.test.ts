// ============================================================
//  FOREMAN Frontend — lib/realtime/ws-client.test.ts
//  Zweck: WebSocketTransport gegen den REALEN Vertrag — subscribe/unsubscribe-
//         Nachrichten, Update-Dispatch, Reconnect→Snapshot-Reload (Re-Subscribe),
//         Close 4401 ohne Reconnect, und „kein Token → ruhig geschlossen".
//  Architektur-Einordnung: Quality-Gate (Akzeptanzkriterium WS-Client).
// ============================================================
import { describe, expect, it } from "vitest";
import { FakeWebSocket } from "./testing/fake-websocket";
import { WebSocketTransport } from "./ws-client";

function setup(options: { token?: string | null } = {}) {
  const sockets: FakeWebSocket[] = [];
  let scheduled: (() => void) | null = null;
  const transport = new WebSocketTransport({
    url: "ws://test/api/v1/ws",
    getToken: async () => ("token" in options ? options.token! : "tok"),
    createSocket: () => {
      const socket = new FakeWebSocket();
      sockets.push(socket);
      return socket;
    },
    setTimeoutFn: (fn) => {
      scheduled = fn;
      return 1;
    },
    clearTimeoutFn: () => {
      scheduled = null;
    },
  });
  return {
    transport,
    sockets,
    runScheduled: () => {
      const fn = scheduled;
      scheduled = null;
      fn?.();
    },
  };
}

/** Lässt awaitete Microtasks (getToken-Promise) durchlaufen. */
const flush = async (): Promise<void> => {
  await Promise.resolve();
  await Promise.resolve();
};

describe("WebSocketTransport — realer WS-Vertrag", () => {
  it("nach Connect+Open: subscribe sendet {action:subscribe,topic}", async () => {
    const { transport, sockets } = setup();
    transport.subscribe("overview", () => {});
    transport.connect();
    await flush();
    const ws = sockets[0]!;
    ws.triggerOpen();
    expect(ws.sentMessages()).toContainEqual({ action: "subscribe", topic: "overview" });
  });

  it("dispatcht Server-Updates an den Themen-Handler", async () => {
    const { transport, sockets } = setup();
    const received: unknown[] = [];
    transport.subscribe("overview", (data) => {
      received.push(data);
    });
    transport.connect();
    await flush();
    const ws = sockets[0]!;
    ws.triggerOpen();
    ws.triggerMessage(JSON.stringify({ type: "update", topic: "overview", data: { total: 3 } }));
    expect(received).toEqual([{ total: 3 }]);
  });

  it("Reconnect re-abonniert alle Themen (Snapshot-Reload)", async () => {
    const { transport, sockets, runScheduled } = setup();
    transport.subscribe("overview", () => {});
    transport.connect();
    await flush();
    sockets[0]!.triggerOpen();
    sockets[0]!.triggerServerClose(1006); // abnormaler Abbruch → Reconnect geplant
    expect(transport.getStatus()).toBe("reconnecting");

    runScheduled();
    await flush();
    const ws2 = sockets[1]!;
    ws2.triggerOpen();
    expect(ws2.sentMessages()).toContainEqual({ action: "subscribe", topic: "overview" });
  });

  it("Close 4401 → kein Reconnect, Themen-Fehler 'unauthorized'", async () => {
    const { transport, sockets } = setup();
    const errors: string[] = [];
    transport.subscribe(
      "overview",
      () => {},
      (reason) => {
        errors.push(reason);
      },
    );
    transport.connect();
    await flush();
    const ws = sockets[0]!;
    ws.triggerOpen();
    ws.triggerServerClose(4401);

    expect(errors).toContain("unauthorized");
    expect(transport.getStatus()).toBe("closed");
    expect(sockets).toHaveLength(1); // kein neuer Socket
  });

  it("letzte Abmeldung sendet {action:unsubscribe}", async () => {
    const { transport, sockets } = setup();
    const off = transport.subscribe("overview", () => {});
    transport.connect();
    await flush();
    const ws = sockets[0]!;
    ws.triggerOpen();
    off();
    expect(ws.sentMessages()).toContainEqual({ action: "unsubscribe", topic: "overview" });
  });

  it("ohne Token: ruhig geschlossen, kein Socket", async () => {
    const { transport, sockets } = setup({ token: null });
    transport.connect();
    await flush();
    expect(sockets).toHaveLength(0);
    expect(transport.getStatus()).toBe("closed");
  });
});
