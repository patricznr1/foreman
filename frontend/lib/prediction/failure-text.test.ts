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

  it("benennt 504 als Verzögerung und verweist auf die Ablage", () => {
    // Anlass 01.09.2026: Der Proxy brach nach 10 s ab, während das Backend die
    // Empfehlung fertig erzeugte und ablegte. Der Text darf sie nicht für
    // verloren erklären.
    const text = failureText(504, "recommendation");
    expect(text).toContain("dauert");
    expect(text).toContain("erscheint");
    expect(text).not.toBe("Empfehlung nicht abrufbar");
  });

  it("trennt bei 504 Vorhersage und Empfehlung", () => {
    expect(failureText(504, "prediction")).not.toBe(failureText(504, "recommendation"));
  });

  it("unterscheidet 504 von 503 — verschiedene Lagen, verschiedene Sätze", () => {
    expect(failureText(504, "recommendation")).not.toBe(failureText(503, "recommendation"));
    expect(failureText(504, "prediction")).not.toBe(failureText(503, "prediction"));
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
    for (const status of [401, 403, 422, 429, 503, 504, 500, null]) {
      for (const what of ["prediction", "recommendation"] as const) {
        const text = failureText(status, what).toLowerCase();
        for (const term of ["gateway", "llm", "shap", "token-bucket", "503"]) {
          expect(text).not.toContain(term);
        }
      }
    }
  });
});
