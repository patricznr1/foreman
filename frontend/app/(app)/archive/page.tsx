// ============================================================
//  FOREMAN Frontend — app/(app)/archive/page.tsx · Archiv (Sektion H, Paket 1c).
//  Zweck: Server-Einstieg in die WÖRTLICHE Archiv-Suche über abgelegte
//         Schichtberichte, Wartungsprotokolle und Alarme. Guard auf Sektion H
//         (Werker/Schichtleiter/Techniker voll, Manager reduziert — alle dürfen
//         suchen). Nimmt einen Deep-Link der Befehlsleiste auf (?q=…) und gibt ihn
//         als Erst-Suche an die Sicht weiter (Cmd-K → H).
//  Architektur-Einordnung: Sektions-Route (Schicht 2, server).
// ============================================================
import { MemoryView } from "@/components/memory/memory-view";
import { requireSection } from "@/lib/auth/guard";

export default async function ArchivePage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string | string[]; quelle?: string | string[] }>;
}) {
  const user = await requireSection("H");
  const params = await searchParams;
  const raw = params.q;
  const query = typeof raw === "string" ? raw : Array.isArray(raw) ? raw[0] : undefined;
  // ?quelle=gedaechtnis — der Navigationseintrag "Hatten wir das schon mal" fragt
  // dieselbe Sektion, aber nur die vierte Quelle. Ein unbekannter Wert faellt still
  // auf die Vollsuche zurueck; die Seite darf an einem Adressparameter nicht scheitern.
  const rohQuelle = params.quelle;
  const quelle = typeof rohQuelle === "string" ? rohQuelle : rohQuelle?.[0];
  return (
    <MemoryView user={user} initialQuery={query} focusMemory={quelle === "gedaechtnis"} />
  );
}
