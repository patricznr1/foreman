// ============================================================
//  FOREMAN Frontend — lib/capture/use-outbox.ts
//  Zweck: Die Offline-Queue beobachten und bei Netz-Rückkehr flushen. Pro Item:
//         POST; bei Erfolg ODER hartem Fehler aus der Queue entfernen
//         (Lösch-nach-Senden = Datenschutz-Hebel, §8); bei transientem Fehler
//         belassen (nächster Flush versucht erneut). Reentry-geschützt.
//  Architektur-Einordnung: State-Anbindung (Schicht 1 ↔ React).
// ============================================================
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { outboxCount, readOutbox, removeFromOutbox } from "./outbox";
import { submitNote } from "./submit";

export interface UseOutboxResult {
  /** Anzahl noch ausstehender (lokal gepufferter) Notizen. */
  pending: number;
  /** Ein Flush läuft gerade. */
  flushing: boolean;
  /** Der letzte Flush ließ Notizen transient liegen (bleiben gepuffert). */
  hadError: boolean;
  /** Sendet die Queue ab (manuell oder via Effekt bei online). */
  flush: () => Promise<void>;
  /** Liest den Zähler neu (z. B. nachdem die View frisch gepuffert hat). */
  refresh: () => void;
}

export function useOutbox(online: boolean): UseOutboxResult {
  const [pending, setPending] = useState(0);
  const [flushing, setFlushing] = useState(false);
  const [hadError, setHadError] = useState(false);
  const flushingRef = useRef(false);

  const refresh = useCallback(() => {
    setPending(outboxCount());
  }, []);

  const flush = useCallback(async () => {
    // Reentry-Schutz: kein paralleler Flush (online-Effekt + manueller Aufruf).
    if (flushingRef.current) {
      return;
    }
    flushingRef.current = true;
    setFlushing(true);
    try {
      let transient = false;
      for (const item of readOutbox()) {
        const outcome = await submitNote(item.payload);
        if (outcome.ok) {
          removeFromOutbox(item.localId); // Lösch-nach-Senden (kein Klartext bleibt)
        } else if (outcome.reason === "error") {
          transient = true; // 5xx/Netz → behalten, später erneut
        } else {
          removeFromOutbox(item.localId); // hart (422/401/403) → nicht endlos retryen
        }
      }
      setHadError(transient);
    } finally {
      flushingRef.current = false;
      setFlushing(false);
      setPending(outboxCount());
    }
  }, []);

  // Erstwert beim Mount (eine offline geschriebene Notiz kann den Reload überlebt haben).
  useEffect(() => {
    refresh();
  }, [refresh]);

  // Netz da → versuchen zu senden (offline→online-Übergang ist der Aufhänger).
  useEffect(() => {
    if (online) {
      void flush();
    }
  }, [online, flush]);

  return { pending, flushing, hadError, flush, refresh };
}
