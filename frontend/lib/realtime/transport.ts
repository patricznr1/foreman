// ============================================================
//  FOREMAN Frontend — lib/realtime/transport.ts
//  Zweck: Die Transport-ABSTRAKTION (Studie §5.1) — der einzige Berührungspunkt
//         zwischen Datenlogik und Außenwelt. Visualisierung kennt den Transport
//         NIE; eine Sicht ist gegen WebSocket, Cache oder Testdaten austauschbar,
//         weil alle dieselbe Schnittstelle erfüllen. Das ist nicht verhandelbar.
//  Architektur-Einordnung: Transport-Ebene (Schicht 1, Stream-State-Quelle).
// ============================================================

export type ConnectionStatus = "connecting" | "open" | "reconnecting" | "closed";

export type TopicHandler = (data: unknown) => void;
export type TopicErrorHandler = (reason: string) => void;
export type StatusListener = (status: ConnectionStatus) => void;

/**
 * Gemultiplexter Themen-Transport. Implementierungen: WebSocketTransport (live,
 * /api/v1/ws) und FakeTransport (Tests/Cache). Themen-Strings folgen dem
 * Backend-Vertrag: "overview" | "machine:{id}" | "trend:{data_point_id}".
 */
export interface Transport {
  /** Verbindung aufbauen (idempotent). */
  connect(): void;
  /** Verbindung dauerhaft schließen. */
  close(): void;
  /** Aktueller Verbindungsstatus. */
  getStatus(): ConnectionStatus;
  /** Statusänderungen beobachten. Liefert eine Abmelde-Funktion. */
  onStatus(listener: StatusListener): () => void;
  /**
   * Ein Thema abonnieren. Liefert bei jedem Server-Update `onMessage`, bei
   * Autorisierungs-Ablehnung `onError("forbidden")`. Rückgabe: Abmelde-Funktion.
   */
  subscribe(topic: string, onMessage: TopicHandler, onError?: TopicErrorHandler): () => void;
}
