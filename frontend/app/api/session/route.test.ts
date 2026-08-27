// ============================================================
//  FOREMAN Frontend — app/api/session/route.test.ts
//  Zweck: Die BFF-Anmelderoute muss drei Lagen AUSEINANDERHALTEN: falsche
//         Anmeldedaten (401), fehlerhafte Eingabe (400) und einen echten
//         Ausfall des Dienstes (502). Belegter Anlass 27.08.2026: eine E-Mail
//         in ungültigem Format (Backend 422) wurde als „Authentifizierungs-
//         dienst nicht erreichbar" gemeldet — die Fehlersuche ging danach in
//         Netz, DNS, Portzuordnung und Deployment statt ins Eingabefeld.
//  Aufbau-Kontroll-Zwillinge: Zu JEDEM Negativfall steht im selben Aufbau ein
//         Erfolgsfall. Ein Handler, der pauschal einen Status liefert, kann
//         damit nicht grün bleiben — die erwarteten Codes sind paarweise
//         verschieden (200 / 400 / 401 / 502).
//  Architektur-Einordnung: Quality-Gate (npm test).
// ============================================================
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/headers", () => ({ cookies: vi.fn() }));

vi.mock("@/lib/auth/session", () => ({
  SESSION_COOKIE: "foreman_token",
  SESSION_MAX_AGE: 3600,
  backendUrl: () => "http://backend",
  fetchCurrentUser: vi.fn(),
  getCurrentUser: vi.fn(),
}));

import { cookies } from "next/headers";
import type { CurrentUser } from "@/lib/api/contracts";
import { fetchCurrentUser } from "@/lib/auth/session";
import { POST } from "./route";

const mockedCookies = vi.mocked(cookies);
const mockedFetchCurrentUser = vi.mocked(fetchCurrentUser);

const USER: CurrentUser = {
  id: 7,
  email: "diagnose@example.com",
  role: "worker",
  assigned_line_ids: [],
  assigned_machine_ids: [],
};

/** Cookie-Ablage des Handlers; `set` wird geprüft (darf im Fehlerfall NICHT laufen). */
function cookieStore(): { set: ReturnType<typeof vi.fn> } {
  const store = { set: vi.fn(), delete: vi.fn(), get: vi.fn() };
  mockedCookies.mockResolvedValue(store as unknown as Awaited<ReturnType<typeof cookies>>);
  return store;
}

