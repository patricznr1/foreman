// ============================================================
//  FOREMAN Frontend — lib/realtime/testing/fake-transport.ts
//  Zweck: Test-Double für Transport — beweist die Transport-Entkopplung (§5.1):
//         Store und Komponenten laufen identisch gegen WebSocket ODER diesen
//         Fake (Stream/Cache/Testdaten). Tests treiben den Strom über emit().
//  Architektur-Einordnung: Test-Infrastruktur (Schicht 1).
// ============================================================
import type {
  ConnectionStatus,
  StatusListener,
  TopicErrorHandler,
  TopicHandler,
  Transport,
} from "../transport";

interface FakeTopic {
  handlers: Set<TopicHandler>;
  errorHandlers: Set<TopicErrorHandler>;
}

export class FakeTransport implements Transport {
  private status: ConnectionStatus = "closed";
  private readonly statusListeners = new Set<StatusListener>();
  private readonly topics = new Map<string, FakeTopic>();
  /** Gesamtzahl subscribe-Aufrufe je Thema (inkl. Re-Subscribe nach Reconnect). */
  readonly subscribeCount = new Map<string, number>();
  readonly unsubscribeCount = new Map<string, number>();

  connect(): void {
    this.setStatus("open");
  }

  close(): void {
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
    if (entry === undefined) {
      entry = { handlers: new Set(), errorHandlers: new Set() };
      this.topics.set(topic, entry);
    }
    const topicEntry = entry;
    topicEntry.handlers.add(onMessage);
    if (onError) {
      topicEntry.errorHandlers.add(onError);
    }
    this.subscribeCount.set(topic, (this.subscribeCount.get(topic) ?? 0) + 1);
    return () => {
      topicEntry.handlers.delete(onMessage);
      if (onError) {
        topicEntry.errorHandlers.delete(onError);
      }
      this.unsubscribeCount.set(topic, (this.unsubscribeCount.get(topic) ?? 0) + 1);
      if (topicEntry.handlers.size === 0) {
        this.topics.delete(topic);
      }
    };
  }

  // — Test-Steuerung —

  setStatus(status: ConnectionStatus): void {
    if (this.status === status) {
      return;
    }
    this.status = status;
    for (const listener of this.statusListeners) {
      listener(status);
    }
  }

  /** Simuliert ein Server-Update für ein Thema. */
  emit(topic: string, data: unknown): void {
    const entry = this.topics.get(topic);
    if (entry === undefined) {
      return;
    }
    for (const handler of entry.handlers) {
      handler(data);
    }
  }

  /** Simuliert eine Autorisierungs-Ablehnung (z. B. "forbidden"). */
  emitError(topic: string, reason: string): void {
    const entry = this.topics.get(topic);
    if (entry === undefined) {
      return;
    }
    for (const handler of entry.errorHandlers) {
      handler(reason);
    }
  }

  hasTopic(topic: string): boolean {
    return this.topics.has(topic);
  }
}
