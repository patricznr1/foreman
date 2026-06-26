// ============================================================
//  FOREMAN Frontend — lib/memory/use-memory-search.ts
//  Zweck: On-Demand-Anbindung der ARCHIV-Suche über den BFF-Proxy. Trigger =
//         GET /api/v1/archive/search (der Dreischritt der Studie §3.2: Trigger →
//         benannter Zustand → Ergebnis mit Herkunft). Wiederverwendung des
//         GETEILTEN On-Demand-Reducers (lib/ondemand/machine) wie E. Degradation:
//         die letzte Suche wird mit Stand gecacht (sessionStorage) und bleibt bei
//         Offline/Fehler als früheres Ergebnis sichtbar — kein Leerlaufen. Die
//         Komponente kennt den Transport nie. Read-only: Suche ist Abruf, keine
//         Aktorik. Graceful-Backend: ein Embedding-Ausfall ergibt KEIN 503 mehr (der
//         Wortlaut trägt) — darum kein 503-Sonderpfad, nur generische Fehler/Offline.
//  Architektur-Einordnung: State-Anbindung (Schicht 1 ↔ React).
// ============================================================
"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import type { ArchiveHit } from "@/lib/api/contracts";
import {
  type OnDemandPhase,
  type OnDemandResult,
  initialPhase,
  onDemandReducer,
} from "@/lib/ondemand/machine";
import { assembleArchiveResult } from "./view-model";
import type { ArchiveSearchResult, SourceType } from "./types";
import { searchArchiveEndpoint } from "./url";

const CACHE_KEY = "foreman.archive.lastSearch";

/** Default-Quellen: alle drei (das Backend durchsucht ohne sources ohnehin alle). */
const ALL_SOURCES: SourceType[] = ["note", "maintenance", "alarm"];

export interface ArchiveSearchFilters {
  /** Optionaler Maschinen-Filter (geht als machine_id ans Backend). */
  machineId?: number | null;
  /** Aktive Quellen (geht als sources[] ans Backend). Default: alle drei. */
  sources?: SourceType[];
}

export interface UseMemorySearchResult {
  phase: OnDemandPhase<ArchiveSearchResult>;
  /** Löst eine Archiv-Suche aus (leere Anfrage wird ignoriert). */
  search: (query: string, filters?: ArchiveSearchFilters) => void;
  busy: boolean;
}

/** Fehlertext (Hallensprache) zu einem fehlgeschlagenen Abruf. */
function failureText(status: number | null): string {
  if (status === 401) {
    return "Sitzung abgelaufen — bitte neu anmelden";
  }
  if (status === 403) {
    return "Kein Zugriff auf das Archiv";
  }
  return "Suche nicht möglich (Netz oder Backend)";
}

/** Letzte Suche aus dem sessionStorage lesen (Offline-Toleranz, best-effort). */
function readCache(): OnDemandResult<ArchiveSearchResult> | null {
  if (typeof window === "undefined") {
    return null;
  }
  try {
    const raw = window.sessionStorage.getItem(CACHE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as OnDemandResult<ArchiveSearchResult>;
    if (parsed && typeof parsed.stampedAt === "string" && parsed.data) {
      return parsed;
    }
    return null;
  } catch {
    return null;
  }
}

/** Letzte Suche im sessionStorage ablegen (best-effort, Fehler still schlucken). */
function writeCache(result: OnDemandResult<ArchiveSearchResult>): void {
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
    onDemandReducer<ArchiveSearchResult>,
    null,
    () => initialPhase<ArchiveSearchResult>(readCache()),
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

  const search = useCallback((query: string, filters: ArchiveSearchFilters = {}) => {
    const trimmed = query.trim();
    if (trimmed.length === 0) {
      return; // leere Anfrage löst nichts aus
    }
    // Leere Auswahl auf den Backend-Default (alle Quellen) normalisieren — sonst
    // ließe der Endpoint den Param weg (Backend sucht alle), die Herkunfts-Basis im
    // Ergebnis trüge aber eine leere Quellen-Liste (Anzeige ≠ tatsächlicher Suchlauf).
    const sources =
      filters.sources && filters.sources.length > 0 ? filters.sources : ALL_SOURCES;
    const controller = new AbortController();
    inflight.current?.abort();
    inflight.current = controller;
    dispatch({ type: "request" });

    void (async () => {
      try {
        const response = await fetch(
          searchArchiveEndpoint(trimmed, filters.machineId ?? null, sources),
          { credentials: "same-origin", signal: controller.signal },
        );
        if (!response.ok) {
          if (mounted.current) {
            dispatch({ type: "reject", message: failureText(response.status) });
          }
          return;
        }
        const hits = (await response.json()) as ArchiveHit[];
        const result = assembleArchiveResult(hits, trimmed, sources);
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
