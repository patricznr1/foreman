// ============================================================
//  FOREMAN Frontend — lib/auth/guard.ts
//  Zweck: Server-seitiger Sektions-Guard. Die Sichtbarkeit ≤ Backend-Autorisierung
//         (default-deny): Direktaufruf einer nicht erlaubten Sektion leitet auf
//         das rollenspezifische Landing um. Das Frontend bypassed den Server nie.
//  Architektur-Einordnung: Auth-Guard (Schicht 1, server-seitig).
// ============================================================
import { redirect } from "next/navigation";
import type { CurrentUser } from "@/lib/api/contracts";
import { type SectionId, canAccessSection, landingRoute } from "./roles";
import { getCurrentUser } from "./session";

/** Stellt sicher, dass der angemeldete Nutzer die Sektion sehen darf. */
export async function requireSection(section: SectionId): Promise<CurrentUser> {
  const user = await getCurrentUser();
  if (user === null) {
    redirect("/login");
  }
  if (!canAccessSection(user.role, section)) {
    redirect(landingRoute(user.role));
  }
  return user;
}
