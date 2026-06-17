// ============================================================
//  FOREMAN Frontend — lib/ondemand/machine.test.ts
//  Zweck: Sichert den GETEILTEN On-Demand-Automaten (Dreischritt + Degradation).
// ============================================================
import { describe, expect, it } from "vitest";
import {
  initialPhase,
  type OnDemandPhase,
  onDemandReducer,
  previousResult,
} from "./machine";

const AT = "2026-06-17T08:30:00.000Z";
const AT2 = "2026-06-17T09:00:00.000Z";

describe("onDemandReducer — Dreischritt", () => {
  it("startet leer (idle, ohne früheres Ergebnis)", () => {
    const phase = initialPhase<number>();
    expect(phase).toEqual({ kind: "idle", previous: null });
  });

  it("request → resolve führt idle über processing zu result", () => {
    let phase: OnDemandPhase<number> = initialPhase<number>();
    phase = onDemandReducer(phase, { type: "request" });
    expect(phase.kind).toBe("processing");
    phase = onDemandReducer(phase, { type: "resolve", data: 42, stampedAt: AT });
    expect(phase).toEqual({ kind: "result", result: { data: 42, stampedAt: AT } });
  });

  it("reject zeigt den Fehler", () => {
    let phase: OnDemandPhase<number> = initialPhase<number>();
    phase = onDemandReducer(phase, { type: "request" });
    phase = onDemandReducer(phase, { type: "reject", message: "offline" });
    expect(phase).toEqual({ kind: "error", message: "offline", previous: null });
  });
});

describe("onDemandReducer — Degradation hält frühere Ergebnisse mit Stand", () => {
  it("ein erneuter Trigger behält das frühere Ergebnis (kein Leerlaufen)", () => {
    let phase: OnDemandPhase<number> = initialPhase<number>();
    phase = onDemandReducer(phase, { type: "resolve", data: 1, stampedAt: AT });
    phase = onDemandReducer(phase, { type: "request" });
    expect(phase).toEqual({ kind: "processing", previous: { data: 1, stampedAt: AT } });
  });

  it("ein Fehlschlag nach einem Ergebnis verwirft das frühere Ergebnis NICHT", () => {
    let phase: OnDemandPhase<number> = initialPhase<number>();
    phase = onDemandReducer(phase, { type: "resolve", data: 1, stampedAt: AT });
    phase = onDemandReducer(phase, { type: "request" });
    phase = onDemandReducer(phase, { type: "reject", message: "fehler" });
    expect(previousResult(phase)).toEqual({ data: 1, stampedAt: AT });
  });

  it("reset kehrt in den Ruhezustand zurück, behält aber das frühere Ergebnis", () => {
    let phase: OnDemandPhase<number> = initialPhase<number>();
    phase = onDemandReducer(phase, { type: "resolve", data: 7, stampedAt: AT2 });
    phase = onDemandReducer(phase, { type: "reset" });
    expect(phase).toEqual({ kind: "idle", previous: { data: 7, stampedAt: AT2 } });
  });

  it("ein frisches resolve ersetzt das frühere Ergebnis", () => {
    let phase: OnDemandPhase<number> = initialPhase<number>();
    phase = onDemandReducer(phase, { type: "resolve", data: 1, stampedAt: AT });
    phase = onDemandReducer(phase, { type: "resolve", data: 2, stampedAt: AT2 });
    expect(previousResult(phase)).toEqual({ data: 2, stampedAt: AT2 });
  });
});
