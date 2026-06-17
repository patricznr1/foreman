// ============================================================
//  FOREMAN Frontend — lib/memory/use-memory-search.ts
//  Zweck: On-Demand-Anbindung der Gedächtnis-Suche über den BFF-Proxy. Trigger =
//         GET /worker_notes/search (der Dreischritt der Studie §3.2: Trigger →
//         benannter Zustand → Ergebnis mit Herkunft). Wiederverwendung des
//         GETEILTEN On-Demand-Reducers (lib/ondemand/machine) wie E. Degradation:
//         die letzte Suche wird mit Stand gecacht (sessionStorage) und bleibt bei
//         Offline/Fehler als früheres Ergebnis sichtbar — kein Leerlaufen. Die
//         Komponente kennt den Transport nie. Read-only: Suche ist Abruf, keine
//         Aktorik.
//  Architektur-Einordnung: State-Anbindung (Schicht 1 ↔ React).
// ============================================================
"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import type { WorkerNoteRead } from "@/lib/api/contracts";
import {
  type OnDemandPhase,
  type OnDemandResult,
  initialPhase,
  onDemandReducer,
} from "@/lib/ondemand/machine";
import { assembleSearchResult } from "./view-model";
import type { MemorySearchResult } from "./types";
import { searchNotesEndpoint } from "./url";

const CACHE_KEY = "foreman.memory.lastSearch";

export interface MemorySearchFilters {
  /** Optionaler Maschinen-Filter (geht als machine_id ans Backend). */
  machineId?: number | null;
}

export interface UseMemorySearchResult {
  phase: OnDemandPhase<MemorySearchResult>;
  /** Löst eine Bedeutungssuche aus (leere Anfrage wird ignoriert). */
  search: (query: string, filters?: MemorySearchFilters) => void;
  busy: boolean;
}

/** Fehlertext (Hallensprache) zu einem fehlgeschlagenen Abruf. */
function failureText(status: number | null): string {
  if (status === 401) {
    return "Sitzung abgelaufen — bitte neu anmelden";
  }
  if (status === 403) {
    return "Kein Zugriff auf das Gedächtnis";
  }
  if (status === 503) {
    return "Gedächtnis derzeit nicht erreichbar — bitte später erneut suchen";
  }
  return "Suche nicht möglich (Netz oder Backend)";
}

/** Letzte Suche aus dem sessionStorage lesen (Offline-Toleranz, best-effort). */
function readCache(): OnDemandResult<MemorySearchResult> | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.sessionStorage.getItem(CACHE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as OnDemandResult<MemorySearchResult>;
    if (parsed && typeof parsed.stampedAt === "string" && parsed.data) {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

/** Letzte Suche im sessionStorage ablegen (best-effort, Fehler still schlucken). */
function writeCache(result: OnDemandResult<MemorySearchResult>): void {
  if (typeof window === "undefined") {
    return;
  }
  try {
    window.sessionStorage.setItem(CACHE_KEY, JSON.stringify(result));
  } catch {
    // Speicher voll/gesperrt — die Suche funktioniert auch ohne Cache.
  }
}

export function useMemorySearch(): UseMemorySearchResult {
  const [phase, dispatch] = useReducer(
    onDemandReducer<MemorySearchResult>,
    null,
    () => initialPhase<MemorySearchResult>(readCache()),
  );
  const inflight = useRef<AbortController | null>(null);
  const mounted = useRef(true);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      inflight.current?.abort();
    };
  }, []);

  const search = useCallback((query: string, filters: MemorySearchFilters = {}) => {
    const trimmed = query.trim();
    if (trimmed.length === 0) {
      return; // leere Anfrage löst nichts aus
    }
    const controller = new AbortController();
    inflight.current?.abort();
    inflight.current = controller;
    dispatch({ type: "request" });

    void (async () => {
      try {
        const response = await fetch(
          searchNotesEndpoint(trimmed, filters.machineId ?? null),
          { credentials: "same-origin", signal: controller.signal },
        );
        if (!response.ok) {
          if (mounted.current) {
            dispatch({ type: "reject", message: failureText(response.status) });
          }
          return;
        }
        const notes = (await response.json()) as WorkerNoteRead[];
        const result = assembleSearchResult(notes, trimmed);
        const stampedAt = new Date().toISOString();
        writeCache({ data: result, stampedAt });
        if (mounted.current) {
          dispatch({ type: "resolve", data: result, stampedAt });
        }
      } catch (caught) {
        if ((caught as Error).name === "AbortError") {
          return;
        }
        if (mounted.current) {
          dispatch({ type: "reject", message: failureText(null) });
        }
      }
    })();
  }, []);

  return { phase, search, busy: phase.kind === "processing" };
}
