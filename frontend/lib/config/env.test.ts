// ============================================================
//  FOREMAN Frontend — lib/config/env.test.ts
//  Zweck: Die Startprüfung fordert `FOREMAN_API_URL` im Betrieb ein, statt eine
//         Adresse zu raten, die dort nie stimmt. Der Kontroll-Zwilling zu jedem
//         Abbruch ist ein Aufruf im selben Aufbau, der NICHT werfen darf —
//         sonst bliebe eine Funktion grün, die immer wirft.
//  Architektur-Einordnung: Quality-Gate (npm test).
// ============================================================
import { describe, expect, it } from "vitest";
import { assertBackendUrlConfigured } from "./env";

describe("assertBackendUrlConfigured", () => {
  it("bricht in Produktion ab, wenn FOREMAN_API_URL fehlt", () => {
    expect(() => assertBackendUrlConfigured({ NODE_ENV: "production" })).toThrow(
      /FOREMAN_API_URL ist nicht gesetzt/,
    );
  });

  it.each([
    ["leerer Wert", ""],
    ["nur Leerzeichen", "   "],
  ])("bricht in Produktion ab bei %s", (_fall, wert) => {
    expect(() =>
      assertBackendUrlConfigured({ NODE_ENV: "production", FOREMAN_API_URL: wert }),
    ).toThrow(/FOREMAN_API_URL ist nicht gesetzt/);
  });

  // KONTROLLE: derselbe Aufbau, gesetzte Variable — die Funktion wirft NICHT
  // pauschal. Ohne diesen Fall belegten die drei Abbrüche oben nichts.
  it("KONTROLLE: lässt Produktion mit gesetzter Adresse durch", () => {
    expect(() =>
      assertBackendUrlConfigured({
        NODE_ENV: "production",
        FOREMAN_API_URL: "http://backend.railway.internal:8000",
      }),
    ).not.toThrow();
  });

  it("lässt Entwicklung ohne Variable durch — der Vorgabewert bleibt dort erlaubt", () => {
    expect(() => assertBackendUrlConfigured({ NODE_ENV: "development" })).not.toThrow();
    expect(() => assertBackendUrlConfigured({ NODE_ENV: "test" })).not.toThrow();
  });

  it("die Meldung nennt die Variable und den Weg zur Behebung", () => {
    // Eine Startmeldung, die nur „Konfigurationsfehler" sagt, kostet dieselbe
    // Suchzeit wie der geratene Vorgabewert.
    expect(() => assertBackendUrlConfigured({ NODE_ENV: "production" })).toThrow(/DEPLOY\.md/);
  });
});
