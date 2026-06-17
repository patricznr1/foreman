// ============================================================
//  FOREMAN Frontend — lib/realtime/realtime-context.tsx
//  Zweck: React-Anbindung der Echtzeit-Schicht. RealtimeProvider stellt EINEN
//         gemultiplexten Store bereit (verbindet beim Mount, schließt beim
//         Unmount). Tests injizieren einen Store mit FakeTransport — die
//         Visualisierung bleibt transport-agnostisch (§5.1).
//  Architektur-Einordnung: State-Anbindung (Schicht 1 ↔ React).
// ============================================================
"use client";

import { type ReactNode, createContext, useContext, useEffect, useMemo } from "react";
import { RealtimeStore } from "./realtime-store";
import { WebSocketTransport } from "./ws-client";

const RealtimeContext = createContext<RealtimeStore | null>(null);

/**
 * WS-Basis-URL. EMPFOHLEN: `NEXT_PUBLIC_FOREMAN_WS_URL` direkt auf den Backend-WS
 * setzen (z. B. ws://host:8000/api/v1/ws) — der ?token=-Query trägt die Auth.
 * Der same-origin-Fallback funktioniert NUR, wenn am Frontend-Origin ein
 * WS-Reverse-Proxy auf den Backend-WS liegt; der HTTP-BFF-Proxy reicht KEIN
 * WebSocket-Upgrade weiter (Review-Hinweis). Ohne Konfiguration bleibt die Sicht
 * auf dem HTTP-Snapshot (als „gecacht"), ohne Live-Strom.
 */
function defaultWsUrl(): string {
  const override = process.env.NEXT_PUBLIC_FOREMAN_WS_URL;
  if (override) {
    return override;
  }
  if (typeof window === "undefined") {
    return "";
  }
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}/api/v1/ws`;
}

/** Holt das kurzlebige WS-Ticket just-in-time (BFF → Backend GET /api/v1/ws-ticket). */
async function fetchWsTicket(): Promise<string | null> {
  try {
    const response = await fetch("/api/ws-ticket", { credentials: "same-origin" });
    if (!response.ok) {
      return null;
    }
    const body = (await response.json()) as { token?: string };
    return body.token ?? null;
  } catch {
    return null;
  }
}

export function createDefaultStore(): RealtimeStore {
  const transport = new WebSocketTransport({ url: defaultWsUrl(), getToken: fetchWsTicket });
  return new RealtimeStore(transport);
}

export interface RealtimeProviderProps {
  /** Optionaler Store (Tests injizieren einen mit FakeTransport). */
  store?: RealtimeStore;
  children: ReactNode;
}

export function RealtimeProvider({ store, children }: RealtimeProviderProps) {
  const realtimeStore = useMemo(() => store ?? createDefaultStore(), [store]);

  useEffect(() => {
    realtimeStore.connect();
    return () => {
      realtimeStore.close();
    };
  }, [realtimeStore]);

  return <RealtimeContext.Provider value={realtimeStore}>{children}</RealtimeContext.Provider>;
}

export function useRealtimeStore(): RealtimeStore {
  const store = useContext(RealtimeContext);
  if (store === null) {
    throw new Error("useRealtimeStore muss innerhalb von <RealtimeProvider> verwendet werden.");
  }
  return store;
}
