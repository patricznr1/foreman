// ============================================================
//  FOREMAN Frontend — app/(app)/machines/[id]/page.tsx
//  Zweck: Maschinen-Detail-Sicht (Sektion B, [KERN]). Server-Guard (requireSection B)
//         + SSR-Erstbild der Stammdaten/Komponenten/Datenpunkte; die Sicht selbst
//         (Trend live, Historie/Alarme Pull) übernimmt der Client. Fehlende Maschine
//         → freundlicher Hinweis (kein weißer Schirm). Die scope-genaue Live-Grenze
//         hält das Backend auf den WS-/Trend-Themen (§20.4) — fremde Maschine → die
//         Trend-/Alarm-Panels zeigen den Forbidden-Zustand.
//  Architektur-Einordnung: Sektions-Route (Schicht 2, server).
// ============================================================
import { MachineDetailView } from "@/components/machine/machine-detail-view";
import type { ComponentRead, DataPointRead, MachineRead } from "@/lib/api/contracts";
import { requireSection } from "@/lib/auth/guard";
import { backendUrl, getSessionToken } from "@/lib/auth/session";

async function authedJson<T>(path: string): Promise<T | null> {
  const token = await getSessionToken();
  if (token === null) {
    return null;
  }
  try {
    const response = await fetch(`${backendUrl()}${path}`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

export default async function MachineDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const user = await requireSection("B");
  const { id } = await params;
  const machineId = Number(id);

  const machine =
    Number.isInteger(machineId) && machineId > 0
      ? await authedJson<MachineRead>(`/api/v1/machines/${machineId}`)
      : null;

  if (machine === null) {
    return (
      <section
        aria-label="Maschine nicht gefunden"
        className="flex flex-col gap-2 rounded-lg border border-line-subtle bg-surface-raised p-6"
      >
        <h1 className="text-h1 text-fg-primary">Maschine nicht gefunden</h1>
        <p className="text-body text-fg-secondary">
          Diese Maschine existiert nicht oder ist nicht abrufbar. Zurück zur Maschinen-Übersicht.
        </p>
      </section>
    );
  }

  const [components, dataPoints] = await Promise.all([
    authedJson<ComponentRead[]>(`/api/v1/components?machine_id=${machineId}`),
    authedJson<DataPointRead[]>(`/api/v1/data_points?machine_id=${machineId}`),
  ]);

  return (
    <MachineDetailView
      user={user}
      machine={machine}
      components={components ?? []}
      dataPoints={dataPoints ?? []}
    />
  );
}
