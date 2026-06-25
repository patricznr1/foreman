// ============================================================
//  FOREMAN Frontend — app/(app)/synoptik/page.tsx
//  Zweck: Route der Live-3D-Linie (Sektion-A-Sub-Ansicht). Server-seitig:
//         Sektions-Guard (A — Manager/Schichtleiter; sonst rollenspezifisches
//         Landing) + HTTP-Snapshot von /overview als Erstbild. Die Live-
//         Aktualisierung übernimmt SynoptikView per WS-Thema "overview". Kein
//         eigener Nav-Eintrag — Einstieg über den Ansichts-Umschalter im Cockpit.
//  Architektur-Einordnung: Routen-Sicht (Schicht 2/3, server + client-View).
// ============================================================
import { SynoptikView } from "@/components/synoptik/synoptik-view";
import { fetchOverviewSnapshot } from "@/lib/api/overview-snapshot";
import { requireSection } from "@/lib/auth/guard";

export default async function SynoptikPage() {
  const user = await requireSection("A");
  const initialData = await fetchOverviewSnapshot();
  return <SynoptikView user={user} initialData={initialData} />;
}
