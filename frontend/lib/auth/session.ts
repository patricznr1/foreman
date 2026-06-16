// ============================================================
//  FOREMAN Frontend — lib/auth/session.ts
//  Zweck: Server-seitige Session-Helfer des BFF. Das JWT lebt in einem
//         httpOnly-Cookie (vor Browser-JS geschützt); HTTP-Requests gehen
//         same-origin über den Proxy-Route-Handler, der den Bearer injiziert.
//         Rolle/Scope kommen aus GET /api/v1/me (Spiegel der Server-Authz).
//  Architektur-Einordnung: BFF/Server (Schicht 1). NUR server-seitig (next/headers).
// ============================================================
import { cookies } from "next/headers";
import type { CurrentUser } from "@/lib/api/contracts";

export const SESSION_COOKIE = "foreman_token";
/**
 * Cookie-Lebensdauer (s) = Backend-Default `jwt_expire_minutes` (60), KEINE Garantie:
 * Wird der Backend-Wert per Env geändert, driftet dies. Das maxAge ist nur eine
 * obere Schranke fürs Cookie — die echte Autorität bleibt die JWT-exp (die
 * Middleware prüft sie). Follow-up: `expires_in` aus dem Login-Vertrag übernehmen.
 */
export const SESSION_MAX_AGE = 60 * 60;

/** Backend-Basis-URL (server-seitig, nie an den Browser ausgeliefert). */
export function backendUrl(): string {
  return process.env.FOREMAN_API_URL ?? "http://localhost:8000";
}

export async function getSessionToken(): Promise<string | null> {
  const store = await cookies();
  return store.get(SESSION_COOKIE)?.value ?? null;
}

/** Lädt Identität + Rolle + Scope des Token-Inhabers (GET /api/v1/me). */
export async function fetchCurrentUser(token: string): Promise<CurrentUser | null> {
  try {
    const response = await fetch(`${backendUrl()}/api/v1/me`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as CurrentUser;
  } catch {
    return null;
  }
}

export async function getCurrentUser(): Promise<CurrentUser | null> {
  const token = await getSessionToken();
  if (token === null) {
    return null;
  }
  return fetchCurrentUser(token);
}
