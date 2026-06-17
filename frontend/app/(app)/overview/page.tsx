// ============================================================
//  FOREMAN Frontend — app/(app)/overview/page.tsx
//  Zweck: Cockpit-Route (Sektion A). Server-seitig: Sektions-Guard (A — Manager/
//         Schichtleiter; Werker/Techniker → Landing) + Geltungsbereich aus den
//         Query-Parametern (?class=&line=) + HTTP-Snapshot als Erstbild. Die
//         Live-Aktualisierung übernimmt CockpitView per WS-Thema "overview".
//         Baut auf dem FE1-Übersicht-Durchstich auf (löst ihn als volle Sicht ab).
//  Architektur-Einordnung: Routen-Sicht (Schicht 2/3, server + client-View).
// ============================================================
import { CockpitView } from "@/components/cockpit/cockpit-view";
import type { FleetOverviewOut } from "@/lib/api/contracts";
import { requireSection } from "@/lib/auth/guard";
import { backendUrl, getSessionToken } from "@/lib/auth/session";
import { parseScope } from "@/lib/cockpit/scope";

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

export default async function OverviewPage({
  searchParams,
}: {
  searchParams: Promise<{ class?: string | string[]; line?: string | string[] }>;
}) {
  const user = await requireSection("A");
  const params = await searchParams;
  const scope = parseScope(params);
  const initialData = await fetchOverviewSnapshot();
  return <CockpitView user={user} scope={scope} initialData={initialData} />;
}
