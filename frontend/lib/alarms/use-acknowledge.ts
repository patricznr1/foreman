// ============================================================
//  FOREMAN Frontend — lib/alarms/use-acknowledge.ts
//  Zweck: HITL-Quittierung über den BFF-Proxy. Sendet AUSSCHLIESSLICH den
//         Alarm-Status-Pfad (.../acknowledge) — die Sicherheits-Invariante wird
//         VOR dem Senden geprüft (kein Anlagen-Schreibpfad, niemals). Der reale
//         Drift-Quittier-Endpunkt nimmt KEINEN Body (acknowledged_by entsteht
//         server-seitig aus der Session, §8); die Pflicht-Begründung wird
//         client-seitig für den HITL-/Audit-Bezug geführt (Persistenz der
//         Begründung = Anschlusspunkt Sektion I).
//  Architektur-Einordnung: State-Anbindung (Schicht 1 ↔ React).
// ============================================================
"use client";

import { useCallback, useState } from "react";
import type { AlarmRead } from "@/lib/api/contracts";
import { acknowledgeEndpoint, isAlarmStatusActionPath } from "./acknowledge";
import type { AlarmViewModel } from "./types";

export type AcknowledgeResult =
  | { ok: true; alarm: AlarmRead }
  // `forbidden`/`unauthorized` sind HARTE Grenzen (nicht durch Retry behebbar);
  // `error` ist transient (5xx/Netz) und darf zum erneuten Versuch einladen.
  | {
      ok: false;
      reason: "no-route" | "blocked" | "forbidden" | "unauthorized" | "error";
      status?: number;
    };

export interface UseAcknowledgeResult {
  /** Optionaler `reason` = auditierbarer Pflicht-Kontext (bei kritisch erzwungen). */
  acknowledge: (vm: AlarmViewModel, reason?: string | null) => Promise<AcknowledgeResult>;
  /** ID des gerade laufenden Quittier-Vorgangs (für die Button-Sperre). */
  pending: number | null;
}

export function useAcknowledge(): UseAcknowledgeResult {
  const [pending, setPending] = useState<number | null>(null);

  const acknowledge = useCallback(
    async (vm: AlarmViewModel, reason?: string | null): Promise<AcknowledgeResult> => {
      const endpoint = acknowledgeEndpoint(vm);
      if (endpoint === null) {
        return { ok: false, reason: "no-route" };
      }
      // SICHERHEITS-INVARIANTE (HITL): nur ein erlaubter Status-Pfad verlässt das
      // Frontend. Jeder andere Pfad wird hier hart geblockt, bevor irgendetwas geht.
      if (!isAlarmStatusActionPath(endpoint)) {
        return { ok: false, reason: "blocked" };
      }
      setPending(vm.id);
      // Begründung forward-compatible mitsenden: die heutige Drift-Route nimmt keinen
      // Body und ignoriert das Feld; eine künftige generische Route nimmt es an.
      const trimmed = reason?.trim();
      try {
        const response = await fetch(endpoint, {
          method: "POST",
          credentials: "same-origin",
          headers: { "content-type": "application/json" },
          body: trimmed ? JSON.stringify({ reason: trimmed }) : "{}",
        });
        if (!response.ok) {
          // Konsistent mit dem Lese-Hook (use-alarms): AuthZ-Ablehnungen sind hart.
          if (response.status === 403) {
            return { ok: false, reason: "forbidden", status: 403 };
          }
          if (response.status === 401) {
            return { ok: false, reason: "unauthorized", status: 401 };
          }
          return { ok: false, reason: "error", status: response.status };
        }
        const alarm = (await response.json()) as AlarmRead;
        return { ok: true, alarm };
      } catch {
        return { ok: false, reason: "error" };
      } finally {
        setPending(null);
      }
    },
    [],
  );

  return { acknowledge, pending };
}
