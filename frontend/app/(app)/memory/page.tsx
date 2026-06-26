// ============================================================
//  FOREMAN Frontend — app/(app)/memory/page.tsx · Redirect → /archive (Paket 1c).
//  Zweck: Die Sektion „Gedächtnis" (Route /memory) wurde ehrlich zum „Archiv"
//         umgewidmet. Bestehende Deep-Links/Lesezeichen (?q=…) werden dauerhaft auf
//         /archive umgeleitet — der Such-Parameter bleibt erhalten. Das Sektions-
//         Gate (H) sitzt auf der Zielroute /archive.
//  Architektur-Einordnung: Sektions-Route (Schicht 2, server).
// ============================================================
import { redirect } from "next/navigation";

export default async function MemoryPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string | string[] }>;
}) {
  const params = await searchParams;
  const raw = params.q;
  const query = typeof raw === "string" ? raw : Array.isArray(raw) ? raw[0] : undefined;
  redirect(query ? `/archive?q=${encodeURIComponent(query)}` : "/archive");
}
