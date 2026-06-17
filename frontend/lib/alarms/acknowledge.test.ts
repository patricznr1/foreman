// ============================================================
//  FOREMAN Frontend — lib/alarms/acknowledge.test.ts
//  Zweck: HITL-Grenze. NEGATIVTEST: keine Aktion löst je einen Anlagen-Schreibpfad
//         auf — nur die Status-Quittierung am Alarm. Plus Endpunkt-Auflösung,
//         Pflicht-Kontext, Deaktivierungs-Gründe, auditierbarer Datensatz.
// ============================================================
import { describe, expect, it } from "vitest";
import {
  ackDisabledReason,
  acknowledgeEndpoint,
  buildAcknowledgeRecord,
  isAlarmStatusActionPath,
  requiresAckContext,
} from "./acknowledge";

describe("acknowledgeEndpoint — reale Route nur für Drift", () => {
  it("Drift-Warnung → echte Backend-Route", () => {
    expect(acknowledgeEndpoint({ id: 42, code: "DRIFT" })).toBe(
      "/api/v1/reasoners/drift/alarms/42/acknowledge",
    );
  });

  it("Nicht-Drift → null (generische Route fehlt, Anschlusspunkt)", () => {
    expect(acknowledgeEndpoint({ id: 7, code: null })).toBeNull();
    expect(acknowledgeEndpoint({ id: 7, code: "PROCESS" })).toBeNull();
  });
});

describe("HITL-GRENZE — kein Anlagen-Schreibpfad (Negativtest)", () => {
  it("akzeptiert NUR den /acknowledge-Status-Pfad", () => {
    expect(isAlarmStatusActionPath("/api/v1/reasoners/drift/alarms/42/acknowledge")).toBe(true);
  });

  it("verweigert jeden Anlagen-/Aktor-/Schalt-Pfad", () => {
    const forbidden = [
      "/api/v1/machines/42/start",
      "/api/v1/machines/42/stop",
      "/api/v1/machines/42/setpoint",
      "/api/v1/reasoners/drift/alarms/42/control",
      "/api/v1/reasoners/drift/alarms/42/acknowledge/../../machines/42/start",
      "/api/v1/alarms/42", // kein /acknowledge-Suffix
      "/api/v1/actuators/42/write",
    ];
    for (const path of forbidden) {
      expect(isAlarmStatusActionPath(path)).toBe(false);
    }
  });

  it("die aufgelöste reale Route ist selbst eine erlaubte Status-Aktion", () => {
    const endpoint = acknowledgeEndpoint({ id: 9, code: "DRIFT" });
    expect(endpoint).not.toBeNull();
    expect(isAlarmStatusActionPath(endpoint as string)).toBe(true);
  });
});

describe("Pflicht-Kontext & Deaktivierung", () => {
  it("kritisch erfordert Begründung (zweistufig mit Pflicht-Kontext)", () => {
    expect(requiresAckContext("critical")).toBe(true);
    expect(requiresAckContext("high")).toBe(false);
  });

  it("Deaktivierungs-Gründe priorisieren Berechtigung → offline → fehlende Route", () => {
    expect(ackDisabledReason({ online: true, canAcknowledge: false, endpoint: "/x" })).toBe(
      "no-permission",
    );
    expect(ackDisabledReason({ online: false, canAcknowledge: true, endpoint: "/x" })).toBe(
      "offline",
    );
    expect(ackDisabledReason({ online: true, canAcknowledge: true, endpoint: null })).toBe(
      "no-route",
    );
    expect(ackDisabledReason({ online: true, canAcknowledge: true, endpoint: "/x" })).toBeNull();
  });
});

describe("buildAcknowledgeRecord — auditierbare Felder (wer/wann/warum)", () => {
  it("trimmt die Begründung; leere → null", () => {
    const rec = buildAcknowledgeRecord({ id: 3, priority: "critical" }, "  Pumpe geprüft  ", "T");
    expect(rec).toEqual({ alarmId: 3, atIso: "T", reason: "Pumpe geprüft" });
    expect(buildAcknowledgeRecord({ id: 3, priority: "low" }, "   ", "T").reason).toBeNull();
  });
});
