// ============================================================
//  FOREMAN Frontend — app/(app)/machines/page.tsx
//  Zweck: Maschinen-Übersicht (Sektion B, Landing für Werker/Techniker). Server-Guard
//         (requireSection B, default-deny) + scope-korrekter SSR-Pull der Maschinen
//         (Sichtbarkeit ≤ Server-Autorisierung: Werker → eigene Maschinen, Schichtleiter
//         → Linien-Maschinen, Manager/Techniker → alle). Einstieg in die Detail-Sicht.
//  Architektur-Einordnung: Sektions-Route (Schicht 2, server).
// ============================================================
import { MachineList } from "@/components/machine/machine-list";
import type { CurrentUser, MachineRead } from "@/lib/api/contracts";
import { requireSection } from "@/lib/auth/guard";
import { backendUrl, getSessionToken } from "@/lib/auth/session";

async function fetchMachines(): Promise<MachineRead[]> {
  const token = await getSessionToken();
  if (token === null) {
    return [];
  }
  try {
    const response = await fetch(`${backendUrl()}/api/v1/machines?limit=1000`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!response.ok) {
      return [];
    }
    return (await response.json()) as MachineRead[];
  } catch {
    return [];
  }
}

// Client-seitiger Scope-Spiegel (GET /machines ist nicht scope-gefiltert — die echte
// AuthZ-Grenze hält das Backend auf den Live-/Trend-Themen, §20.4; hier UX-Filter).
function inScope(user: CurrentUser, machine: MachineRead): boolean {
  if (user.role === "manager" || user.role === "technician") {
    return true;
  }
  if (user.role === "worker") {
    return user.assigned_machine_ids.includes(machine.id);
  }
  if (user.role === "shift_lead") {
    return machine.line_id !== null && user.assigned_line_ids.includes(machine.line_id);
  }
  return false;
}

export default async function MachinesPage() {
  const user = await requireSection("B");
  const machines = (await fetchMachines()).filter((machine) => inScope(user, machine));
  return <MachineList machines={machines} />;
}
