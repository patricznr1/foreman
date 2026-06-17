// ============================================================
//  FOREMAN Frontend — lib/state/view-state.test.ts
//  Zweck: Die fünf Pflichtzustände werden korrekt abgeleitet (Prinzip 2 / §5.5),
//         inkl. der Degradation: geladen + Verbindung weg → gecacht, nicht leer.
//  Architektur-Einordnung: Quality-Gate (Akzeptanzkriterium Fünf-Zustände).
// ============================================================
import { describe, expect, it } from "vitest";
import type { TopicView } from "../realtime/realtime-store";
import { deriveDataState } from "./view-state";

const view = (over: Partial<TopicView>): TopicView => ({
  data: undefined,
  error: null,
  loaded: false,
  ...over,
});

describe("deriveDataState — fünf Pflichtzustände", () => {
  it("nicht geladen → lädt", () => {
    expect(deriveDataState(view({}), "connecting").kind).toBe("loading");
    expect(deriveDataState(view({}), "open").kind).toBe("loading");
  });

  it("geladen + offen → live", () => {
    const state = deriveDataState<{ x: number }>(view({ loaded: true, data: { x: 1 } }), "open");
    expect(state.kind).toBe("live");
    if (state.kind === "live") {
      expect(state.data.x).toBe(1);
    }
  });

  it("geladen + Verbindung weg → gecacht (Degradation friert ein, leert nicht)", () => {
    expect(deriveDataState(view({ loaded: true, data: { x: 1 } }), "reconnecting").kind).toBe(
      "cached",
    );
    expect(deriveDataState(view({ loaded: true, data: { x: 1 } }), "closed").kind).toBe("cached");
  });

  it("geladen + leer → leer", () => {
    const state = deriveDataState<number[]>(view({ loaded: true, data: [] }), "open", {
      isEmpty: (d) => d.length === 0,
    });
    expect(state.kind).toBe("empty");
  });

  it("nicht geladen + Fehler → Fehler", () => {
    expect(deriveDataState(view({ error: "boom" }), "closed").kind).toBe("error");
  });

  it("forbidden ist autoritativ → Fehler trotz vorhandenem Cache", () => {
    const state = deriveDataState(
      view({ loaded: true, data: { x: 1 }, error: "forbidden" }),
      "open",
    );
    expect(state.kind).toBe("error");
    if (state.kind === "error") {
      expect(state.message).toBe("forbidden");
    }
  });
});
