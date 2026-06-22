// ============================================================
//  FOREMAN Frontend — lib/event-chains/use-chains.ts
//  Zweck: On-Demand-Anbindung der Rekonstruktion (Studie §3.2/§4D) über den BFF.
//         Trigger = POST /reconstruct {anchor_alarm_id, lookback_hours?} gegen einen
//         Anker-ALARM (Vertrag: der Anker IST ein Alarm). Erbt den GETEILTEN
//         Reducer (lib/ondemand) — Degradation hält frühere Ergebnisse mit Stand.
//         Die Komponente kennt den Transport nie.
//  Architektur-Einordnung: State-Anbindung (Schicht 1 ↔ React).
// ============================================================
"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import type { ReasonerExplanationDetailRead, ReconstructRequestBody } from "@/lib/api/contracts";
import { type OnDemandPhase, initialPhase, onDemandReducer } from "@/lib/ondemand/machine";
import { reconstructEndpoint } from "./url";

export interface UseChainReconstructionResult {
  phase: OnDemandPhase<ReasonerExplanationDetailRead>;
  /** Rekonstruiert gegen den Anker-Alarm (optionaler Rückblick in Stunden). */
  trigger: (lookbackHours?: number | null) => void;
  busy: boolean;
}

const JSON_HEADERS = { "content-type": "application/json" } as const;

/** Fehlertext (Hallensprache) zu einem fehlgeschlagenen Schritt. */
function failureText(status: number | null): string {
  if (status === 401) {
    return "Sitzung abgelaufen — bitte neu anmelden";
  }
  if (status === 403) {
    return "Kein Zugriff auf diese Erkenntnis";
  }
  if (status === 404) {
    return "Anker-Alarm nicht gefunden";
  }
  if (status === 422) {
    return "Ungültiger Anker oder Rückblick-Fenster";
  }
  return "Kette nicht rekonstruierbar (Netz oder Backend)";
}

export function useChainReconstruction(anchorAlarmId: number | null): UseChainReconstructionResult {
  const [phase, dispatch] = useReducer(
    onDemandReducer<ReasonerExplanationDetailRead>,
    initialPhase<ReasonerExplanationDetailRead>(),
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

  const trigger = useCallback(
    (lookbackHours: number | null = null) => {
      if (anchorAlarmId === null) {
        return;
      }
      const controller = new AbortController();
      inflight.current?.abort();
      inflight.current = controller;
      dispatch({ type: "request" });

      void (async () => {
        try {
          const body: ReconstructRequestBody = { anchor_alarm_id: anchorAlarmId };
          if (lookbackHours != null) {
            body.lookback_hours = lookbackHours;
          }
          const res = await fetch(reconstructEndpoint(), {
            method: "POST",
            credentials: "same-origin",
            headers: JSON_HEADERS,
            body: JSON.stringify(body),
            signal: controller.signal,
          });
          if (!res.ok) {
            if (mounted.current) {
              dispatch({ type: "reject", message: failureText(res.status) });
            }
            return;
          }
          const detail = (await res.json()) as ReasonerExplanationDetailRead;
          if (mounted.current) {
            dispatch({ type: "resolve", data: detail, stampedAt: detail.created_at });
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
    },
    [anchorAlarmId],
  );

  return { phase, trigger, busy: phase.kind === "processing" };
}
