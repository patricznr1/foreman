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

export async function GET(): Promise<NextResponse> {
  const sessionToken = await getSessionToken();
  if (sessionToken === null) {
    return NextResponse.json({ detail: "Nicht angemeldet" }, { status: 401 });
  }
  try {
    const response = await fetch(`${backendUrl()}/api/v1/ws-ticket`, {
      headers: { Authorization: `Bearer ${sessionToken}` },
      cache: "no-store",
      signal: AbortSignal.timeout(5_000),
    });
    if (!response.ok) {
      return NextResponse.json({ detail: "WS-Ticket nicht verfügbar" }, { status: 502 });
    }
    const data = (await response.json().catch(() => null)) as { ticket?: string } | null;
    if (!data?.ticket) {
      return NextResponse.json({ detail: "WS-Ticket nicht verfügbar" }, { status: 502 });
    }
    // Nur das kurzlebige Ticket an Browser-JS — no-store, kein Cache.
    return NextResponse.json(
      { token: data.ticket },
      { headers: { "cache-control": "no-store, private, max-age=0" } },
    );
  } catch {
    return NextResponse.json({ detail: "WS-Ticket nicht verfügbar" }, { status: 502 });
  }
}
