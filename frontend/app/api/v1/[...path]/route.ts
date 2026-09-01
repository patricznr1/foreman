// ============================================================
//  FOREMAN Frontend — app/api/v1/[...path]/route.ts
//  Zweck: BFF-Proxy für alle HTTP-Zugriffe auf das Backend-/api/v1. Liest das
//         JWT aus dem httpOnly-Cookie und injiziert es als Bearer — so bleibt
//         das Token vor Browser-JS geschützt und das Backend braucht KEINE
//         CORS-Lockerung (chirurgisch, kein Backend-Change). GENERISCHER Proxy
//         (GET/POST/PATCH/DELETE): die Read-only-/„keine-Aktorik"-Garantie liegt
//         im BACKEND (es exponiert nichts Schaltbares), nicht in dieser Schicht;
//         Auth wird hier erzwungen (401 ohne gültiges Cookie).
//  Architektur-Einordnung: BFF-Route-Handler (Schicht 1, server-seitig).
// ============================================================
import { NextResponse } from "next/server";
import { backendUrl, getSessionToken } from "@/lib/auth/session";

type RouteContext = { params: Promise<{ path: string[] }> };

/** Frist für gewöhnliche Abrufe — Listen, Karten, Trends, Notizen. */
export const STANDARD_TIMEOUT_MS = 10_000;

/**
 * Frist für die auslösenden Aufrufe der Sprachmodell-Bausteine.
 * Das Backend gibt dem Modellaufruf allein schon 60 s (src/foreman/llm/config.py,
 * `request_timeout_s`); dazu kommen Quellenaufbau, Ablage und Substrat-Spiegelung.
 * Gemessen am 01.09.2026 an der Demo-Instanz (`foreman.llm.gateway`-Protokoll):
 * 18,7 s / 26,6 s / 36,9 s reine Modell-Latenz. Mit der früheren pauschalen
 * 10-s-Frist endete deshalb JEDER Auslöser mit 502, während das Backend seine
 * Arbeit erfolgreich zu Ende brachte und ablegte.
 */
export const REASONER_TIMEOUT_MS = 90_000;

/**
 * Welche Frist ein Pfad bekommt. Mit dem Modell rechnen nur die AUSLÖSENDEN
 * Aufrufe unter `reasoners/`; die GETs dort lesen bereits Abgelegtes und sollen
 * weiterhin schnell scheitern.
 */
export function timeoutFor(method: string, path: string[]): number {
  const loestAus = method !== "GET" && method !== "HEAD" && path[0] === "reasoners";
  return loestAus ? REASONER_TIMEOUT_MS : STANDARD_TIMEOUT_MS;
}

async function proxy(request: Request, path: string[]): Promise<Response> {
  const token = await getSessionToken();
  if (token === null) {
    return NextResponse.json({ detail: "Nicht angemeldet" }, { status: 401 });
  }

  // Pfad-Härtung: keine Dot-/Leersegmente (kein Path-Traversal aus /api/v1/ heraus).
  if (path.some((segment) => segment === "" || segment === "." || segment === "..")) {
    return NextResponse.json({ detail: "Ungültiger Pfad" }, { status: 400 });
  }

  const incoming = new URL(request.url);
  const safePath = path.map(encodeURIComponent).join("/");
  const target = `${backendUrl()}/api/v1/${safePath}${incoming.search}`;

  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  const contentType = request.headers.get("content-type");
  if (contentType) {
    headers["content-type"] = contentType;
  }

  const init: RequestInit = {
    method: request.method,
    headers,
    cache: "no-store",
    signal: AbortSignal.timeout(timeoutFor(request.method, path)),
  };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.text();
  }

  let response: Response;
  try {
    response = await fetch(target, init);
  } catch (caught) {
    // Eine Zeitüberschreitung ist KEIN „Backend nicht erreichbar": Am 01.09.2026
    // hat genau diese Zusammenfassung die Ursachensuche zu den Zugangsschlüsseln
    // geschickt, während das Backend rechnete und ablegte. Getrennt melden.
    if (caught instanceof DOMException && caught.name === "TimeoutError") {
      return NextResponse.json({ detail: "Zeitüberschreitung beim Backend" }, { status: 504 });
    }
    // Backend nicht erreichbar → kontrollierter 502 statt opaker 500.
    return NextResponse.json({ detail: "Backend nicht erreichbar" }, { status: 502 });
  }
  const payload = await response.text();
  return new NextResponse(payload, {
    status: response.status,
    headers: { "content-type": response.headers.get("content-type") ?? "application/json" },
  });
}

export async function GET(request: Request, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function POST(request: Request, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function PATCH(request: Request, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  return proxy(request, path);
}

export async function DELETE(request: Request, context: RouteContext): Promise<Response> {
  const { path } = await context.params;
  return proxy(request, path);
}
