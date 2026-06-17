// ============================================================
//  FOREMAN Frontend — app/page.tsx
//  Zweck: Einstieg — leitet auf das rollenspezifische Landing (§3.3) bzw. /login.
//  Architektur-Einordnung: Routen-Einstieg (Schicht 2, server).
// ============================================================
import { redirect } from "next/navigation";
import { landingRoute } from "@/lib/auth/roles";
import { getCurrentUser } from "@/lib/auth/session";

export default async function Home() {
  const user = await getCurrentUser();
  redirect(user ? landingRoute(user.role) : "/login");
}
