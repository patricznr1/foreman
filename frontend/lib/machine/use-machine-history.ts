// ============================================================
//  FOREMAN Frontend — lib/machine/use-machine-history.ts
//  Zweck: Lädt die Maschinen-Historie (Wartung + Notizen) per Pull, blätterbar
//         (limit/offset je Quelle), und vereint sie über buildHistory zu einer
//         chronologischen Liste (PII maskiert). Pull-only → „gecacht, Stand X"
//         (kein Live-Puls; Historie ist eine Momentaufnahme). Degradation: Fehler
//         ohne Daten → Fehler-Zustand, sonst weiter mit dem vorhandenen Stand.
//  Architektur-Einordnung: View-State-Hook (Schicht 2/3, client).
// ============================================================
"use client";

import { useCallback, useEffect, useState } from "react";

import type { MaintenanceEventRead, WorkerNoteRead } from "@/lib/api/contracts";
import type { DataState } from "@/lib/state/view-state";

import { buildHistory, type MachineHistoryItem } from "./history";
import { maintenanceEventsUrl, workerNotesUrl } from "./url";

const DEFAULT_PAGE_SIZE = 25;

export interface UseMachineHistoryArgs {
  machineId: number;
  pageSize?: number;
}

export interface UseMachineHistoryResult {
  state: DataState<MachineHistoryItem[]>;
  loadMore: () => void;
  hasMore: boolean;
  loadingMore: boolean;
  stampedAt: Date | null;
}

export function useMachineHistory({
  machineId,
  pageSize = DEFAULT_PAGE_SIZE,
}: UseMachineHistoryArgs): UseMachineHistoryResult {
  const [maintenance, setMaintenance] = useState<MaintenanceEventRead[]>([]);
  const [notes, setNotes] = useState<WorkerNoteRead[]>([]);
  const [offset, setOffset] = useState(0);
  const [loaded, setLoaded] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stampedAt, setStampedAt] = useState<Date | null>(null);
  const [hasMore, setHasMore] = useState(false);

  const fetchPage = useCallback(
    async (pageOffset: number, replace: boolean) => {
      if (pageOffset === 0) {
        setLoaded(false);
      } else {
        setLoadingMore(true);
      }
      setError(null);
      try {
        const [maintRes, notesRes] = await Promise.all([
          fetch(maintenanceEventsUrl(machineId, pageSize, pageOffset), { credentials: "same-origin" }),
          fetch(workerNotesUrl(machineId, pageSize, pageOffset), { credentials: "same-origin" }),
        ]);
        if (!maintRes.ok || !notesRes.ok) {
          const status = !maintRes.ok ? maintRes.status : notesRes.status;
          throw new Error(status === 403 ? "forbidden" : status === 401 ? "unauthorized" : "error");
        }
        const maint = (await maintRes.json()) as MaintenanceEventRead[];
        const note = (await notesRes.json()) as WorkerNoteRead[];
        setMaintenance((prev) => (replace ? maint : [...prev, ...maint]));
        setNotes((prev) => (replace ? note : [...prev, ...note]));
        setHasMore(maint.length >= pageSize || note.length >= pageSize);
        setStampedAt(new Date());
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : "error");
      } finally {
        setLoaded(true);
        setLoadingMore(false);
      }
    },
    [machineId, pageSize],
  );

  useEffect(() => {
    setMaintenance([]);
    setNotes([]);
    setOffset(0);
    void fetchPage(0, true);
  }, [fetchPage]);

  const loadMore = useCallback(() => {
    const next = offset + pageSize;
    setOffset(next);
    void fetchPage(next, false);
  }, [offset, pageSize, fetchPage]);

  const items = buildHistory(maintenance, notes);

  let state: DataState<MachineHistoryItem[]>;
  if (!loaded) {
    state = { kind: "loading" };
  } else if (error !== null && items.length === 0) {
    state = { kind: "error", message: error };
  } else if (items.length === 0) {
    state = { kind: "empty" };
  } else {
    state = { kind: "cached", data: items };
  }

  return { state, loadMore, hasMore, loadingMore, stampedAt };
}
