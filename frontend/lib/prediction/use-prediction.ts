// ============================================================
//  FOREMAN Frontend — lib/prediction/use-prediction.ts
//  Zweck: On-Demand-Anbindung der Sektion E über den BFF-Proxy. Trigger =
//         POST /predict → POST .../recommendation (der Dreischritt der Studie §3.2);
//         Autoload = jüngste VOLLSTÄNDIGE Erkenntnis (Vorhersage + ihre Empfehlung)
//         als Snapshot. Liefert NIE eine nackte Vorhersage ohne Empfehlung — fehlt
//         die Empfehlung, bleibt der Ruhezustand. Die Komponente kennt den Transport nie.
//  Architektur-Einordnung: State-Anbindung (Schicht 1 ↔ React).
// ============================================================
"use client";

import { useCallback, useEffect, useReducer, useRef } from "react";
import type { FailurePredictionRead, WorkerRecommendationRead } from "@/lib/api/contracts";
import { type OnDemandPhase, initialPhase, onDemandReducer } from "@/lib/ondemand/machine";
import type { PredictionPair } from "./types";
import { latestPredictionEndpoint, predictEndpoint, recommendationEndpoint } from "./url";

export interface UsePredictionOptions {
  machineId: number;
  /** Beim Mount die jüngste gespeicherte Erkenntnis laden (Werker/Techniker). */
  autoload?: boolean;
}

export interface UsePredictionResult {
  phase: OnDemandPhase<PredictionPair>;
  /** Fordert frisch an: Vorhersage + Empfehlung (nur erlaubte Rollen rufen das auf). */
  trigger: () => void;
  busy: boolean;
}

const JSON_HEADERS = { "content-type": "application/json" } as const;

/** Fehlertext (Hallensprache) zu einem fehlgeschlagenen Schritt. */
function failureText(status: number | null, what: "prediction" | "recommendation"): string {
  if (status === 401) {
    return "Sitzung abgelaufen — bitte neu anmelden";
  }
  if (status === 403) {
    return "Kein Zugriff auf diese Erkenntnis";
  }
  if (what === "recommendation" && status === 422) {
    // Backend rejectet eine unbelegte/umdeutende Empfehlung (Invarianten I/II) — ehrlich benennen.
    return "Empfehlung konnte nicht belegbar erzeugt werden";
  }
  return what === "prediction" ? "Vorhersage nicht abrufbar" : "Empfehlung nicht abrufbar";
}

export function usePrediction({ machineId, autoload = true }: UsePredictionOptions): UsePredictionResult {
  const [phase, dispatch] = useReducer(
    onDemandReducer<PredictionPair>,
    initialPhase<PredictionPair>(),
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

  /** Jüngste VOLLSTÄNDIGE Erkenntnis laden (Snapshot) — nie eine nackte Vorhersage. */
  const loadLatest = useCallback(async () => {
    const controller = new AbortController();
    inflight.current?.abort();
    inflight.current = controller;
    try {
      const predRes = await fetch(latestPredictionEndpoint(machineId), {
        credentials: "same-origin",
        signal: controller.signal,
      });
      if (!predRes.ok) {
        return;
      }
      const list = (await predRes.json()) as FailurePredictionRead[];
      const prediction = list[0];
      if (!prediction) {
        return; // keine gespeicherte Vorhersage → Ruhezustand bleibt leer
      }
      const recRes = await fetch(recommendationEndpoint(prediction.id), {
        credentials: "same-origin",
        signal: controller.signal,
      });
      if (!recRes.ok) {
        return; // Vorhersage ohne Empfehlung → keine Karte, Ruhezustand bleibt leer
      }
      const recommendation = (await recRes.json()) as WorkerRecommendationRead;
      if (mounted.current) {
        dispatch({
          type: "resolve",
          data: { prediction, recommendation },
          stampedAt: recommendation.created_at,
        });
      }
    } catch {
      // Autoload ist best-effort: still bleiben, der Trigger kann frisch holen.
    }
  }, [machineId]);

  useEffect(() => {
    if (autoload) {
      void loadLatest();
    }
  }, [autoload, loadLatest]);

  const trigger = useCallback(() => {
    const controller = new AbortController();
    inflight.current?.abort();
    inflight.current = controller;
    dispatch({ type: "request" });

    void (async () => {
      try {
        const predRes = await fetch(predictEndpoint(), {
          method: "POST",
          credentials: "same-origin",
          headers: JSON_HEADERS,
          body: JSON.stringify({ machine_id: machineId }),
          signal: controller.signal,
        });
        if (!predRes.ok) {
          if (mounted.current) {
            dispatch({ type: "reject", message: failureText(predRes.status, "prediction") });
          }
          return;
        }
        const prediction = (await predRes.json()) as FailurePredictionRead;
        const recRes = await fetch(recommendationEndpoint(prediction.id), {
          method: "POST",
          credentials: "same-origin",
          headers: JSON_HEADERS,
          body: "{}",
          signal: controller.signal,
        });
        if (!recRes.ok) {
          if (mounted.current) {
            dispatch({ type: "reject", message: failureText(recRes.status, "recommendation") });
          }
          return;
        }
        const recommendation = (await recRes.json()) as WorkerRecommendationRead;
        if (mounted.current) {
          dispatch({
            type: "resolve",
            data: { prediction, recommendation },
            stampedAt: recommendation.created_at,
          });
        }
      } catch (caught) {
        if ((caught as Error).name === "AbortError") {
          return;
        }
        if (mounted.current) {
          dispatch({ type: "reject", message: "Erkenntnis nicht abrufbar (Netz oder Backend)" });
        }
      }
    })();
  }, [machineId]);

  return { phase, trigger, busy: phase.kind === "processing" };
}
