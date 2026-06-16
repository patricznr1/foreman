// ============================================================
//  FOREMAN Frontend — app/(app)/overview/page.tsx
//  Zweck: Übersicht-Route (vertikaler Durchstich). Server-seitig: Sektions-Guard
//         (A — Manager/Schichtleiter; Werker/Techniker → Landing) + HTTP-Snapshot
//         als Erstbild. Die Live-Aktualisierung übernimmt OverviewView per WS.
//  Architektur-Einordnung: Routen-Sicht (Schicht 2/3, server + client-View).
// ============================================================
import type { FleetOverviewOut } from "@/lib/api/contracts";
import { requireSection } from "@/lib/auth/guard";
import { backendUrl, getSessionToken } from "@/lib/auth/session";
import { OverviewView } from "@/views/overview/overview-view";

async function fetchOverviewSnapshot(): Promise<FleetOverviewOut | undefined> {
  const token = await getSessionToken();
  if (token === null) {
    return undefined;
  }
  try {
    const response = await fetch(`${backendUrl()}/api/v1/overview`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!response.ok) {
      return undefined;
    }
    return (await response.json()) as FleetOverviewOut;
  } catch {
    return undefined;
  }
}

export default async function OverviewPage() {
  await requireSection("A");
  const initialData = await fetchOverviewSnapshot();
  return <OverviewView initialData={initialData} />;
}
