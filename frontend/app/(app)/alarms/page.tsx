// ============================================================
//  FOREMAN Frontend — app/(app)/alarms/page.tsx · Alarme (Sektion C, [STEHT]).
//  Zweck: Server-Einstieg. Erzwingt die Sektions-Berechtigung (Guard, default-deny,
//         Sichtbarkeit ≤ Server-Autorisierung) und übergibt Rolle/Scope an die
//         Client-Sicht. Die Rollen-Variante (Werker/Schichtleiter/Techniker/Manager)
//         entscheidet die Sicht selbst.
//  Architektur-Einordnung: Sektions-Route (Schicht 2, server).
// ============================================================
import { AlarmsView } from "@/components/alarms/alarms-view";
import { requireSection } from "@/lib/auth/guard";

export default async function AlarmsPage() {
  const user = await requireSection("C");
  return <AlarmsView user={user} />;
}
