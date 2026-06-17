// ============================================================
//  FOREMAN Frontend — app/api/ws-ticket/route.ts
//  Zweck: Liefert dem Client das Token für den ?token=-Query von /api/v1/ws.
//         WICHTIG (ehrliche Einordnung): Das Backend exponiert KEIN separates,
//         kurzlebiges WS-Ticket — daher gibt diese Route DERZEIT das volle
//         Session-JWT (httpOnly-Cookie) heraus. Der WS-Vertrag erzwingt ein Token
//         im Query, das clientseitiges JS bauen muss; damit ist der httpOnly-
//         Schutz für DIESEN Pfad bewusst durchbrochen. Der Client persistiert es
//         nicht. Nur same-origin + nur authentifiziert abrufbar.
//  FOLLOW-UP (GROUND_TRUTH §21.8): Backend-Endpoint, der ein kurzlebiges,
//         WS-scoped Ticket (z. B. 30–60 s) prägt; dann hier NUR dieses ausgeben.
//  Architektur-Einordnung: BFF-Route-Handler (Schicht 1, server-seitig).
// ============================================================
import { NextResponse } from "next/server";
import { getSessionToken } from "@/lib/auth/session";

export async function GET(): Promise<NextResponse> {
  const token = await getSessionToken();
  if (token === null) {
    return NextResponse.json({ detail: "Nicht angemeldet" }, { status: 401 });
  }
  // TODO(§21.8): durch ein backend-geprägtes, kurzlebiges WS-Ticket ersetzen.
  // no-store: das Secret darf nicht in Browser-/Proxy-Caches landen.
  return NextResponse.json(
    { token },
    { headers: { "cache-control": "no-store, private, max-age=0" } },
  );
}
