// FOREMAN Frontend — app/(app)/alarms/page.tsx · Alarme (C).
import { SectionPlaceholder } from "@/components/shell/section-placeholder";
import { requireSection } from "@/lib/auth/guard";

export default async function AlarmsPage() {
  await requireSection("C");
  return (
    <SectionPlaceholder
      title="Alarme & Warnungen"
      note="Die Alarm-Sicht (Sektion C: ISA-18.2-gestaffelte Prioritäten, HITL-Quittierung, Drift-Warnungen) folgt als eigener Prompt — eine der [STEHT]-Sichten mit höchstem Sofort-Wert."
    />
  );
}
