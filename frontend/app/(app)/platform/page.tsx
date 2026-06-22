// ============================================================
//  FOREMAN Frontend — app/(app)/platform/page.tsx
//  Zweck: Server-Einstieg in Sektion I (Plattform/Audit, [BACKEND STEHT] · §21.16).
//         Erzwingt die Sektions-Berechtigung (Guard, default-deny, Sichtbarkeit ≤
//         Server-Autorisierung): Werker/Techniker landen auf ihrer Sicht, ohne
//         Session → /login. Manager/Schichtleiter erhalten die Client-Ansicht; die
//         Rollen-Variante (Manager voll / Schichtleiter nur Topologie) entscheidet
//         die Ansicht selbst. Kein searchParams-Deep-Link in dieser Sektion.
//  Architektur-Einordnung: Sektions-Route (Schicht 2, server).
// ============================================================
import { PlatformView } from "@/components/platform/platform-view";
import { requireSection } from "@/lib/auth/guard";

export default async function PlatformPage() {
  const user = await requireSection("I");
  return <PlatformView user={user} />;
}
