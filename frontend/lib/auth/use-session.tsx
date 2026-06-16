// ============================================================
//  FOREMAN Frontend — lib/auth/use-session.tsx
//  Zweck: Client-seitiger Zugriff auf die (server-seitig geladene) Session —
//         Rolle + Scope des angemeldeten Nutzers. Speist Rollen-Routing,
//         Navigations-Filter und Sichtbarkeit (Spiegel der Server-Authz).
//  Architektur-Einordnung: Auth-Anbindung (Schicht 1 ↔ React).
// ============================================================
"use client";

import { type ReactNode, createContext, useContext } from "react";
import type { CurrentUser } from "@/lib/api/contracts";

const SessionContext = createContext<CurrentUser | null>(null);

export function SessionProvider({ user, children }: { user: CurrentUser; children: ReactNode }) {
  return <SessionContext.Provider value={user}>{children}</SessionContext.Provider>;
}

export function useSession(): CurrentUser {
  const user = useContext(SessionContext);
  if (user === null) {
    throw new Error("useSession muss innerhalb von <SessionProvider> verwendet werden.");
  }
  return user;
}

export function useOptionalSession(): CurrentUser | null {
  return useContext(SessionContext);
}
