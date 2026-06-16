// FOREMAN Frontend — app/(app)/machines/page.tsx · Landing Werker/Techniker (B).
import { SectionPlaceholder } from "@/components/shell/section-placeholder";
import { requireSection } from "@/lib/auth/guard";

export default async function MachinesPage() {
  await requireSection("B");
  return (
    <SectionPlaceholder
      title="Linie & Maschinen"
      note="Die Maschinen-Detail-Sicht (Sektion B: Trends mit Normalband, Stammdaten, Wartungshistorie, Notizen) folgt als eigener Ausbauschritt auf diesem Fundament."
    />
  );
}
