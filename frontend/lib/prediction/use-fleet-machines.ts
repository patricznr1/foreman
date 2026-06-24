// ============================================================
//  FOREMAN Frontend — lib/prediction/use-fleet-machines.ts
//  Zweck: Lädt die ganze Flotte (GET /api/v1/machines über den BFF) als Auswahl-
//         quelle der Manager-Vorhersage. Der Werksleiter hat KEINE zugewiesene
//         Maschine (assigned_machine_ids leer), sieht im Vollzugriff aber alle
//         (§21.10). On-Demand-Pull (E ist eine Pull-Sektion, kein WS) → kein
//         RealtimeProvider nötig. Fünf-Zustände an der Auswahl.
//  Architektur-Einordnung: State-Anbindung (Schicht 1 ↔ React). Sektions-eigen,
//         keine capture-Scope-Kopplung (manager = Vollzugriff, keine Filterung).
// ============================================================
"use client";

import { useEffect, useState } from "react";
import type { MachineRead } from "@/lib/api/contracts";

export type FleetMachinesState =
  | { kind: "loading" }
  | { kind: "ready"; machines: MachineRead[] }
  | { kind: "empty" }
  | { kind: "error" };

const MACHINES_URL = "/api/v1/machines?limit=1000";

/** Lädt die Flotte für die Manager-Vorhersage-Auswahl (Vollzugriff, ungefiltert). */
export function useFleetMachines(): FleetMachinesState {
  const [state, setState] = useState<FleetMachinesState>({ kind: "loading" });

  useEffect(() => {
    let active = true;
    const controller = new AbortController();
    void (async () => {
      try {
        const response = await fetch(MACHINES_URL, {
          credentials: "same-origin",
          signal: controller.signal,
        });
        if (!response.ok) {
          if (active) {
            setState({ kind: "error" });
          }
          return;
        }
        const machines = (await response.json()) as MachineRead[];
        if (active) {
          setState(machines.length === 0 ? { kind: "empty" } : { kind: "ready", machines });
        }
      } catch (caught) {
        if ((caught as Error).name === "AbortError") {
          return;
        }
        if (active) {
          setState({ kind: "error" });
        }
      }
    })();
    return () => {
      active = false;
      controller.abort();
    };
  }, []);

  return state;
}
