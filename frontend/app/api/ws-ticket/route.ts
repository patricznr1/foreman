// ============================================================
//  FOREMAN Frontend — app/api/ws-ticket/route.ts
//  Zweck: Liefert dem Client das Token für den ?token=-Query von /api/v1/ws.
//         Holt dafür ein KURZLEBIGES, WS-scoped Ticket vom Backend
//         (GET /api/v1/ws-ticket, aud="ws", ~60 s) und gibt NUR dieses heraus —
//         NIE das volle Session-JWT (das bleibt im httpOnly-Cookie). Damit ist der
//         §21.8-Security-Follow-up geschlossen: bei Query-/JS-Leak ist nur ein
//         kurzlebiges Nur-WS-Ticket exponiert, kein breit gültiges Session-Token.
//  Architektur-Einordnung: BFF-Route-Handler (Schicht 1, server-seitig).
// ============================================================
import { NextResponse } from "next/server";
import { backendUrl, getSessionToken } from "@/lib/auth/session";

// Secret-/Token-Antwort nie cachen — auf ALLEN Pfaden, auch bei Fehlern.
const NO_STORE = { "cache-control": "no-store, private, max-age=0" } as const;

export async function GET(): Promise<NextResponse> {
  const sessionToken = await getSessionToken();
  if (sessionToken === null) {
    return NextResponse.json({ detail: "Nicht angemeldet" }, { status: 401, headers: NO_STORE });
  }
  try {
    const response = await fetch(`${backendUrl()}/api/v1/ws-ticket`, {
      headers: { Authorization: `Bearer ${sessionToken}` },
      cache: "no-store",
      signal: AbortSignal.timeout(5_000),
    });
    if (!response.ok) {
      return NextResponse.json(
        { detail: "WS-Ticket nicht verfügbar" },
        { status: 502, headers: NO_STORE },
      );
    }
    const data = (await response.json().catch(() => null)) as { ticket?: unknown } | null;
    if (typeof data?.ticket !== "string" || data.ticket.length === 0) {
      return NextResponse.json(
        { detail: "WS-Ticket nicht verfügbar" },
        { status: 502, headers: NO_STORE },
      );
    }
    // Nur das kurzlebige Ticket an Browser-JS — no-store, kein Cache.
    return NextResponse.json({ token: data.ticket }, { headers: NO_STORE });
  } catch {
    return NextResponse.json(
      { detail: "WS-Ticket nicht verfügbar" },
      { status: 502, headers: NO_STORE },
    );
  }
}
