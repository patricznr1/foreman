// ============================================================
//  FOREMAN Frontend — lib/capture/use-context-suggestions.ts
//  Zweck: Die dezente Brücke zu H (Studie §4J): passende frühere Fälle AN DIESER
//         MASCHINE anbieten („hatten wir das schon mal"). Reine Wiederverwendung der
//         realen F-SEM-Route (searchNotesEndpoint mit machine_id) + des geteilten
//         On-Demand-Reducers. Abruf echter Notizen, KEINE Generierung.
//  DATENSCHUTZ (§8): OPT-IN — der Entwurfstext (potenziell unmaskierter Werker-
//         Freitext) verlässt das Gerät NUR auf eine BEWUSSTE Geste (search()), nie
//         passiv/automatisch beim Tippen. Kein sessionStorage-Cache (kein lokaler
//         Klartext bleibt liegen); abortbar.
//  Architektur-Einordnung: State-Anbindung (Schicht 1 ↔ React).
// ============================================================
"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import type { WorkerNoteRead } from "@/lib/api/contracts";
import { searchNotesEndpoint } from "@/lib/memory/url";
import { initialPhase, onDemandReducer, type OnDemandPhase } from "@/lib/ondemand/machine";

/** Erst ab einer sinnvollen Query suchen (kein Vorschlag bei zwei Buchstaben). */
export const MIN_SUGGESTION_QUERY = 4;
/** Wenige, dezente Treffer (kein zweites H-Vollergebnis im Erfassungs-Flow). */
const SUGGESTION_K = 4;

export interface UseContextSuggestionsResult {
  phase: OnDemandPhase<WorkerNoteRead[]>;
  /** Löst die Suche bewusst aus (Opt-in) — mit dem aktuellen Entwurf + Maschine. */
  search: () => void;
  busy: boolean;
  /** Ob eine Suche überhaupt möglich ist (Maschine gewählt, Query lang genug, aktiv). */
  canSearch: boolean;
}

export function useContextSuggestions(
  text: string,
  machineId: number | null,
  enabled: boolean,
): UseContextSuggestionsResult {
  const [phase, dispatch] = useReducer(onDemandReducer<WorkerNoteRead[]>, null, () =>
    initialPhase<WorkerNoteRead[]>(),
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

  const query = text.trim();
  const canSearch = enabled && machineId !== null && query.length >= MIN_SUGGESTION_QUERY;

  const search = useCallback(() => {
    if (!enabled || machineId === null || query.length < MIN_SUGGESTION_QUERY) {
      return;
    }
    const controller = new AbortController();
    inflight.current?.abort();
    inflight.current = controller;
    dispatch({ type: "request" });
    void (async () => {
      try {
        const response = await fetch(searchNotesEndpoint(query, machineId, SUGGESTION_K), {
          credentials: "same-origin",
          signal: controller.signal,
        });
        if (!response.ok) {
          if (mounted.current) {
            dispatch({ type: "reject", message: "Vorschläge gerade nicht abrufbar" });
          }
          return;
        }
        const notes = (await response.json()) as WorkerNoteRead[];
        if (mounted.current) {
          dispatch({ type: "resolve", data: notes, stampedAt: new Date().toISOString() });
        }
      } catch (caught) {
        if ((caught as Error).name === "AbortError") {
          return;
        }
        if (mounted.current) {
          dispatch({ type: "reject", message: "Vorschläge gerade nicht abrufbar" });
        }
      }
    })();
  }, [enabled, machineId, query]);

  return { phase, search, busy: phase.kind === "processing", canSearch };
}
