// ============================================================
//  FOREMAN Frontend — lib/event-chains/failure-text.test.ts
//  Zweck: Die Statuscode-Abbildung der Ketten-Rekonstruktion. 503/429 sind
//         BEKANNTE Betriebszustände (Modell-Gateway nicht erreichbar bzw.
//         gedrosselt) und müssen als vorübergehend erkennbar sein — nicht als
//         Defekt. Gegenstück zur Backend-Abbildung (§11.2/§13.2).
// ============================================================
import { describe, expect, it } from "vitest";
import { failureText } from "./use-chains";

describe("failureText — Ketten-Rekonstruktion", () => {
  it("benennt 503 als vorübergehend und stellt klar, was weiterläuft", () => {
    const text = failureText(503);
    expect(text).toContain("vorübergehend");
    // Der Werker soll wissen, dass die Anlage weiter beobachtet wird.
    expect(text.toLowerCase()).toContain("alarme");
  });

  it("bittet bei 429 um Geduld statt einen Fehler zu melden", () => {
    expect(failureText(429)).toContain("warten");
  });

  it("hält die bestehenden Fälle unverändert", () => {
    expect(failureText(401)).toContain("Sitzung");
    expect(failureText(403)).toContain("Kein Zugriff");
    expect(failureText(404)).toContain("nicht gefunden");
    expect(failureText(422)).toContain("Ungültiger Anker");
  });

  it("fällt bei unbekanntem Status auf die allgemeine Meldung zurück", () => {
    expect(failureText(500)).toContain("nicht rekonstruierbar");
    expect(failureText(null)).toContain("nicht rekonstruierbar");
  });

  it("nutzt durchgehend Hallensprache ohne internes Vokabular", () => {
    for (const status of [401, 403, 404, 422, 429, 503, 500, null]) {
      const text = failureText(status).toLowerCase();
      for (const term of ["gateway", "backend-unavailable", "llm", "token-bucket", "500"]) {
        expect(text).not.toContain(term);
      }
    }
  });
});
