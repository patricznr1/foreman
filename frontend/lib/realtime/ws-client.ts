// ============================================================
//  FOREMAN Frontend — lib/realtime/ws-client.ts
//  Zweck: WebSocketTransport — der gemultiplexte Live-Client gegen /api/v1/ws.
//         Spricht den REALEN Vertrag: Client {action: subscribe|unsubscribe, topic},
//         Server {type: update|error, topic, data|reason}. Themen-Abos mit
//         Ref-Counting, Reconnect mit Backoff, und nach (Re)Connect ein erneutes
//         subscribe je aktivem Thema → der Server schickt frische Snapshots
//         (Reconnect→Snapshot-Reload). Close 4401 = Auth ungültig → kein Reconnect.
//  Architektur-Einordnung: Transport-Ebene (Schicht 1). Kennt KEINE Visualisierung.
// ============================================================
import {
  type ConnectionStatus,
  type StatusListener,
  type TopicErrorHandler,
  type TopicHandler,
  type Transport,
} from "./transport";
import { WS_UNAUTHORIZED_CLOSE, type WsClientMessage, type WsServerMessage } from "../api/contracts";

/** Minimaler WebSocket-Ausschnitt — injizierbar für Tests (FakeWebSocket). */
export interface WebSocketLike {
  send(data: string): void;
  close(code?: number, reason?: string): void;
  readyState: number;
  onopen: (() => void) | null;
  onclose: ((event: { code: number; reason: string }) => void) | null;
  onmessage: ((event: { data: unknown }) => void) | null;
  onerror: (() => void) | null;
}

const WS_OPEN = 1;
const NORMAL_CLOSE = 1000;

export interface WebSocketTransportOptions {
  /** Basis-URL des WS-Endpoints (ohne Token), z. B. ws://host/api/v1/ws. */
  url: string;
  /** Liefert das kurzlebige WS-Ticket (JWT) just-in-time für den ?token=-Query. */
  getToken: () => Promise<string | null>;
  /** Socket-Fabrik (Default: globaler WebSocket). Injizierbar für Tests. */
  createSocket?: (url: string) => WebSocketLike;
  reconnectBaseMs?: number;
  reconnectMaxMs?: number;
  setTimeoutFn?: (fn: () => void, ms: number) => number;
  clearTimeoutFn?: (handle: number) => void;
}

interface TopicEntry {
  handlers: Set<TopicHandler>;
  errorHandlers: Set<TopicErrorHandler>;
}

export class WebSocketTransport implements Transport {
  private readonly options: Required<
    Omit<WebSocketTransportOptions, "createSocket" | "getToken" | "url">
  > &
    Pick<WebSocketTransportOptions, "createSocket" | "getToken" | "url">;
  private socket: WebSocketLike | null = null;
  private status: ConnectionStatus = "closed";
  private intentionalClose = false;
  private reconnectAttempts = 0;
  private reconnectHandle: number | null = null;
  private readonly topics = new Map<string, TopicEntry>();
  private readonly statusListeners = new Set<StatusListener>();

  constructor(options: WebSocketTransportOptions) {
    this.options = {
      reconnectBaseMs: 500,
      reconnectMaxMs: 10_000,
      setTimeoutFn: (fn, ms) => globalThis.setTimeout(fn, ms) as unknown as number,
      clearTimeoutFn: (handle) => globalThis.clearTimeout(handle),
      ...options,
    };
  }

  connect(): void {
    if (this.socket !== null || this.status === "connecting") {
      return;
    }
    this.intentionalClose = false;
    this.setStatus("connecting");
    void this.open();
  }

  close(): void {
    this.intentionalClose = true;
    if (this.reconnectHandle !== null) {
      this.options.clearTimeoutFn?.(this.reconnectHandle);
      this.reconnectHandle = null;
    }
    if (this.socket !== null) {
      this.socket.close(NORMAL_CLOSE, "client closed");
      this.socket = null;
    }
    this.setStatus("closed");
  }

  getStatus(): ConnectionStatus {
    return this.status;
  }

  onStatus(listener: StatusListener): () => void {
    this.statusListeners.add(listener);
    return () => {
      this.statusListeners.delete(listener);
    };
  }

