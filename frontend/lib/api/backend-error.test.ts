// ============================================================
//  FOREMAN Frontend — lib/api/backend-error.test.ts
//  Zweck: Die Trennung 4xx (Anfrage) / 5xx (Dienst) und das Auslesen der
//         beanstandeten Felder aus einem FastAPI-422. Kern der Zusicherung:
//         aus einem Body fremder Form wird KEIN Feldname geraten.
//  Architektur-Einordnung: Quality-Gate (npm test).
// ============================================================
import { describe, expect, it } from "vitest";
import { invalidFields, isClientError } from "./backend-error";

describe("isClientError", () => {
  it("trennt Anfrage-Fehler von Dienst-Fehlern an den Grenzen", () => {
    // Grenzwerte, nicht nur die bequemen Mittelwerte.
    expect(isClientError(399)).toBe(false);
    expect(isClientError(400)).toBe(true);
    expect(isClientError(401)).toBe(true);
    expect(isClientError(422)).toBe(true);
    expect(isClientError(429)).toBe(true);
    expect(isClientError(499)).toBe(true);
    expect(isClientError(500)).toBe(false);
    expect(isClientError(502)).toBe(false);
    expect(isClientError(200)).toBe(false);
  });
});

describe("invalidFields", () => {
  it("liest den Feldnamen aus einem echten FastAPI-422 (E-Mail)", () => {
    const payload = {
      detail: [
        {
          type: "value_error",
          loc: ["body", "email"],
          msg: "value is not a valid email address: An email address must have an @-sign.",
          input: "werker.halle3",
        },
      ],
    };
    expect(invalidFields(payload)).toEqual(["email"]);
  });

  it("liest mehrere beanstandete Felder in der Reihenfolge des Backends", () => {
    const payload = {
      detail: [
        { type: "value_error", loc: ["body", "email"], msg: "…" },
        { type: "string_too_long", loc: ["body", "password"], msg: "…" },
      ],
    };
    expect(invalidFields(payload)).toEqual(["email", "password"]);
  });

  it("nimmt den LETZTEN loc-Eintrag, auch bei verschachtelten Pfaden", () => {
    const payload = { detail: [{ loc: ["body", "credentials", "password"] }] };
    expect(invalidFields(payload)).toEqual(["password"]);
  });

  // Negativfälle: aus fremder Form wird NICHTS geraten. Der Kontroll-Zwilling
  // oben belegt, dass diese leeren Ergebnisse nicht daher rühren, dass die
  // Funktion grundsätzlich nichts findet.
  it.each([
    ["kein Objekt", "Internal Server Error"],
    ["null", null],
    ["detail als Zeichenkette (HTTPException statt Validierung)", { detail: "Nicht gefunden" }],
    ["detail fehlt", { message: "kaputt" }],
    ["loc kein Array", { detail: [{ loc: "body.email" }] }],
    ["loc leer", { detail: [{ loc: [] }] }],
    ["loc endet auf Zahl (Listenindex)", { detail: [{ loc: ["body", 0] }] }],
    ["Eintrag ist kein Objekt", { detail: ["body.email"] }],
  ])("rät nichts bei %s", (_fall, payload) => {
    expect(invalidFields(payload)).toEqual([]);
  });

  it("überspringt unbrauchbare Einträge, behält die brauchbaren", () => {
    const payload = { detail: [{ loc: "kaputt" }, null, { loc: ["body", "email"] }] };
    expect(invalidFields(payload)).toEqual(["email"]);
  });
});
