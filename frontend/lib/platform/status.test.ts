// ============================================================
//  FOREMAN Frontend — lib/platform/status.test.ts
//  Zweck: Sichert die EHRLICHE Status-/Richtungs-Abbildung: bekannte Werte mappen
//         mehrkanalig, jeder fremde/leere Wert defaultet auf „unbekannt" bzw.
//         „keine" (nie grün geraten), und „verbunden" ist die EINZIGE ok-Aussage.
// ============================================================
import { describe, expect, it } from "vitest";
import {
  connectionStatusLabel,
  directionPresentation,
  normalizeDirection,
  normalizeStatus,
  statusPresentation,
} from "./status";

describe("normalizeStatus", () => {
  it("reicht die vier bekannten Werte durch (inkl. Umlaut 'gestört')", () => {
    expect(normalizeStatus("verbunden")).toBe("verbunden");
    expect(normalizeStatus("gestört")).toBe("gestört");
    expect(normalizeStatus("inaktiv")).toBe("inaktiv");
    expect(normalizeStatus("unbekannt")).toBe("unbekannt");
  });

  it("defaultet fremde/leere Werte ehrlich auf 'unbekannt' (nie grün)", () => {
    expect(normalizeStatus("ok")).toBe("unbekannt");
    expect(normalizeStatus("connected")).toBe("unbekannt");
    expect(normalizeStatus("")).toBe("unbekannt");
    expect(normalizeStatus(null)).toBe("unbekannt");
    expect(normalizeStatus(undefined)).toBe("unbekannt");
  });
});

describe("statusPresentation", () => {
  it("nur 'verbunden' trägt den ok-Token; gestört ist ruhig (kein Alarm-Rot)", () => {
    expect(statusPresentation("verbunden").colorToken).toBe("state-ok");
    expect(statusPresentation("gestört").colorToken).toBe("state-check");
    // gestört darf NICHT die kritische Alarmfarbe tragen (ISA-101-Ruhe).
    expect(statusPresentation("gestört").colorToken).not.toBe("alarm-critical");
    expect(statusPresentation("gestört").colorToken).not.toBe("state-failure");
  });

  it("inaktiv und unbekannt sind neutral und über die FORM unterscheidbar", () => {
    expect(statusPresentation("inaktiv").colorToken).toBe("fg-muted");
    expect(statusPresentation("unbekannt").colorToken).toBe("fg-muted");
    // Farbe allein reicht nicht — der Form-Kanal trennt sie.
    expect(statusPresentation("inaktiv").glyph).toBe("hollow");
    expect(statusPresentation("unbekannt").glyph).toBe("question");
  });

  it("ein unbekannter Roh-Wert wird NICHT als 'verbunden'/grün dargestellt", () => {
    const p = statusPresentation("alles_gut");
    expect(p.status).toBe("unbekannt");
    expect(p.colorToken).not.toBe("state-ok");
  });
});

describe("normalizeDirection / directionPresentation", () => {
  it("reicht bekannte Richtungen durch und mappt sie auf Pfeil-Form", () => {
    expect(normalizeDirection("liefert")).toBe("liefert");
    expect(directionPresentation("liefert").arrow).toBe("in");
    expect(directionPresentation("liest").arrow).toBe("out");
    expect(directionPresentation("beides").arrow).toBe("both");
    expect(directionPresentation("keine").arrow).toBe("none");
  });

  it("defaultet Fremdwerte auf 'keine' (kein erfundener Fluss)", () => {
    expect(normalizeDirection("bidirektional")).toBe("keine");
    expect(normalizeDirection(null)).toBe("keine");
    expect(directionPresentation("xyz").arrow).toBe("none");
  });
});

describe("connectionStatusLabel — interne Quelle spricht ehrlich 'aktiv'", () => {
  it("nennt eine aktive interne Quelle 'aktiv' (intern getickt, kein externer Peer)", () => {
    expect(connectionStatusLabel("verbunden", true)).toBe("aktiv");
  });

  it("lässt 'verbunden' für externe Quellen unverändert", () => {
    expect(connectionStatusLabel("verbunden", false)).toBe("verbunden");
  });

  it("lässt inaktiv/unbekannt/gestört auch intern beim ehrlichen Wort", () => {
    expect(connectionStatusLabel("inaktiv", true)).toBe("inaktiv");
    expect(connectionStatusLabel("unbekannt", true)).toBe("unbekannt");
    expect(connectionStatusLabel("gestört", true)).toBe("gestört");
  });
});
