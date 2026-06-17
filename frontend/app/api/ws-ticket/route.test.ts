// ============================================================
//  FOREMAN Frontend — app/api/ws-ticket/route.test.ts
//  Zweck: Der BFF-ws-ticket-Handler reicht NUR das kurzlebige Backend-Ticket an
//         den Client durch — nie das Session-JWT. 401 ohne Session, 502 bei
//         Backend-Ausfall, Bearer-Weitergabe ans Backend.
//  Architektur-Einordnung: Quality-Gate (Security-Härtung §21.8).
// ============================================================
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/auth/session", () => ({
  getSessionToken: vi.fn(),
  backendUrl: () => "http://backend",
}));

import { getSessionToken } from "@/lib/auth/session";
import { GET } from "./route";

const mockedGetSessionToken = vi.mocked(getSessionToken);

describe("GET /api/ws-ticket (BFF)", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("401 ohne Session", async () => {
    mockedGetSessionToken.mockResolvedValue(null);
    const response = await GET();
    expect(response.status).toBe(401);
    expect(response.headers.get("cache-control")).toContain("no-store");
  });

  it("gibt NUR das kurzlebige Ticket zurück (nicht das Session-JWT)", async () => {
    mockedGetSessionToken.mockResolvedValue("SESSION_JWT");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ticket: "WS_TICKET", expires_in: 60 }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const response = await GET();
    expect(response.status).toBe(200);
    const body = (await response.json()) as { token: string };
    expect(body.token).toBe("WS_TICKET");
    expect(body.token).not.toBe("SESSION_JWT");
    // Ans Backend mit dem Session-JWT als Bearer — das Session-JWT verlässt den Server nicht.
    expect(fetchSpy).toHaveBeenCalledWith(
      "http://backend/api/v1/ws-ticket",
      expect.objectContaining({ headers: { Authorization: "Bearer SESSION_JWT" } }),
    );
  });

  it("502 wenn das Backend kein Ticket liefert", async () => {
    mockedGetSessionToken.mockResolvedValue("SESSION_JWT");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response("nope", { status: 500 }));
    const response = await GET();
    expect(response.status).toBe(502);
  });

  it("502 wenn das Ticket kein String ist (strikte Validierung)", async () => {
    mockedGetSessionToken.mockResolvedValue("SESSION_JWT");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ ticket: 12345 }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );
    const response = await GET();
    expect(response.status).toBe(502);
  });
});
