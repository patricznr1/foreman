// FOREMAN Frontend — app/(app)/platform/page.tsx · Integration/Plattform (I).
import { SectionPlaceholder } from "@/components/shell/section-placeholder";
import { requireSection } from "@/lib/auth/guard";

export default async function PlatformPage() {
  await requireSection("I");
  return (
    <SectionPlaceholder
      title="Plattform"
      note="Die Integrations-/Plattformsicht (Sektion I: Systemtopologie + unveränderlicher Audit-Trail) folgt als eigener Prompt. Nur Manager (voll) und Schichtleiter (lesend)."
    />
  );
}
