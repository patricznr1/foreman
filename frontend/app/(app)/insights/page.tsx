// ============================================================
//  FOREMAN Frontend — app/(app)/insights/page.tsx · Erkenntnisse-Dach (D/E/F/G).
//  Zweck: Server-Einstieg in die On-Demand-Reasoner. Guard auf Sektion E (alle
//         Rollen mit Erkenntnis-Zugang haben E-Zugriff); zeigt den Hub mit der
//         Sekundärnavigation. E ist live, D/F/G folgen graceful.
//  Architektur-Einordnung: Sektions-Route (Schicht 2, server).
// ============================================================
import { InsightsHub } from "@/components/insights/insights-hub";
import { requireSection } from "@/lib/auth/guard";

export default async function InsightsPage() {
  await requireSection("E");
  return <InsightsHub />;
}
