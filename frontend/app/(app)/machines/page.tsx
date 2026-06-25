// ============================================================
//  FOREMAN Frontend — app/(app)/machines/page.tsx
//  Zweck: Maschinen-Übersicht (Sektion B, Landing für Werker/Techniker). Server-Guard
//         (requireSection B, default-deny) + scope-korrekter SSR-Pull der lebenden
//         Maschinenkarten (GET /api/v1/cards — serverseitig nach Rolle gefiltert:
//         Werker → eigene Maschinen, Schichtleiter → Linien-Maschinen, Manager/
//         Techniker → alle). Das Karten-Grid ersetzt die bisherigen Listen-Reiter.
//  Architektur-Einordnung: Sektions-Route (Schicht 2, server).
// ============================================================
import { MachineCardGrid } from "@/components/machine/machine-card-grid";
import type { MachineCardOut } from "@/lib/api/contracts";
import { requireSection } from "@/lib/auth/guard";
import { backendUrl, getSessionToken } from "@/lib/auth/session";

async function fetchCards(): Promise<MachineCardOut[]> {
  const token = await getSessionToken();
  if (token === null) {
    return [];
  }
  try {
    const response = await fetch(`${backendUrl()}/api/v1/cards`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!response.ok) {
      // Ehrlich: ein Backend-Fehler ist KEIN leerer Scope — serverseitig loggen,
      // damit „keine Maschinen" nicht stillschweigend einen Ausfall verdeckt.
      console.error(`Kartenliste: /api/v1/cards antwortete mit ${response.status}`);
      return [];
    }
    return (await response.json()) as MachineCardOut[];
  } catch (error) {
    console.error("Kartenliste: Anfrage an /api/v1/cards fehlgeschlagen", error);
    return [];
  }
}

export default async function MachinesPage() {
  await requireSection("B");
  const cards = await fetchCards();
  return (
    <section aria-label="Linie & Maschinen" className="flex flex-col gap-4">
      <h1 className="text-h1 text-fg-primary">Linie &amp; Maschinen</h1>
      <MachineCardGrid cards={cards} />
    </section>
  );
}
