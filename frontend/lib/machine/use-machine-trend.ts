// ============================================================
//  FOREMAN Frontend — lib/machine/use-machine-trend.ts
//  Zweck: Verdrahtet den Sensortrend transport-agnostisch zu EINER abgeleiteten Reihe:
//         der historische Teil kommt stabil per Pull (`/machines/{id}/trend`, by NAME),
//         der jüngste Rand live über das WS-Thema `trend:{data_point_id}` (das bei
//         jedem Reading das ganze 1h-Fenster neu pusht). Der Merge (trend-series.ts)
//         läuft auf dem bucket-Schlüssel → der Rand atmet ohne Sprung. Der sichtbare
//         AUSSCHNITT gehört NICHT hierher — er lebt im Ausschnitts-Zustand der
//         Detailsicht; dieser Hook sagt allein, welches LADEFENSTER wirklich
//         beantwortet wurde. Degradation: ohne offene Verbindung „gecacht mit Stand",
//         Live eingefroren (kein weißer Schirm).
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
}

export interface UseMachineTrendResult {
  state: DataState<MachineTrendData>;
  /**
   * Anfang (Epoche ms) des zuletzt ERFOLGREICH beantworteten Ladefensters, sonst
   * null. Speist die `unloaded`-Marke: links davon hat niemand gefragt, und genau
   * das soll dort stehen. Die Quelle ist das Fenster der Anfrage, die zurückkam —
   * NICHT `now - hours*3.6e6` (die Marke wanderte dann schon beim Absenden nach
   * links, während die Kurve dort noch fehlt) und NICHT `samples[0].t` (das machte
   * aus einer echten Messlücke am linken Rand eine erfundene Ladelücke).
   */
  loadedFromMs: number | null;
  /** Eine Anfrage ist unterwegs, während bereits Punkte im Bild stehen. */
  refetching: boolean;
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
}: UseMachineTrendArgs): UseMachineTrendResult {
  const store = useRealtimeStore();
  const status = useConnectionStatus(store);
  const live = useTopicView(store, `trend:${dataPointId}`);

  const [historical, setHistorical] = useState<MachineTrendOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [loadedFromMs, setLoadedFromMs] = useState<number | null>(null);
  const [stampedAt, setStampedAt] = useState<Date | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const inflight = useRef<AbortController | null>(null);

  useEffect(() => {
    let cancelled = false;
    inflight.current?.abort();
    const controller = new AbortController();
    inflight.current = controller;
    // Das Fenster, das GENAU DIESE Anfrage abdeckt (die Route pinnt `end` auf jetzt
    // und nimmt nur `hours`). Es liegt bewusst im Abschluss dieses Laufs und nicht in
    // einem Ref: so kann eine überholte Antwort den Wert einer neueren nicht
    // überschreiben. Fortgeschrieben wird es erst unten im Erfolgszweig.
    const requestedFromMs = windowStartMs(Date.now(), hours);
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
        // Die Fortschrittsmarke — und sie steht NUR hier. Ein Wegfehler (Netz,
        // Zeitüberschreitung, 500) darf keinen Bereich als abgerufen-und-leer
        // markieren: die Fläche links davon trägt sonst keine Schraffur mehr und
        // behauptet damit „dort war nichts", wo in Wahrheit niemand gefragt hat.
        setLoadedFromMs(requestedFromMs);
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

  // `loaded` ist genau „eine HTTP-Anfrage ist unterwegs" (false beim Absenden, true
  // bei Antwort UND bei Fehler). Nachladen heißt: unterwegs, obwohl schon Punkte im
  // Bild stehen — und genau diese beiden Zustände tragen Daten. Der Zustand wird
  // hier ZURÜCKGELESEN statt die Bedingung ein zweites Mal hinzuschreiben.
  const refetching = !loaded && (state.kind === "live" || state.kind === "cached");

  return {
    state,
    loadedFromMs,
    refetching,
    stampedAt,
    refetch: () => setReloadKey((key) => key + 1),
  };
}
