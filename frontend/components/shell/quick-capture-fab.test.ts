// ============================================================
//  FOREMAN Frontend — components/shell/quick-capture-fab.test.ts
//  Zweck: Sichert die Kontext-Ableitung der Schnellerfassung (?machine= aus der
//         aktuellen Maschinen-Detailseite, sonst kontextlos).
// ============================================================
import { describe, expect, it } from "vitest";
import { captureHref } from "./quick-capture-fab";

describe("captureHref", () => {
  it("öffnet J kontextlos auf normalen Routen", () => {
    expect(captureHref("/alarms")).toBe("/capture");
    expect(captureHref("/overview")).toBe("/capture");
    expect(captureHref(null)).toBe("/capture");
  });

  it("wählt die Maschine vor, wenn man auf ihrer Detailseite steht", () => {
    expect(captureHref("/machines/42")).toBe("/capture?machine=42");
    expect(captureHref("/machines/42/")).toBe("/capture?machine=42");
  });

  it("ignoriert die Maschinen-Übersicht ohne ID (keine Vorauswahl)", () => {
    expect(captureHref("/machines")).toBe("/capture");
  });
});
