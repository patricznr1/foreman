// ============================================================
//  FOREMAN Frontend — lib/capture/use-machines.ts
//  Zweck: Die für den Nutzer wählbaren Maschinen laden (GET /api/v1/machines über
//         den BFF) und auf den Scope filtern (UX-Führung, keine AuthZ-Grenze, §20).
//         Trägt die fünf Pflichtzustände an der Maschinen-Auswahl: lädt → bereit /
//         leer / Fehler. Das Freitextfeld der Erfassung ist davon unabhängig sofort
//         nutzbar (die Auswahl lädt nebenher).
//  Architektur-Einordnung: State-Anbindung (Schicht 1 ↔ React).
// ============================================================
"use client";

import { useEffect, useState } from "react";
import type { CurrentUser, MachineRead } from "@/lib/api/contracts";
import { selectableMachines } from "./scope";

export type MachinesState =
  | { kind: "loading" }
  | { kind: "ready"; machines: MachineRead[] }
  | { kind: "empty" } // keine zugewiesene Maschine im Scope
  | { kind: "error" };

const MACHINES_URL = "/api/v1/machines?limit=1000";

/** `enabled=false` (z. B. Manager: liest, erfasst nicht) lädt NICHT — kein
 *  überflüssiger Request; der Hook wird trotzdem immer aufgerufen (keine bedingten
 *  Hooks), die Rollen-Verzweigung passiert auf Komponenten-Ebene. */
export function useSelectableMachines(user: CurrentUser, enabled = true): MachinesState {
  const [state, setState] = useState<MachinesState>(enabled ? { kind: "loading" } : { kind: "empty" });

  useEffect(() => {
    if (!enabled) {
      return;
    }
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
        const all = (await response.json()) as MachineRead[];
        const machines = selectableMachines(user, all);
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
  }, [user, enabled]);

  return state;
}
