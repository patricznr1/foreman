// ============================================================
//  FOREMAN Frontend — app/(app)/layout.tsx
//  Zweck: Authentifizierter Bereich. Lädt die Session server-seitig (GET /me),
//         leitet ohne gültige Sitzung zu /login, und spannt SessionProvider +
//         RealtimeProvider + AppShell um die Sicht. Rolle/Scope stammen aus dem
//         Backend (Spiegel der Server-Autorisierung).
//  Architektur-Einordnung: Bereichs-Layout (Schicht 2, server + client-Provider).
// ============================================================
import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/shell/app-shell";
import { getCurrentUser } from "@/lib/auth/session";
import { SessionProvider } from "@/lib/auth/use-session";
import { RealtimeProvider } from "@/lib/realtime/realtime-context";

export default async function AppLayout({ children }: { children: ReactNode }) {
  const user = await getCurrentUser();
  if (user === null) {
    redirect("/login");
  }
  return (
    <SessionProvider user={user}>
      <RealtimeProvider>
        <AppShell>{children}</AppShell>
      </RealtimeProvider>
    </SessionProvider>
  );
}
