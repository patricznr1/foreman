// FOREMAN Frontend — app/(app)/capture/page.tsx · Eingabe & Erfassung (J).
import { SectionPlaceholder } from "@/components/shell/section-placeholder";
import { requireSection } from "@/lib/auth/guard";

export default async function CapturePage() {
  await requireSection("J");
  return (
    <SectionPlaceholder
      title="Erfassung"
      note="Die Werker-Erfassung (Sektion J: reibungsarme Notiz mit vorbefüllter Zuordnung, Offline-Queue mit Sync-Status; Spracheingabe als Vision) folgt als eigener Prompt."
    />
  );
}
