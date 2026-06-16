// ============================================================
//  FOREMAN Frontend — lib/realtime/realtime-store.ts
//  Zweck: Die STREAM-STATE-Ebene (Studie §5.1, Ebene 1 von 3): eingehende
//         Live-Daten je Thema, gepuffert + gedrosselt (client-seitige
//         Backpressure → Anzeigeauflösung, kein Rerender pro Sekunde). Bietet das
//         externe-Store-Protokoll (subscribe/getSnapshot) für useSyncExternalStore.
//         Komponenten lesen NUR die abgeleitete Ebene — sie kennen den Transport nie.
//  Architektur-Einordnung: State-Ebene 1 (Stream). Transport-agnostisch (nimmt
//         eine beliebige Transport-Implementierung).
// ============================================================
import type { ConnectionStatus, StatusListener, Transport } from "./transport";

/** Stabiler View je Thema (Referenz ändert sich nur bei echter Änderung). */
export interface TopicView {
  data: unknown;
  error: string | null;
  loaded: boolean;
}

const INITIAL_VIEW: TopicView = Object.freeze({ data: undefined, error: null, loaded: false });

interface TopicState {
  listeners: Set<() => void>;
  transportUnsub: (() => void) | null;
  view: TopicView;
  pending: unknown;
  hasPending: boolean;
  flushHandle: number | null;
}

export interface RealtimeStoreOptions {
  /** Drosselfenster (ms): Bursts werden auf einen Flush je Fenster gebündelt. */
  throttleMs?: number;
  setTimeoutFn?: (fn: () => void, ms: number) => number;
  clearTimeoutFn?: (handle: number) => void;
}

export class RealtimeStore {
  private readonly transport: Transport;
  private readonly throttleMs: number;
  private readonly setTimeoutFn: (fn: () => void, ms: number) => number;
  private readonly clearTimeoutFn: (handle: number) => void;
  private readonly topics = new Map<string, TopicState>();
  private readonly statusListeners = new Set<StatusListener>();
  private transportStatusUnsub: (() => void) | null = null;

  constructor(transport: Transport, options: RealtimeStoreOptions = {}) {
    this.transport = transport;
    this.throttleMs = options.throttleMs ?? 100;
    this.setTimeoutFn =
      options.setTimeoutFn ?? ((fn, ms) => globalThis.setTimeout(fn, ms) as unknown as number);
    this.clearTimeoutFn = options.clearTimeoutFn ?? ((handle) => globalThis.clearTimeout(handle));
  }

  connect(): void {
    if (this.transportStatusUnsub === null) {
      // Statuswechsel betreffen die abgeleitete Ebene (live ↔ gecacht) → alle
      // Themen-Listener benachrichtigen, nicht nur Status-Listener.
      this.transportStatusUnsub = this.transport.onStatus((status) => {
        for (const listener of this.statusListeners) {
          listener(status);
        }
        for (const topic of this.topics.values()) {
          this.notify(topic);
        }
      });
    }
    this.transport.connect();
  }

  close(): void {
    this.transport.close();
    if (this.transportStatusUnsub) {
      this.transportStatusUnsub();
      this.transportStatusUnsub = null;
    }
  }

  getStatus(): ConnectionStatus {
    return this.transport.getStatus();
  }

  subscribeStatus(listener: StatusListener): () => void {
    this.statusListeners.add(listener);
    return () => {
      this.statusListeners.delete(listener);
    };
  }

  /** Externes-Store-Abo je Thema (für useSyncExternalStore). */
  subscribeTopic(topic: string, listener: () => void): () => void {
    let state = this.topics.get(topic);
    if (state === undefined) {
      state = {
        listeners: new Set(),
        transportUnsub: null,
        view: INITIAL_VIEW,
        pending: undefined,
        hasPending: false,
        flushHandle: null,
      };
      this.topics.set(topic, state);
    }
    const topicState = state;
    topicState.listeners.add(listener);

    // Erstes Abo dieses Themas → Transport-Abo eröffnen.
    if (topicState.transportUnsub === null) {
      topicState.transportUnsub = this.transport.subscribe(
        topic,
        (data) => {
          this.onData(topic, data);
        },
        (reason) => {
          this.onError(topic, reason);
        },
      );
    }

    return () => {
      topicState.listeners.delete(listener);
      if (topicState.listeners.size === 0) {
        if (topicState.flushHandle !== null) {
          this.clearTimeoutFn(topicState.flushHandle);
        }
        topicState.transportUnsub?.();
        this.topics.delete(topic);
      }
    };
  }

  /** Stabiler Snapshot je Thema (Referenz ändert sich nur bei Flush/Fehler). */
  getTopicView(topic: string): TopicView {
    return this.topics.get(topic)?.view ?? INITIAL_VIEW;
  }

  // — intern —

  private onData(topic: string, data: unknown): void {
    const state = this.topics.get(topic);
    if (state === undefined) {
      return;
    }
    state.pending = data;
    state.hasPending = true;
    if (this.throttleMs <= 0) {
      this.flush(topic);
      return;
    }
    if (state.flushHandle === null) {
      state.flushHandle = this.setTimeoutFn(() => {
        this.flush(topic);
      }, this.throttleMs);
    }
  }

  private flush(topic: string): void {
    const state = this.topics.get(topic);
    if (state === undefined) {
      return;
    }
    state.flushHandle = null;
    if (!state.hasPending) {
      return;
    }
    state.hasPending = false;
    state.view = { data: state.pending, error: null, loaded: true };
    this.notify(state);
  }

  private onError(topic: string, reason: string): void {
    const state = this.topics.get(topic);
    if (state === undefined) {
      return;
    }
    // Letzte Daten als Cache behalten (Degradation friert ein, leert nicht).
    state.view = { data: state.view.data, error: reason, loaded: state.view.loaded };
    this.notify(state);
  }

  private notify(state: TopicState): void {
    for (const listener of state.listeners) {
      listener();
    }
  }
}