  subscribe(topic: string, onMessage: TopicHandler, onError?: TopicErrorHandler): () => void {
    let entry = this.topics.get(topic);
    const isNewTopic = entry === undefined;
    if (entry === undefined) {
      entry = { handlers: new Set(), errorHandlers: new Set() };
      this.topics.set(topic, entry);
    }
    entry.handlers.add(onMessage);
    if (onError) {
      entry.errorHandlers.add(onError);
    }
    // Erstes Abo dieses Themas → dem Server mitteilen (er antwortet mit Snapshot).
    if (isNewTopic) {
      this.send({ action: "subscribe", topic });
    }

    return () => {
      const current = this.topics.get(topic);
      if (current === undefined) {
        return;
      }
      current.handlers.delete(onMessage);
      if (onError) {
        current.errorHandlers.delete(onError);
      }
      if (current.handlers.size === 0) {
        this.topics.delete(topic);
        this.send({ action: "unsubscribe", topic });
      }
    };
  }

  // — intern —

  private async open(): Promise<void> {
    let token: string | null;
    try {
      token = await this.options.getToken();
    } catch {
      token = null;
    }
    if (this.intentionalClose) {
      return;
    }
    if (token === null) {
      // Kein Ticket → keine Verbindung (z. B. nicht angemeldet). Ruhig schließen.
      this.setStatus("closed");
      return;
    }
    const url = `${this.options.url}?token=${encodeURIComponent(token)}`;
    const socket = this.makeSocket(url);
    this.socket = socket;

    socket.onopen = () => {
      this.reconnectAttempts = 0;
      this.setStatus("open");
      // Reconnect→Snapshot-Reload: alle aktiven Themen erneut abonnieren.
      for (const topic of this.topics.keys()) {
        this.sendVia(socket, { action: "subscribe", topic });
      }
    };

    socket.onmessage = (event) => {
      this.handleMessage(event.data);
    };

    socket.onclose = (event) => {
      this.socket = null;
      if (this.intentionalClose) {
        this.setStatus("closed");
        return;
      }
      if (event.code === WS_UNAUTHORIZED_CLOSE) {
        // Auth ungültig — kein Reconnect (Schleife sinnlos). Themen informieren.
        this.setStatus("closed");
        for (const entry of this.topics.values()) {
          for (const handler of entry.errorHandlers) {
            handler("unauthorized");
          }
        }
        return;
      }
      this.setStatus("reconnecting");
      this.scheduleReconnect();
    };

    socket.onerror = () => {
      // onclose folgt und steuert den Reconnect.
    };
  }

  private makeSocket(url: string): WebSocketLike {
    if (this.options.createSocket) {
      return this.options.createSocket(url);
    }
    if (typeof WebSocket === "undefined") {
      throw new Error("WebSocket nicht verfügbar — createSocket injizieren.");
    }
    return new WebSocket(url) as unknown as WebSocketLike;
  }

  private handleMessage(raw: unknown): void {
    if (typeof raw !== "string") {
      return;
    }
    let message: WsServerMessage;
    try {
      message = JSON.parse(raw) as WsServerMessage;
    } catch {
      return;
    }
    const entry = this.topics.get(message.topic);
    if (entry === undefined) {
      return;
    }
    if (message.type === "error") {
      for (const handler of entry.errorHandlers) {
        handler(message.reason ?? "error");
      }
      return;
    }
    for (const handler of entry.handlers) {
      handler(message.data);
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectHandle !== null || this.intentionalClose) {
      return;
    }
    const backoff = Math.min(
      this.options.reconnectBaseMs * 2 ** this.reconnectAttempts,
      this.options.reconnectMaxMs,
    );
    this.reconnectAttempts += 1;
    const schedule = this.options.setTimeoutFn;
    this.reconnectHandle = schedule(() => {
      this.reconnectHandle = null;
      if (!this.intentionalClose) {
        void this.open();
      }
    }, backoff);
  }

  private send(message: WsClientMessage): void {
    if (this.socket !== null && this.socket.readyState === WS_OPEN) {
      this.sendVia(this.socket, message);
    }
  }

  private sendVia(socket: WebSocketLike, message: WsClientMessage): void {
    socket.send(JSON.stringify(message));
  }

  private setStatus(status: ConnectionStatus): void {
    if (this.status === status) {
      return;
    }
    this.status = status;
    for (const listener of this.statusListeners) {
      listener(status);
    }
  }
}