function loginRequest(email: string, password: string): Request {
  return new Request("http://frontend/api/session", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

/** Antwort des Backends auf `POST /auth/login`. */
function backendResponds(status: number, body: unknown): void {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

/** Der geglückte Weg — Kontroll-Zwilling für jeden Negativfall unten. */
function backendAcceptsLogin(): void {
  backendResponds(200, { access_token: "JWT", token_type: "bearer" });
  mockedFetchCurrentUser.mockResolvedValue(USER);
}

async function detailOf(response: Response): Promise<string> {
  const body = (await response.json()) as { detail?: string };
  return body.detail ?? "";
}

describe("POST /api/session (BFF-Anmeldung)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockedFetchCurrentUser.mockReset();
  });

  // ---------------------------------------------------------------
  //  Kontroll-Zwilling: derselbe Aufbau trägt bis zum Erfolg durch.
  //  Ohne ihn belegt kein einziger Negativfall unten etwas.
  // ---------------------------------------------------------------
  it("KONTROLLE: gültige Anmeldung → 200 und Cookie gesetzt", async () => {
    const store = cookieStore();
    backendAcceptsLogin();

    const response = await POST(loginRequest("diagnose@example.com", "richtiges-passwort"));

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual(USER);
    expect(store.set).toHaveBeenCalledWith("foreman_token", "JWT", expect.objectContaining({}));
  });

  it("falsches Passwort (Backend 401) → 401 „Ungültige Anmeldedaten“", async () => {
    const store = cookieStore();
    backendResponds(401, { detail: "Ungültige Anmeldedaten" });

    const response = await POST(loginRequest("diagnose@example.com", "falsches-passwort"));

    expect(response.status).toBe(401);
    expect(await detailOf(response)).toBe("Ungültige Anmeldedaten");
    expect(store.set).not.toHaveBeenCalled();
  });

  it("E-Mail ohne gültiges Format (Backend 422) → 400 mit Eingabe-Meldung, NICHT 502", async () => {
    const store = cookieStore();
    // Echte FastAPI-Form: EmailStr beanstandet `body.email`.
    backendResponds(422, {
      detail: [
        {
          type: "value_error",
          loc: ["body", "email"],
          msg: "value is not a valid email address: An email address must have an @-sign.",
          input: "werker.halle3",
        },
      ],
    });

    const response = await POST(loginRequest("werker.halle3", "irgendein-passwort"));

    expect(response.status).toBe(400);
    expect(await detailOf(response)).toBe("E-Mail-Adresse hat kein gültiges Format");
    expect(store.set).not.toHaveBeenCalled();
  });

  it("die 422-Antwort nennt NICHT den Dienst als Ursache", async () => {
    cookieStore();
    backendResponds(422, { detail: [{ loc: ["body", "email"], msg: "…" }] });

    const response = await POST(loginRequest("werker.halle3", "irgendein-passwort"));

    // Genau der Satz, der die halbe Stunde gekostet hat.
    expect(await detailOf(response)).not.toContain("nicht erreichbar");
    expect(response.status).not.toBe(502);
  });

  it("zu langes Passwort (Backend 422 auf `password`) → eigener Satz, kein E-Mail-Text", async () => {
    cookieStore();
    backendResponds(422, {
      detail: [
        {
          type: "string_too_long",
          loc: ["body", "password"],
          msg: "String should have at most 72 characters",
        },
      ],
    });

    const response = await POST(loginRequest("diagnose@example.com", "x".repeat(80)));

    expect(response.status).toBe(400);
    // Der Text wird aus `loc` ABGELEITET, nicht pauschal gesetzt.
    expect(await detailOf(response)).toBe("Passwort hat kein zulässiges Format (1 bis 72 Zeichen)");
  });

  it("422 zu einem unbekannten Feld → allgemeiner Eingabe-Satz, kein geratenes Feld", async () => {
    cookieStore();
    backendResponds(422, { detail: [{ loc: ["body", "tenant_id"], msg: "…" }] });

    const response = await POST(loginRequest("diagnose@example.com", "passwort"));

    expect(response.status).toBe(400);
    const detail = await detailOf(response);
    expect(detail).toBe("Eingabe wurde abgelehnt — bitte E-Mail und Passwort prüfen");
    expect(detail).not.toContain("E-Mail-Adresse hat kein");
  });

  it("anderes 4xx (z. B. 429) → 400, weil die Anfrage beanstandet wurde", async () => {
    cookieStore();
    backendResponds(429, { detail: "Zu viele Versuche" });

    const response = await POST(loginRequest("diagnose@example.com", "passwort"));

    expect(response.status).toBe(400);
    expect(await detailOf(response)).not.toContain("nicht erreichbar");
  });

  it("Backend-Ausfall (500) bleibt 502 — 5xx wird NICHT zum Eingabefehler", async () => {
    cookieStore();
    backendResponds(500, { detail: "Internal Server Error" });

    const response = await POST(loginRequest("diagnose@example.com", "passwort"));

    expect(response.status).toBe(502);
    expect(await detailOf(response)).toBe("Authentifizierungsdienst nicht erreichbar");
  });

  it("echter Verbindungsfehler (fetch wirft) → 502", async () => {
    const store = cookieStore();
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("fetch failed"));

    const response = await POST(loginRequest("diagnose@example.com", "passwort"));

    expect(response.status).toBe(502);
    expect(await detailOf(response)).toBe("Authentifizierungsdienst nicht erreichbar");
    expect(store.set).not.toHaveBeenCalled();
  });

  it("Zeitüberschreitung (AbortError) → 502", async () => {
    cookieStore();
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      new DOMException("The operation was aborted.", "TimeoutError"),
    );

    const response = await POST(loginRequest("diagnose@example.com", "passwort"));

    expect(response.status).toBe(502);
  });

  it("Antwort ohne access_token → 502 (der Dienst hält den Vertrag nicht)", async () => {
    cookieStore();
    backendResponds(200, { token_type: "bearer" });

    const response = await POST(loginRequest("diagnose@example.com", "passwort"));

    expect(response.status).toBe(502);
  });

  it("fehlende Eingabe wird vor dem Backend abgefangen → 400, kein fetch", async () => {
    cookieStore();
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    const response = await POST(loginRequest("", ""));

    expect(response.status).toBe(400);
    expect(await detailOf(response)).toBe("E-Mail und Passwort erforderlich");
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
