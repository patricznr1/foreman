// ============================================================
//  FOREMAN Frontend — lib/ondemand/use-online.ts
//  Zweck: Ehrlicher Netz-Status für die On-Demand-Degradation (Studie §3.2): bei
//         Offline werden Trigger sichtbar deaktiviert MIT GRUND. Spiegelt
//         navigator.onLine plus online/offline-Events — geteilt von E und D/F/G/H.
//  Architektur-Einordnung: State-Anbindung (Schicht 1 ↔ React).
// ============================================================
"use client";

import { useEffect, useState } from "react";

export function useOnline(): boolean {
  const [online, setOnline] = useState(true);

  useEffect(() => {
    // Erstwert clientseitig (SSR kennt navigator nicht → Default true).
    if (typeof navigator !== "undefined" && typeof navigator.onLine === "boolean") {
      setOnline(navigator.onLine);
    }
    const goOnline = () => setOnline(true);
    const goOffline = () => setOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  return online;
}
