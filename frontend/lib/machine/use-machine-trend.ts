// ============================================================
//  FOREMAN Frontend — lib/machine/use-machine-trend.ts
//  Zweck: Verdrahtet den Sensortrend transport-agnostisch zu EINER abgeleiteten Reihe:
//         der historische Teil kommt stabil per Pull (`/machines/{id}/trend`, by NAME),
//         der jüngste Rand live über das WS-Thema `trend:{data_point_id}` (das bei
//         jedem Reading das ganze 1h-Fenster neu pusht). Der Merge (trend-series.ts)
//         läuft auf dem bucket-Schlüssel → der Rand atmet ohne Sprung. Die X-Domäne
//         setzt das Zeitfenster (startMs/endMs), nicht die Daten. Degradation: ohne
//         offene Verbindung „gecacht mit Stand", Live eingefroren (kein weißer Schirm).
//  Architektur-Einordnung: View-State-Hook (Schicht 2/3). Nutzt FE1-Echtzeit-Schicht.
// ============================================================
"use client";

import { useEffect, useRef, useState } from "react";

import type { MachineTrendOut } from "@/lib/api/contracts";
import { useRealtimeStore } from "@/lib/realtime/realtime-context";
import { useConnectionStatus, useTopicView } from "@/lib/state/use-topic";
import type { DataState } from "@/lib/state/view-state";

import { windowStartMs } from "./time-window";
import { deriveDriftSegments, mergeTrendSeries } from "./trend-series";
import type { DriftSegment, TrendSeries } from "./types";
import { machineTrendUrl } from "./url";

export interface MachineTrendData {
  series: TrendSeries;
  driftSegments: DriftSegment[];
}

export interface UseMachineTrendArgs {
  machineId: number;
  dataPointId: number;
  dataPointName: string;
  hours: number;
  /** Injizierbar für deterministische Tests; sonst der aktuelle Zeitpunkt. */
  nowMs?: number;
}

export interface UseMachineTrendResult {
  state: DataState<MachineTrendData>;
  startMs: number;
  endMs: number;
  stampedAt: Date | null;
  refetch: () => void;
}

function statusToMessage(status: number): string {
  if (status === 403) return "forbidden";
  if (status === 401) return "unauthorized";
  if (status === 404) return "not_found";
  return "error";
}

export function useMachineTrend({
  machineId,
  dataPointId,
  dataPointName,
  hours,
  nowMs,
}: UseMachineTrendArgs): UseMachineTrendResult {
  const store = useRealtimeStore();
  const status = useConnectionStatus(store);
  const live = useTopicView(store, `trend:${dataPointId}`);

  const [historical, setHistorical] = useState<MachineTrendOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [stampedAt, setStampedAt] = useState<Date | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const inflight = useRef<AbortController | null>(null);

  useEffect(() => {
    let cancelled = false;
    inflight.current?.abort();
    const controller = new AbortController();
    inflight.current = controller;
    setLoaded(false);
    setError(null);
    fetch(machineTrendUrl(machineId, dataPointName, hours), {
      credentials: "same-origin",
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          throw new Error(statusToMessage(response.status));
        }
        return (await response.json()) as MachineTrendOut;
      })
      .then((data) => {
        if (cancelled) return;
        setHistorical(data);
        setStampedAt(new Date());
        setLoaded(true);
      })
      .catch((caught: unknown) => {
        if (cancelled) return;
        if (caught instanceof Error && caught.name === "AbortError") return;
        setError(caught instanceof Error ? caught.message : "error");
        setLoaded(true);
      });
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [machineId, dataPointName, hours, reloadKey]);

  const liveData = (live.data as MachineTrendOut | null) ?? null;
  const merged = mergeTrendSeries(historical, liveData);
  const data: MachineTrendData | null =
    merged !== null ? { series: merged, driftSegments: deriveDriftSegments(merged) } : null;

  const isLoaded = loaded || live.loaded;
  const authoritativeError = error ?? live.error;

  let state: DataState<MachineTrendData>;
  if (data !== null && data.series.samples.length > 0) {
    const fresh = status === "open" && liveData !== null;
    state = fresh ? { kind: "live", data } : { kind: "cached", data };
  } else if (!isLoaded) {
    state = { kind: "loading" };
  } else if (authoritativeError !== null) {
    state = { kind: "error", message: authoritativeError };
  } else {
    state = { kind: "empty" };
  }

  const endMs = nowMs ?? Date.now();
  const startMs = windowStartMs(endMs, hours);

  return {
    state,
    startMs,
    endMs,
    stampedAt,
    refetch: () => setReloadKey((key) => key + 1),
  };
}
