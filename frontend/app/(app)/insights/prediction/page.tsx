// ============================================================
//  FOREMAN Frontend — app/(app)/insights/prediction/page.tsx
//  Zweck: Server-Einstieg in Sektion E (Ausfallvorhersage & Empfehlung, [STEHT]).
//         Erzwingt die Sektions-Berechtigung (Guard, default-deny, Sichtbarkeit
//         ≤ Server-Autorisierung) und übergibt Rolle/Scope an die Client-Sicht.
//         Die Rollen-Variante (Werker liest / Schichtleiter triggert+quittiert /
//         Techniker Faktor-Detail / Manager Aggregat) entscheidet die Sicht selbst.
//  Architektur-Einordnung: Sektions-Route (Schicht 2, server).
// ============================================================
import { PredictionView } from "@/components/prediction/prediction-view";
import { requireSection } from "@/lib/auth/guard";

export default async function PredictionPage() {
  const user = await requireSection("E");
  return <PredictionView user={user} />;
}
