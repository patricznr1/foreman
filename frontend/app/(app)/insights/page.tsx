// FOREMAN Frontend — app/(app)/insights/page.tsx · Erkenntnisse (D/E/F/G).
import { SectionPlaceholder } from "@/components/shell/section-placeholder";
import { requireSection } from "@/lib/auth/guard";

export default async function InsightsPage() {
  await requireSection("E");
  return (
    <SectionPlaceholder
      title="Erkenntnisse"
      note="Die On-Demand-Reasoner (Ereignisketten D, Ausfallvorhersage & Empfehlung E mit untrennbarem Simulations-Vorbehalt, Wartung F, Belastungs-Simulation G) folgen als eigene Prompts — alle nach dem Muster Trigger → Herkunft → Vorbehalt."
    />
  );
}
