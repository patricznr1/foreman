// ============================================================
//  FOREMAN Frontend — app/api/session/route.ts
//  Zweck: BFF-Session-Endpoint. POST = Login (ruft Backend /auth/login server-
//         seitig, legt das JWT in ein httpOnly-Cookie, liefert Rolle/Scope via
//         /me). DELETE = Logout (Cookie löschen). GET = aktuelle Session.
//  Architektur-Einordnung: BFF-Route-Handler (Schicht 1, server-seitig).
// ============================================================
import { cookies } from "next/headers";
import { NextResponse } from "next/server";
import { invalidFields, isClientError } from "@/lib/api/backend-error";
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

/**
 * Beanstandetes Feld → Satz in Hallensprache.
 *
 * Das Backend prüft die Anmeldedaten mit Pydantic (`schemas/auth.py`): `EmailStr`
 * für die Adresse, 1–72 Zeichen fürs Passwort (bcrypt verarbeitet max. 72 Byte).
 * Beides ergibt 422 — ein EINGABE-Fehler, der auch als solcher am Terminal
 * ankommen muss.
 */
const LOGIN_FIELD_MESSAGES: Record<string, string> = {
  email: "E-Mail-Adresse hat kein gültiges Format",
  password: "Passwort hat kein zulässiges Format (1 bis 72 Zeichen)",
};

/** Wenn das Backend ein Feld beanstandet, das hier nicht steht (oder keines nennt). */
const LOGIN_INPUT_FALLBACK = "Eingabe wurde abgelehnt — bitte E-Mail und Passwort prüfen";

/** Übersetzt einen 422-Body in einen Satz für die Halle; nennt nie ein geratenes Feld. */
function loginInputMessage(payload: unknown): string {
  for (const field of invalidFields(payload)) {
    const message = LOGIN_FIELD_MESSAGES[field];
    if (message !== undefined) {
      return message;
    }
  }
  return LOGIN_INPUT_FALLBACK;
}

export async function POST(request: Request): Promise<NextResponse> {
  const body = (await request.json().catch(() => ({}))) as LoginBody;
  if (!body.email || !body.password) {
    return NextResponse.json({ detail: "E-Mail und Passwort erforderlich" }, { status: 400 });
  }

  let accessToken: string;
  try {
    const loginResponse = await fetch(`${backendUrl()}/auth/login`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email: body.email, password: body.password }),
      cache: "no-store",
      signal: AbortSignal.timeout(5_000),
    });
    if (loginResponse.status === 401) {
      return NextResponse.json({ detail: "Ungültige Anmeldedaten" }, { status: 401 });
    }
    // Jedes andere 4xx beanstandet die EINGABE, nicht den Dienst. Ohne diesen
    // Zweig meldete eine E-Mail in ungültigem Format (Backend: 422) hier
    // „Authentifizierungsdienst nicht erreichbar" — und die Fehlersuche ging in
    // Netz, DNS und Deployment statt ins Eingabefeld.
    if (isClientError(loginResponse.status)) {
      const payload = (await loginResponse.json().catch(() => null)) as unknown;
      return NextResponse.json({ detail: loginInputMessage(payload) }, { status: 400 });
    }
    if (!loginResponse.ok) {
      return NextResponse.json(
        { detail: "Authentifizierungsdienst nicht erreichbar" },
        { status: 502 },
      );
    }
    const data = (await loginResponse.json().catch(() => null)) as { access_token?: string } | null;
    if (!data?.access_token) {
      return NextResponse.json(
        { detail: "Authentifizierungsdienst nicht erreichbar" },
        { status: 502 },
      );
    }
    accessToken = data.access_token;
  } catch {
    return NextResponse.json(
      { detail: "Authentifizierungsdienst nicht erreichbar" },
      { status: 502 },
    );
  }

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
