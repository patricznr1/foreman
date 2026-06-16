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
    signal: AbortSignal.timeout(10_000),
  };
  if (request.method !== "GET" && request.method !== "HEAD") {
    init.body = await request.text();
  }

  let response: Response;
  try {
    response = await fetch(target, init);
  } catch {
    // Backend nicht erreichbar/Timeout → kontrollierter 502 statt opaker 500.
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
