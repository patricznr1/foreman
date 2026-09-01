// ============================================================
//  FOREMAN Frontend — app/api/v1/[...path]/route.test.ts
//  Zweck: Der BFF-Proxy muss den Sprachmodell-Bausteinen genug Zeit lassen und
//         eine Zeitüberschreitung von einem echten Ausfall UNTERSCHEIDEN.
//         Belegter Anlass 01.09.2026: Die Frist stand pauschal auf 10 s, während
//         ein Modellaufruf 18,7 bis 36,9 s braucht (gemessen an der Demo-Instanz,
//         `foreman.llm.gateway`-Protokoll). Jeder Auslöser endete mit 502
//         „Backend nicht erreichbar" — das Backend rechnete dabei erfolgreich zu
//         Ende und legte sein Ergebnis ab, nur die Antwort kam nicht mehr durch.
//         Die Fehlersuche ging deshalb zuerst zu den Zugangsschlüsseln.
//         Dieselbe Klasse wie der Vorfall in app/api/session/route.test.ts.
//  Aufbau-Kontroll-Zwillinge: Zu jedem Negativfall steht im selben Aufbau ein
//         Erfolgsfall, und die erwarteten Codes sind paarweise verschieden
//         (200 / 401 / 400 / 502 / 504). Ein Handler, der pauschal einen Status
//         liefert, kann damit nicht grün bleiben.
//  Architektur-Einordnung: Quality-Gate (npm test).
// ============================================================
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/auth/session", () => ({
  backendUrl: () => "http://backend",
  getSessionToken: vi.fn(),
}));

import { getSessionToken } from "@/lib/auth/session";
import { GET, POST, REASONER_TIMEOUT_MS, STANDARD_TIMEOUT_MS, timeoutFor } from "./route";

const mockedToken = vi.mocked(getSessionToken);

function angemeldet(): void {
  mockedToken.mockResolvedValue("JWT");
}

function anfrage(method: string, pfad: string): Request {
  return new Request(`http://frontend/api/v1/${pfad}`, {
    method,
    headers: { "content-type": "application/json" },
    ...(method === "GET" ? {} : { body: "{}" }),
  });
}

function kontext(pfad: string): { params: Promise<{ path: string[] }> } {
  return { params: Promise.resolve({ path: pfad.split("/") }) };
}

/** Das Backend antwortet regulär — Kontroll-Zwilling für jeden Negativfall. */
function backendAntwortet(status = 200, body: unknown = { ok: true }): void {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

async function detailVon(response: Response): Promise<string> {
  const body = (await response.json()) as { detail?: string };
  return body.detail ?? "";
}

describe("timeoutFor — welche Frist ein Pfad bekommt", () => {
  // Die drei auslösenden Aufrufe der Sprachmodell-Bausteine. Genau sie liefen
  // am 01.09.2026 in die zu kurze Frist.
  it.each([
    ["POST", "reasoners/event_chain/reconstruct"],
    ["POST", "reasoners/failure/predict"],
    ["POST", "reasoners/failure/predictions/20/recommendation"],
  ])("%s /%s bekommt die lange Frist", (method, pfad) => {
    expect(timeoutFor(method, pfad.split("/"))).toBe(REASONER_TIMEOUT_MS);
  });

  it("die lange Frist deckt den Gateway-Timeout des Backends (60 s) ab", () => {
    // src/foreman/llm/config.py -> request_timeout_s = 60.0, dazu Quellenaufbau,
    // Speichern und Substrat-Spiegelung. Eine kürzere Frist würde das Backend
    // erneut mitten in der Arbeit abschneiden.
    expect(REASONER_TIMEOUT_MS).toBeGreaterThan(60_000);
  });

  // Gegenprobe: Die lange Frist gilt NICHT pauschal für alles unter reasoners/.
  it("GET unter reasoners/ liest nur Gespeichertes und bleibt bei der kurzen Frist", () => {
    expect(timeoutFor("GET", ["reasoners", "event_chain", "explanations"])).toBe(
      STANDARD_TIMEOUT_MS,
    );
  });

  it.each([
    ["GET", "machines"],
    ["POST", "worker_notes"],
    ["GET", "alarms"],
  ])("%s /%s bleibt bei der kurzen Frist", (method, pfad) => {
    expect(timeoutFor(method, pfad.split("/"))).toBe(STANDARD_TIMEOUT_MS);
  });

  it("die beiden Fristen sind verschieden — sonst belegt keiner der Fälle oben etwas", () => {
    expect(REASONER_TIMEOUT_MS).not.toBe(STANDARD_TIMEOUT_MS);
  });
});

describe("POST /api/v1/[...path] — die Frist kommt am fetch an", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockedToken.mockReset();
  });

  it("KONTROLLE: ein Auslöser wird durchgereicht und liefert die Backend-Antwort", async () => {
    angemeldet();
    backendAntwortet(201, { id: 9 });

    const response = await POST(
      anfrage("POST", "reasoners/event_chain/reconstruct"),
      kontext("reasoners/event_chain/reconstruct"),
    );

    expect(response.status).toBe(201);
    expect(await response.json()).toEqual({ id: 9 });
  });

  it("der Auslöser der Ereigniskette bekommt die LANGE Frist am fetch", async () => {
    angemeldet();
    backendAntwortet();
    const uhr = vi.spyOn(AbortSignal, "timeout");

    await POST(
      anfrage("POST", "reasoners/event_chain/reconstruct"),
      kontext("reasoners/event_chain/reconstruct"),
    );

    // Der Wert selbst wird geprüft, nicht nur, dass irgendein Signal gesetzt wurde.
    expect(uhr).toHaveBeenCalledWith(REASONER_TIMEOUT_MS);
    expect(uhr).not.toHaveBeenCalledWith(STANDARD_TIMEOUT_MS);
  });

  it("ein gewöhnlicher Abruf bekommt weiterhin die KURZE Frist", async () => {
    angemeldet();
    backendAntwortet();
    const uhr = vi.spyOn(AbortSignal, "timeout");

    await GET(anfrage("GET", "machines"), kontext("machines"));

    expect(uhr).toHaveBeenCalledWith(STANDARD_TIMEOUT_MS);
    expect(uhr).not.toHaveBeenCalledWith(REASONER_TIMEOUT_MS);
  });
});

