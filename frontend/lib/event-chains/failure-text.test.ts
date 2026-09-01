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

  it("benennt 504 als Verzögerung, NICHT als Fehlschlag", () => {
    // Anlass 01.09.2026: Der Proxy brach nach 10 s ab, während das Backend die
    // Kette fertig rechnete und ablegte. Der Text darf die Arbeit nicht für
    // verloren erklären — sonst löst der Bediener sie ein zweites Mal aus.
    const text = failureText(504);
    expect(text).toContain("dauert");
    expect(text).toContain("gespeicherten Ketten");
    expect(text).not.toContain("nicht rekonstruierbar");
  });

  it("unterscheidet 504 von 503 — verschiedene Lagen, verschiedene Sätze", () => {
    expect(failureText(504)).not.toBe(failureText(503));
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
    for (const status of [401, 403, 404, 422, 429, 503, 504, 500, null]) {
      const text = failureText(status).toLowerCase();
      for (const term of ["gateway", "backend-unavailable", "llm", "token-bucket", "500"]) {
        expect(text).not.toContain(term);
      }
    }
  });
});
