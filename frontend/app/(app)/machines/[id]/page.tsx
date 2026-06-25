// ============================================================
//  FOREMAN Frontend — app/(app)/machines/[id]/page.tsx
//  Zweck: Maschinen-Detail-Sicht (Sektion B, [KERN]). Server-Guard (requireSection B)
//         + EIN scope-genauer SSR-Pull der lebenden Maschinenkarte
//         (GET /machines/{id}/card) als einzige Quelle: Steckbrief + Komponenten +
//         Datenpunkte mit aktuellem Wert/Status. Die Detail-Sub-Sichten (Kopf, Trend,
//         Alarme) leiten ihre Stammdaten-Form dünn aus der Karte ab (kein Zweit-Fetch);
//         der Sensortrend lädt seine Kurven weiterhin live im Client. Fehlende oder
//         nicht zugreifbare Maschine (out-of-scope → 403) → freundlicher Hinweis.
//  Architektur-Einordnung: Sektions-Route (Schicht 2, server).
// ============================================================
import { MachineDetailView } from "@/components/machine/machine-detail-view";
import type { DataPointRead, MachineCardOut, MachineRead } from "@/lib/api/contracts";
import { requireSection } from "@/lib/auth/guard";
import { backendUrl, getSessionToken } from "@/lib/auth/session";

async function fetchCard(machineId: number): Promise<MachineCardOut | null> {
  const token = await getSessionToken();
  if (token === null) {
    return null;
  }
  try {
    const response = await fetch(`${backendUrl()}/api/v1/machines/${machineId}/card`, {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!response.ok) {
      return null;
    }
    return (await response.json()) as MachineCardOut;
  } catch {
    return null;
  }
}

// Dünne Form-Adapter: die lebende Karte ist die EINE Quelle; Kopf/Trend/Alarme
// erwarten noch die Stammdaten-Form. Die von der Karte nicht getragenen Felder
// (source/address/created_at) sind in diesen Sichten ungenutzt — neutral gefüllt,
// nicht erfunden angezeigt.
function toMachineRead(card: MachineCardOut): MachineRead {
  return {
    id: card.id,
    line_id: card.line_id,
    external_id: card.external_id,
    label: card.label,
    machine_class: card.machine_class,
    manufacturer: card.manufacturer,
    location: card.location,
    created_at: "",
  };
}

function toDataPointReads(card: MachineCardOut): DataPointRead[] {
  return card.data_points.map((dp) => ({
    id: dp.id,
    machine_id: card.id,
    component_id: dp.component_id,
    name: dp.name,
    // Das Backend garantiert eine gültige Datenpunkt-Art (DB-Validierung) — die Karte
    // führt sie nur als string; hier auf das engere Vertrags-Literal eingeengt.
    kind: dp.kind as DataPointRead["kind"],
    measurement_type: dp.measurement_type,
    unit: dp.unit,
    source: null,
    address: null,
    normal_min: dp.normal_min,
    normal_max: dp.normal_max,
    created_at: "",
  }));
}

export default async function MachineDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const user = await requireSection("B");
  const { id } = await params;
  const machineId = Number(id);

  const card =
    Number.isInteger(machineId) && machineId > 0 ? await fetchCard(machineId) : null;

  if (card === null) {
    return (
      <section
        aria-label="Maschine nicht gefunden"
        className="flex flex-col gap-2 rounded-lg border border-line-subtle bg-surface-raised p-6"
      >
        <h1 className="text-h1 text-fg-primary">Maschine nicht gefunden</h1>
        <p className="text-body text-fg-secondary">
          Diese Maschine existiert nicht oder ist nicht in deinem Zugriff. Zurück zur
          Maschinen-Übersicht.
        </p>
      </section>
    );
  }

  return (
    <MachineDetailView
      user={user}
      machine={toMachineRead(card)}
      dataPoints={toDataPointReads(card)}
      card={card}
    />
  );
}