describe("POST /api/v1/[...path] — Zeitüberschreitung ist kein Ausfall", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockedToken.mockReset();
  });

  it("KONTROLLE: derselbe Aufbau trägt bis zum Erfolg durch", async () => {
    angemeldet();
    backendAntwortet(200, { narrative: "…" });

    const response = await POST(
      anfrage("POST", "reasoners/failure/predict"),
      kontext("reasoners/failure/predict"),
    );

    expect(response.status).toBe(200);
  });

  it("Zeitüberschreitung → 504, NICHT 502", async () => {
    angemeldet();
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      new DOMException("The operation was aborted due to timeout", "TimeoutError"),
    );

    const response = await POST(
      anfrage("POST", "reasoners/event_chain/reconstruct"),
      kontext("reasoners/event_chain/reconstruct"),
    );

    expect(response.status).toBe(504);
    expect(response.status).not.toBe(502);
  });

  it("die Zeitüberschreitung behauptet NICHT, das Backend sei weg", async () => {
    angemeldet();
    vi.spyOn(globalThis, "fetch").mockRejectedValue(
      new DOMException("aborted", "TimeoutError"),
    );

    const response = await POST(
      anfrage("POST", "reasoners/event_chain/reconstruct"),
      kontext("reasoners/event_chain/reconstruct"),
    );

    // Genau der Satz, der die Ursachensuche zu den Zugangsschlüsseln geschickt hat.
    expect(await detailVon(response)).not.toContain("nicht erreichbar");
  });

  it("echter Verbindungsfehler bleibt 502 „Backend nicht erreichbar“", async () => {
    angemeldet();
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("fetch failed"));

    const response = await POST(anfrage("POST", "machines"), kontext("machines"));

    expect(response.status).toBe(502);
    expect(await detailVon(response)).toBe("Backend nicht erreichbar");
  });
});

describe("POST /api/v1/[...path] — die bestehenden Zusicherungen halten", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockedToken.mockReset();
  });

  it("ohne Anmeldung → 401 und es geht kein fetch hinaus", async () => {
    mockedToken.mockResolvedValue(null);
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    const response = await GET(anfrage("GET", "machines"), kontext("machines"));

    expect(response.status).toBe(401);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("Pfad-Traversal wird abgewiesen → 400 und kein fetch", async () => {
    angemeldet();
    const fetchSpy = vi.spyOn(globalThis, "fetch");

    const response = await GET(anfrage("GET", "machines"), kontext("machines/../secret"));

    expect(response.status).toBe(400);
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
