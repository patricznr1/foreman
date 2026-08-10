// ============================================================
//  FOREMAN Frontend — lib/prediction/failure-text.test.ts
//  Zweck: Die Statuscode-Abbildung von Vorhersage + Empfehlung. Wichtig ist die
//         TRENNUNG: die Vorhersage rechnet lokal (kein Modell-Aufruf), nur die
//         Empfehlung braucht das Gateway. Fällt es aus, bleibt die Vorhersage
//         gültig — das muss der Text sagen, sonst wirkt beides kaputt.
// ============================================================
import { describe, expect, it } from "vitest";
import { failureText } from "./use-prediction";

describe("failureText — Vorhersage & Empfehlung", () => {
  it("hält bei 503 die Vorhersage ausdrücklich aufrecht", () => {
    const text = failureText(503, "recommendation");
    expect(text).toContain("vorübergehend");
    expect(text).toContain("Vorhersage bleibt gültig");
  });

  it("meldet die Vorhersage bei 503 als vorübergehend, nicht als Defekt", () => {
    expect(failureText(503, "prediction")).toContain("vorübergehend");
  });

  it("bittet bei 429 um Geduld", () => {
    expect(failureText(429, "recommendation")).toContain("warten");
    expect(failureText(429, "prediction")).toContain("warten");
  });

  it("hält die bestehenden Fälle unverändert", () => {
    expect(failureText(401, "prediction")).toContain("Sitzung");
    expect(failureText(403, "prediction")).toContain("Kein Zugriff");
    // Die Grounding-Ablehnung (Invarianten I/II) bleibt eigenständig benannt.
    expect(failureText(422, "recommendation")).toContain("belegbar");
  });

  it("fällt bei unbekanntem Status auf die allgemeine Meldung zurück", () => {
    expect(failureText(500, "prediction")).toBe("Vorhersage nicht abrufbar");
    expect(failureText(null, "recommendation")).toBe("Empfehlung nicht abrufbar");
  });

  it("nutzt durchgehend Hallensprache ohne internes Vokabular", () => {
    for (const status of [401, 403, 422, 429, 503, 500, null]) {
      for (const what of ["prediction", "recommendation"] as const) {
        const text = failureText(status, what).toLowerCase();
        for (const term of ["gateway", "llm", "shap", "token-bucket", "503"]) {
          expect(text).not.toContain(term);
        }
      }
    }
  });
});
