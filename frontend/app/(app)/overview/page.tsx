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
import { fetchOverviewSnapshot } from "@/lib/api/overview-snapshot";
import { requireSection } from "@/lib/auth/guard";
import { parseScope } from "@/lib/cockpit/scope";

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
