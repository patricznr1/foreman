// FOREMAN Frontend — app/(app)/memory/page.tsx · Gedächtnis & Verknüpfung (H).
import { SectionPlaceholder } from "@/components/shell/section-placeholder";
import { requireSection } from "@/lib/auth/guard";

export default async function MemoryPage() {
  await requireSection("H");
  return (
    <SectionPlaceholder
      title="Gedächtnis"
      note="Die Bedeutungssuche (Sektion H: ähnliche Fälle über Maschinen, Klassen und Schichten — hatten wir das schon mal?) folgt als eigener Prompt. Erreichbar zusätzlich über die Befehlsleiste (Cmd-K)."
    />
  );
}
