// ============================================================
//  FOREMAN Frontend — components/shell/global-status-bar.test.tsx
//  Zweck: Sichert die KERN-Konsistenz des Auftrags: das globale „Live"-Badge
//         spiegelt den ECHTEN Eingangs-Stream, nicht nur den WS-Transport. Steht
//         die Verbindung über rein statischer Historie (kein tickender Worker),
//         zeigt das Badge „Verlauf" — niemals „Live" (Verfassung: kein Etikett ohne
//         Strom). Tickt der Stream, wird es ehrlich „Live". Transport-agnostisch
//         über FakeTransport.
// ============================================================
import { act, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
  usePathname: () => "/overview",
}));

import type { CurrentUser, FleetOverviewOut } from "@/lib/api/contracts";
import { SessionProvider } from "@/lib/auth/use-session";
import { RealtimeProvider } from "@/lib/realtime/realtime-context";
import { RealtimeStore } from "@/lib/realtime/realtime-store";
import { FakeTransport } from "@/lib/realtime/testing/fake-transport";

import { GlobalStatusBar } from "./global-status-bar";

const MANAGER: CurrentUser = {
  id: 1,
  email: "m@x.de",
  role: "manager",
  assigned_line_ids: [],
  assigned_machine_ids: [],
};

function overviewWithStream(active: boolean, lastReadingAt: string | null): FleetOverviewOut {
  return {
    machines: [],
    by_status: { healthy: 0, drift_active: 0, open_warning: 0 },
    open_alarm_total: 0,
    stream: { active, last_reading_at: lastReadingAt },
  };
}

function setup() {
  const transport = new FakeTransport();
  const store = new RealtimeStore(transport);
  render(
    <SessionProvider user={MANAGER}>
      <RealtimeProvider store={store}>
        <GlobalStatusBar />
      </RealtimeProvider>
    </SessionProvider>,
  );
  return { transport };
}

describe("GlobalStatusBar — Live-Badge spiegelt den Eingangs-Stream", () => {
  it("zeigt 'Verlauf' (kein Live), wenn die Verbindung steht, aber kein Stream tickt", async () => {
    const { transport } = setup();
    act(() => {
      transport.emit("overview", overviewWithStream(false, "2026-06-25T12:30:00Z"));
    });
    expect(await screen.findByText(/Verlauf/)).toBeInTheDocument();
    // Genau der verbotene Fall: kein „Live" über statischer Historie.
    expect(screen.queryByText(/Live/)).toBeNull();
  });

  it("zeigt 'Live', wenn die Verbindung steht UND der Stream tickt", async () => {
    const { transport } = setup();
    act(() => {
      transport.emit("overview", overviewWithStream(true, "2026-06-25T12:30:00Z"));
    });
    expect(await screen.findByText(/Live/)).toBeInTheDocument();
  });
});
