// ============================================================
//  FOREMAN Frontend — lib/alarms/lifecycle.test.ts
//  Zweck: Lebenszyklus aus Zeitstempeln (kein Backend-Feld), Drift-Klasse,
//         erwartete Bedienhandlung je Zustand.
// ============================================================
import { describe, expect, it } from "vitest";
import { deriveBaseLifecycle, expectedAction, isDriftAlarm } from "./lifecycle";

describe("deriveBaseLifecycle — aus Zeitstempeln", () => {
  it("cleared_at gesetzt → geklärt (schlägt alles)", () => {
    expect(
      deriveBaseLifecycle({ cleared_at: "2026-06-17T09:00:00Z", acknowledged_at: null }),
    ).toBe("cleared");
    expect(
      deriveBaseLifecycle({
        cleared_at: "2026-06-17T09:00:00Z",
        acknowledged_at: "2026-06-17T08:30:00Z",
      }),
    ).toBe("cleared");
  });

  it("nur acknowledged_at → quittiert", () => {
    expect(deriveBaseLifecycle({ cleared_at: null, acknowledged_at: "2026-06-17T08:30:00Z" })).toBe(
      "acknowledged",
    );
  });

  it("keine Stempel → aktiv", () => {
    expect(deriveBaseLifecycle({ cleared_at: null, acknowledged_at: null })).toBe("active");
  });
});

describe("isDriftAlarm", () => {
  it("erkennt code=DRIFT", () => {
    expect(isDriftAlarm({ code: "DRIFT" })).toBe(true);
    expect(isDriftAlarm({ code: "OTHER" })).toBe(false);
    expect(isDriftAlarm({ code: null })).toBe(false);
  });
});

describe("expectedAction — Hallensprache je Zustand", () => {
  it("aktiv+kritisch → sofort prüfen und quittieren", () => {
    expect(expectedAction("critical", "active", false)).toMatch(/quittieren/i);
  });
  it("aktiv+drift → Abweichung prüfen (weicher)", () => {
    expect(expectedAction("medium", "active", true)).toMatch(/abweichung/i);
  });
  it("quittiert/geklärt schlagen die Priorität", () => {
    expect(expectedAction("critical", "acknowledged", false)).toMatch(/quittiert/i);
    expect(expectedAction("critical", "cleared", false)).toBe("Erledigt");
    expect(expectedAction("critical", "shelved", false)).toMatch(/zurückgestellt/i);
  });
});
