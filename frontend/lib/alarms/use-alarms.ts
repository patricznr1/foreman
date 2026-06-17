// ============================================================
//  FOREMAN Frontend — lib/alarms/use-alarms.ts
//  Zweck: Datenanbindung der Alarm-Liste. Der WS pusht KEINE Alarm-Zeilen (nur
//         Aggregat-Signale) → die Sicht lädt das Erstbild per HTTP (BFF, GET
//         /api/v1/alarms) und lädt bei jedem relevanten WS-Signal gedrosselt nach.
//         Frische Alarme (ID-Diff) tragen das Neu-Flag (Einblend-Puls). Der
//         Lebenszyklus-Zustand (live/gecacht) folgt dem WS-Verbindungsstatus —
//         Degradation friert ein (Studie §3.2). Komponenten kennen den Transport nie.
//  Architektur-Einordnung: State-Anbindung (Schicht 1 ↔ React).
// ============================================================
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { AlarmRead } from "@/lib/api/contracts";
import { useRealtimeStore } from "@/lib/realtime/realtime-context";
import { useConnectionStatus } from "@/lib/state/use-topic";
import { type DataState, deriveDataState } from "@/lib/state/view-state";
import { diffNewIds, idSet } from "./diff";

export interface UseAlarmsOptions {
  /** WS-Themen, deren Signal eine Nachladung auslöst (overview oder machine:{id}). */
  signalTopics: readonly string[];
  /** Obergrenze der Liste (Backend 1–1000). */
  limit?: number;
  /** Gedrosseltes Nachlade-Fenster (ms). */
  refetchDebounceMs?: number;
}

export interface UseAlarmsResult {
  state: DataState<AlarmRead[]>;
  newIds: ReadonlySet<number>;
  stampedAt: Date | null;
  refetch: () => void;
  /** Steigt bei jeder erfolgreichen Nachladung — für die Re-Ansage gleichlautender Live-Meldungen. */
  fetchSeq: number;
}

/** Frist (ms), nach der die Neu-Markierung verfällt → Einblend-Puls bleibt einmalig. */
const NEW_FLAG_TTL_MS = 1500;

function alarmsUrl(limit: number): string {
  return `/api/v1/alarms?limit=${limit}`;
}

export function useAlarms({
  signalTopics,
  limit = 500,
  refetchDebounceMs = 400,
}: UseAlarmsOptions): UseAlarmsResult {
  const store = useRealtimeStore();
  const status = useConnectionStatus(store);

  const [alarms, setAlarms] = useState<AlarmRead[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [newIds, setNewIds] = useState<ReadonlySet<number>>(new Set());
  const [stampedAt, setStampedAt] = useState<Date | null>(null);
  // Nachladung fehlgeschlagen, aber Cache vorhanden → nicht mehr „live" (Freshness ehrlich).
  const [stale, setStale] = useState(false);
  const [fetchSeq, setFetchSeq] = useState(0);

  const prevIds = useRef<Set<number> | null>(null);
  const inflight = useRef<AbortController | null>(null);
  const clearNewHandle = useRef<number | null>(null);

  const fetchNow = useCallback(async () => {
    inflight.current?.abort();
    const controller = new AbortController();
    inflight.current = controller;
    try {
      const response = await fetch(alarmsUrl(limit), {
        credentials: "same-origin",
        signal: controller.signal,
      });
      if (!response.ok) {
        // Fataler Fehler (Auth) nur, wenn wir noch keine Daten haben — sonst
        // gecachtes Bild behalten (Degradation friert ein, leert nicht), aber
        // ehrlich als „nicht mehr live" markieren (Freshness lügt nicht).
        if (prevIds.current === null) {
          setError(
            response.status === 401
              ? "unauthorized"
              : response.status === 403
                ? "forbidden"
                : "fehler",
          );
        } else {
          setStale(true);
        }
        return;
      }
      const data = (await response.json()) as AlarmRead[];
      const fresh = diffNewIds(prevIds.current, data);
      setNewIds(fresh);
      prevIds.current = idSet(data);
      setAlarms(data);
      setError(null);
      setStale(false);
      setStampedAt(new Date());
      setFetchSeq((seq) => seq + 1);
      // Einblend-Puls ist EINMALIG: Neu-Markierung nach kurzer Frist löschen, damit
      // ein späterer Remount (Virtualisierung) oder Re-Render nicht erneut pulst.
      if (clearNewHandle.current !== null) {
        window.clearTimeout(clearNewHandle.current);
        clearNewHandle.current = null;
      }
      if (fresh.size > 0) {
        clearNewHandle.current = window.setTimeout(() => {
          clearNewHandle.current = null;
          setNewIds(new Set());
        }, NEW_FLAG_TTL_MS);
      }
    } catch (caught) {
      if ((caught as Error).name === "AbortError") {
        return;
      }
      if (prevIds.current === null) {
        setError("fehler");
      } else {
        setStale(true);
      }
    }
  }, [limit]);

  // Erstbild.
  useEffect(() => {
    void fetchNow();
    return () => {
      inflight.current?.abort();
      if (clearNewHandle.current !== null) {
        window.clearTimeout(clearNewHandle.current);
      }
    };
  }, [fetchNow]);

  // Live-Signal → gedrosselte Nachladung (kein Polling, nur bei echtem WS-Delta).
  const topicsKey = signalTopics.join(",");
  useEffect(() => {
    let handle: number | null = null;
    const trigger = () => {
      if (handle !== null) {
        return;
      }
      handle = window.setTimeout(() => {
        handle = null;
        void fetchNow();
      }, refetchDebounceMs);
    };
    const unsubscribes = topicsKey
      ? topicsKey.split(",").map((topic) => store.subscribeTopic(topic, trigger))
      : [];
    return () => {
      for (const unsubscribe of unsubscribes) {
        unsubscribe();
      }
      if (handle !== null) {
        window.clearTimeout(handle);
      }
    };
  }, [store, topicsKey, refetchDebounceMs, fetchNow]);

  let state = deriveDataState<AlarmRead[]>(
    { data: alarms ?? undefined, error, loaded: alarms !== null },
    status,
    { isEmpty: (list) => list.length === 0 },
  );
  // Fehlgeschlagene Nachladung trotz Cache: als gecacht zeigen, nicht „live" lügen.
  if (stale && state.kind === "live") {
    state = { kind: "cached", data: state.data };
  }

  return { state, newIds, stampedAt, refetch: fetchNow, fetchSeq };
}
