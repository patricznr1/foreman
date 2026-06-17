// ============================================================
//  FOREMAN Frontend — lib/realtime/testing/fake-websocket.ts
//  Zweck: Test-Double für eine WebSocket-Verbindung (WebSocketLike). Erfasst
//         gesendete Nachrichten und erlaubt das manuelle Auslösen von open/
//         message/close — ohne echten Socket. Für die WebSocketTransport-Tests.
//  Architektur-Einordnung: Test-Infrastruktur (Schicht 1).
// ============================================================
import type { WebSocketLike } from "../ws-client";

export class FakeWebSocket implements WebSocketLike {
  // 0 = CONNECTING, 1 = OPEN, 3 = CLOSED.
  readyState = 0;
  readonly sent: string[] = [];
  onopen: (() => void) | null = null;
  onclose: ((event: { code: number; reason: string }) => void) | null = null;
  onmessage: ((event: { data: unknown }) => void) | null = null;
  onerror: (() => void) | null = null;

  send(data: string): void {
    this.sent.push(data);
  }

  close(code?: number, reason?: string): void {
    this.readyState = 3;
    this.onclose?.({ code: code ?? 1000, reason: reason ?? "" });
  }

  // — Test-Steuerung —

  /** Simuliert das Öffnen der Verbindung. */
  triggerOpen(): void {
    this.readyState = 1;
    this.onopen?.();
  }

  /** Simuliert eine eingehende Server-Nachricht (roher JSON-String). */
  triggerMessage(data: string): void {
    this.onmessage?.({ data });
  }

  /** Simuliert einen serverseitigen Verbindungsabbruch mit Close-Code. */
  triggerServerClose(code: number): void {
    this.readyState = 3;
    this.onclose?.({ code, reason: "" });
  }

  /** Die gesendeten Nachrichten als geparste Objekte. */
  sentMessages(): unknown[] {
    return this.sent.map((raw) => JSON.parse(raw) as unknown);
  }
}
