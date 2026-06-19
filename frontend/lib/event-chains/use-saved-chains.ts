// ============================================================
//  FOREMAN Frontend — lib/event-chains/use-saved-chains.ts
//  Zweck: Pull der GESPEICHERTEN Ketten über den BFF — Liste (GET /explanations,
//         optional je Maschine, jüngste zuerst) + Detail (GET /explanations/{id}
//         mit eingefrorener Kette + Schwester-Referenzen). On-Demand = Momentaufnahme
//         → Frische „gecacht", kein Live-Puls. Fünf Pflichtzustände (DataState).
//  Architektur-Einordnung: State-Anbindung (Schicht 1 ↔ React).
// ============================================================
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { ReasonerExplanationDetailRead, ReasonerExplanationRead } from "@/lib/api/contracts";
import type { DataState } from "@/lib/state/view-state";
import { explanationEndpoint, explanationsEndpoint } from "./url";

/** Status-Code → DataState-Fehlerschlüssel (forbidden/unauthorized werden in
 *  five-states zu Hallensprache, sonst generischer Fehler). */
function errorKey(status: number): string {
  if (status === 401) {
    return "unauthorized";
  }
  if (status === 403) {
    return "forbidden";
  }
  return "load-failed";
}

export interface SavedChainsResult {
  state: DataState<ReasonerExplanationRead[]>;
  reload: () => void;
}

export function useSavedChains(machineId: number | null): SavedChainsResult {
  const [state, setState] = useState<DataState<ReasonerExplanationRead[]>>({ kind: "loading" });
  const [tick, setTick] = useState(0);
  const inflight = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    inflight.current?.abort();
    inflight.current = controller;
    setState({ kind: "loading" });
    void (async () => {
      try {
        const res = await fetch(explanationsEndpoint(machineId), {
          credentials: "same-origin",
          signal: controller.signal,
        });
        if (!res.ok) {
          setState({ kind: "error", message: errorKey(res.status) });
          return;
        }
        const list = (await res.json()) as ReasonerExplanationRead[];
        setState(list.length === 0 ? { kind: "empty" } : { kind: "cached", data: list });
      } catch (caught) {
        if ((caught as Error).name === "AbortError") {
          return;
        }
        setState({ kind: "error", message: "load-failed" });
      }
    })();
    return () => controller.abort();
  }, [machineId, tick]);

  const reload = useCallback(() => setTick((value) => value + 1), []);
  return { state, reload };
}

export function useChainDetail(
  explanationId: number | null,
): DataState<ReasonerExplanationDetailRead> {
  const [state, setState] = useState<DataState<ReasonerExplanationDetailRead>>({ kind: "loading" });
  const inflight = useRef<AbortController | null>(null);

  useEffect(() => {
    if (explanationId === null) {
      setState({ kind: "empty" });
      return;
    }
    const controller = new AbortController();
    inflight.current?.abort();
    inflight.current = controller;
    setState({ kind: "loading" });
    void (async () => {
      try {
        const res = await fetch(explanationEndpoint(explanationId), {
          credentials: "same-origin",
          signal: controller.signal,
        });
        if (!res.ok) {
          setState({ kind: "error", message: errorKey(res.status) });
          return;
        }
        const detail = (await res.json()) as ReasonerExplanationDetailRead;
        setState({ kind: "cached", data: detail });
      } catch (caught) {
        if ((caught as Error).name === "AbortError") {
          return;
        }
        setState({ kind: "error", message: "load-failed" });
      }
    })();
    return () => controller.abort();
  }, [explanationId]);

  return state;
}
