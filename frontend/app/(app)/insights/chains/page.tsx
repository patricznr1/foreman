// ============================================================
//  FOREMAN Frontend — app/(app)/insights/chains/page.tsx
//  Zweck: Server-Einstieg in Sektion D (Ereignisketten, [STEHT]). Erzwingt die
//         Sektions-Berechtigung (Guard, default-deny, Sichtbarkeit ≤ Server-
//         Autorisierung) und liest den Anker-Alarm (?anchor, Querlink aus C/B) und
//         den Maschinen-Filter (?machine, aus B) server-seitig — kein useSearchParams.
//         Die Rollen-Variante (Schichtleiter triggert / Techniker liest+pinnt /
//         Werker liest / Manager Aggregat) entscheidet die Client-Sicht selbst.
//  Architektur-Einordnung: Sektions-Route (Schicht 2, server).
// ============================================================
import { ChainsView } from "@/components/event-chains/chains-view";
import { requireSection } from "@/lib/auth/guard";

/** Liest eine positive Ganzzahl aus einem Query-Parameter (sonst null). */
function parseId(value: string | string[] | undefined): number | null {
  const raw = Array.isArray(value) ? value[0] : value;
  if (raw === undefined) {
    return null;
  }
  const parsed = Number(raw);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : null;
}

export default async function ChainsPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const user = await requireSection("D");
  const params = await searchParams;
  return (
    <ChainsView
      user={user}
      anchorAlarmId={parseId(params.anchor)}
      machineId={parseId(params.machine)}
      initialExplanationId={parseId(params.explanation)}
    />
  );
}
