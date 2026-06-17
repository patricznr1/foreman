// FOREMAN Frontend — app/(app)/capture/page.tsx · Eingabe & Erfassung (J).
// Liest die Kontext-Vorauswahl ?machine= (aus B/Alarm/QuickCaptureFab) — Muster wie
// /memory (?q=): Next 15 reicht searchParams als Promise, server-seitig normalisiert,
// als initialMachineId an die Client-View. Ungültige/fremde IDs behandelt die View
// graceful (keine Vorauswahl). Server-Guard requireSection("J") bleibt erste Zeile.
import { CaptureView } from "@/components/capture/capture-view";
import { requireSection } from "@/lib/auth/guard";

export default async function CapturePage({
  searchParams,
}: {
  searchParams: Promise<{ machine?: string | string[] }>;
}) {
  const user = await requireSection("J");
  const params = await searchParams;
  const raw = params.machine;
  const value = typeof raw === "string" ? raw : Array.isArray(raw) ? raw[0] : undefined;
  const parsed = value ? Number(value) : Number.NaN;
  const initialMachineId = Number.isInteger(parsed) && parsed > 0 ? parsed : null;
  return <CaptureView user={user} initialMachineId={initialMachineId} />;
}
