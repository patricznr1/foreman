// ============================================================
//  FOREMAN Frontend — app/api/session/route.ts
//  Zweck: BFF-Session-Endpoint. POST = Login (ruft Backend /auth/login server-
//         seitig, legt das JWT in ein httpOnly-Cookie, liefert Rolle/Scope via
//         /me). DELETE = Logout (Cookie löschen). GET = aktuelle Session.
//  Architektur-Einordnung: BFF-Route-Handler (Schicht 1, server-seitig).
// ============================================================
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import {
  SESSION_COOKIE,
  SESSION_MAX_AGE,
  backendUrl,
  fetchCurrentUser,
  getCurrentUser,
} from "@/lib/auth/session";

interface LoginBody {
  email?: string;
  password?: string;
}

export async function POST(request: Request): Promise<NextResponse> {
  const body = (await request.json().catch(() => ({}))) as LoginBody;
  if (!body.email || !body.password) {
    return NextResponse.json({ detail: "E-Mail und Passwort erforderlich" }, { status: 400 });
  }

  const loginResponse = await fetch(`${backendUrl()}/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email: body.email, password: body.password }),
    cache: "no-store",
  });
  if (!loginResponse.ok) {
    return NextResponse.json({ detail: "Ungültige Anmeldedaten" }, { status: 401 });
  }

  const { access_token: accessToken } = (await loginResponse.json()) as { access_token: string };
  const user = await fetchCurrentUser(accessToken);
  if (user === null) {
    return NextResponse.json({ detail: "Profil nicht abrufbar" }, { status: 502 });
  }

  const store = await cookies();
  store.set(SESSION_COOKIE, accessToken, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: SESSION_MAX_AGE,
  });
  return NextResponse.json(user);
}

export async function DELETE(): Promise<NextResponse> {
  const store = await cookies();
  store.delete(SESSION_COOKIE);
  return NextResponse.json({ ok: true });
}

export async function GET(): Promise<NextResponse> {
  const user = await getCurrentUser();
  if (user === null) {
    return NextResponse.json({ detail: "Nicht angemeldet" }, { status: 401 });
  }
  return NextResponse.json(user);
}
