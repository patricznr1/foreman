// ============================================================
//  FOREMAN Frontend — lib/api/overview-snapshot.ts
//  Zweck: Server-seitiger HTTP-Snapshot des Flotten-Lagebilds (/api/v1/overview)
//         als Erstbild für die Live-Sichten der Sektion A (Cockpit + 3D-Synoptik).
//         Eine Quelle, damit beide Routen denselben Snapshot-Fetch teilen. Fehlt
//         Token/Antwort, liefert die Funktion undefined (FiveState zeigt dann
//         „lädt"/Degradation) — kein harter Fehler.
//  Architektur-Einordnung: Server-Datenzugriff (Schicht 2, server-seitig).
// ============================================================
import type { FleetOverviewOut } from "@/lib/api/contracts";
import { backendUrl, getSessionToken } from "@/lib/auth/session";

/** Holt das Flotten-Lagebild als SSR-Erstbild; undefined, wenn nicht verfügbar. */
export async function fetchOverviewSnapshot(): Promise<FleetOverviewOut | undefined> {
  const token = await getSessionToken();
  if (token === null) {
    return undefined;
  }
  try {
    const response = await fetch(`${backendUrl()}/api/v1/overview`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
      // Hartes Zeitlimit: ein hängendes Backend darf das SSR-Rendering nicht blockieren
      // (Node ≥ 20). Timeout/Abort fällt unten in den catch → undefined → FiveState.
      signal: AbortSignal.timeout(5_000),
    });
    if (!response.ok) {
      return undefined;
    }
    return (await response.json()) as FleetOverviewOut;
  } catch {
    return undefined;
  }
}
