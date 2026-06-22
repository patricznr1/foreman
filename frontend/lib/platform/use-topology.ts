// ============================================================
//  FOREMAN Frontend — lib/platform/use-topology.ts
//  Zweck: HTTP-Snapshot-Anbindung der Systemtopologie über den BFF (§22.2). Es gibt
//         BEWUSST KEINEN WS-Live-Feed für Sektion I — der Backend-Status wird pro
//         Request berechnet, der „Live-Statuswechsel" der Studie ist [VISION].
//         Daher: Snapshot + EXPLIZITER, manueller Refresh. Der Refresh hat Kosten
//         (probe=true schreibt einen Substrat-Smoke-Marker, §9) → er ist bewusst,
//         und der probe-Schalter steuert das Backend-Query-Param. Fünf Zustände
//         über DataState; Degradation hält den letzten Stand.
//  Architektur-Einordnung: State-Anbindung (Schicht 1 ↔ React).
// ============================================================
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { DataState } from "@/lib/state/view-state";
import { assembleTopology, realNodeCount } from "./topology-view-model";
import type { TopologyModel, TopologyViewRead } from "./types";
import { fetchErrorKey, topologyEndpoint } from "./url";

export interface UseTopologyResult {
  state: DataState<TopologyModel>;
  /** Lädt den Snapshot neu (bewusste Aktion; probe=true schreibt einen Smoke-Marker). */
  refresh: () => void;
  /** Ein Snapshot wird gerade geladen (für die ruhige Refresh-Rückmeldung). */
  refreshing: boolean;
}

/**
 * Lädt einen Topologie-Snapshot. `probe` steuert die Substrat-Live-Probe,
 * `freshWithinMinutes` das „verbunden"-Fenster. Re-Fetch bei Parameter-Wechsel
 * oder explizitem `refresh()`.
 */
export function useTopology(probe: boolean, freshWithinMinutes?: number): UseTopologyResult {
  const [state, setState] = useState<DataState<TopologyModel>>({ kind: "loading" });
  const [tick, setTick] = useState(0);
  const [refreshing, setRefreshing] = useState(true);
  const inflight = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    inflight.current?.abort();
    inflight.current = controller;
    setRefreshing(true);
    void (async () => {
      try {
        const res = await fetch(topologyEndpoint({ probe, freshWithinMinutes }), {
          credentials: "same-origin",
          cache: "no-store",
          signal: controller.signal,
        });
        if (!res.ok) {
          setState({ kind: "error", message: fetchErrorKey(res.status) });
          return;
        }
        const raw = (await res.json()) as TopologyViewRead;
        const model = assembleTopology(raw);
        setState(
          realNodeCount(model) === 0 && model.vision.length === 0
            ? { kind: "empty" }
            : { kind: "cached", data: model },
        );
      } catch (caught) {
        if ((caught as Error).name === "AbortError") {
          return;
        }
        setState({ kind: "error", message: "load-failed" });
      } finally {
        if (!controller.signal.aborted) {
          setRefreshing(false);
        }
      }
    })();
    return () => controller.abort();
  }, [probe, freshWithinMinutes, tick]);

  const refresh = useCallback(() => setTick((value) => value + 1), []);
  return { state, refresh, refreshing };
}
