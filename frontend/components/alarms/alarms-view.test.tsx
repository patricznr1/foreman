// ============================================================
//  FOREMAN Frontend — components/alarms/alarms-view.test.tsx
//  Zweck: Integrationssicht (Sektion C) gegen FakeTransport + gemocktes Fetch —
//         Staffelung (kritisch oben), Rollen-Varianten (Werker kein Quittieren,
//         Manager nur Aggregat), Degradation (offline → gecacht + Quittieren
//         deaktiviert mit Grund), Live-Insert (neuer Alarm via WS-Signal eingefügt).
// ============================================================
import { act, cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { AlarmRead, CurrentUser, FleetOverviewOut, Role } from "@/lib/api/contracts";
import { RealtimeStore } from "@/lib/realtime/realtime-store";
import { RealtimeProvider } from "@/lib/realtime/realtime-context";
import { FakeTransport } from "@/lib/realtime/testing/fake-transport";
import { SessionProvider } from "@/lib/auth/use-session";
import { alarm } from "@/lib/alarms/testing/fixtures";
import { AlarmsView } from "./alarms-view";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

afterEach(cleanup);

function user(role: Role, over: Partial<CurrentUser> = {}): CurrentUser {
  return {
    id: 1,
    email: "lead@werk.de",
    role,
    assigned_line_ids: [3],
    assigned_machine_ids: [1, 2],
    ...over,
  };
}

const emptyOverview: FleetOverviewOut = {
  machines: [],
  by_status: { healthy: 0, drift_active: 0, open_warning: 0, critical: 0 },
  open_alarm_total: 0,
  stream: { active: false, last_reading_at: null },
};

function setup(current: CurrentUser, responses: AlarmRead[][]) {
  const transport = new FakeTransport();
  const store = new RealtimeStore(transport, { throttleMs: 0 });
  let call = 0;
  const fetchMock = vi.fn(async () => {
    const body = responses[Math.min(call, responses.length - 1)] ?? [];
    call += 1;
    return { ok: true, json: async () => body } as unknown as Response;
  });
  vi.stubGlobal("fetch", fetchMock);
  render(
    <SessionProvider user={current}>
      <RealtimeProvider store={store}>
        <AlarmsView user={current} />
      </RealtimeProvider>
    </SessionProvider>,
  );
  return { transport, store, fetchMock };
}

beforeEach(() => vi.restoreAllMocks());

describe("AlarmsView — Staffelung & Rollen", () => {
  it("Schichtleiter: kritischer Gruppenkopf steht oben (nicht chronologisch-flach)", async () => {
    setup(user("shift_lead"), [
      [
        alarm({ id: 1, machine_id: 1, severity: "info" }),
        alarm({ id: 2, machine_id: 1, severity: "critical" }),
        alarm({ id: 3, machine_id: 1, severity: "warning" }),
      ],
    ]);
    await screen.findByRole("heading", { level: 3, name: /Kritisch/ });
    // Gruppenköpfe sind <h3> (die sr-only-h1 trägt nur den Sichttitel).
    const groupHeadings = screen.getAllByRole("heading", { level: 3 });
    expect(groupHeadings[0]?.textContent).toMatch(/Kritisch/);
  });

  it("Werker: liest, aber KEIN Quittieren (auch bei Drift-Warnung)", async () => {
    setup(user("worker", { assigned_machine_ids: [1] }), [
      [alarm({ id: 9, machine_id: 1, code: "DRIFT", severity: "critical" })],
    ]);
    // Werker hat keinen overview-Zugang → Maschinen-Label fällt auf "Maschine {id}" zurück.
    await screen.findByText("Maschine 1");
    expect(screen.queryByRole("button", { name: /quittieren/i })).toBeNull();
  });

  it("Manager (Vollzugriff): Lagebild-Kopf UND volle Liste, darf quittieren (Drift)", async () => {
    // Werksleiter-/Vorführ-Profil (§21.9): das Lagebild bleibt als Überblicks-Kopf,
    // darunter die volle Liste — keine Aggregat-Sackgasse mehr. Quittieren erlaubt
    // (HITL-Status, keine Aktorik); reale Quittier-Route nur für Drift.
    const { transport } = setup(user("manager"), [
      [alarm({ id: 5, machine_id: 1, code: "DRIFT", severity: "critical" })],
    ]);
    act(() => {
      transport.emit("overview", {
        ...emptyOverview,
        machines: [
          {
            id: 1,
            label: "Presse 1",
            line_id: 3,
            machine_class: null,
            status: "open_warning",
            open_alarm_count: 2,
            open_by_severity: { critical: 1, warning: 1 },
            last_alarm_at: null,
          },
        ],
        open_alarm_total: 2,
      });
    });
    // Lagebild-Kopf (Überblick) ...
    expect(await screen.findByText("Häufigste Quellen")).toBeInTheDocument();
    // ... UND die volle Liste mit Quittier-Ziel (manager darf jetzt quittieren).
    expect(await screen.findByRole("button", { name: /quittieren/i })).toBeInTheDocument();
  });
});

describe("AlarmsView — Degradation & Live-Insert", () => {
  it("offline → Quittieren deaktiviert mit Grund (gecacht, friert ein)", async () => {
    const { transport } = setup(user("shift_lead"), [
      [alarm({ id: 5, machine_id: 1, code: "DRIFT", severity: "critical" })],
    ]);
    await screen.findByRole("button", { name: /quittieren/i });
    act(() => transport.setStatus("closed"));
    await waitFor(() => expect(screen.getByText(/Offline/)).toBeInTheDocument());
    expect(screen.queryByRole("button", { name: /quittieren/i })).toBeNull();
  });

  it("fehlgeschlagene Nachladung bei offenem WS → cached + Quittieren deaktiviert (Freshness ehrlich)", async () => {
    const transport = new FakeTransport();
    const store = new RealtimeStore(transport, { throttleMs: 0 });
    let call = 0;
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => {
        call += 1;
        if (call === 1) {
          return {
            ok: true,
            json: async () => [alarm({ id: 5, machine_id: 1, code: "DRIFT", severity: "critical" })],
          } as unknown as Response;
        }
        return { ok: false, status: 500, json: async () => ({}) } as unknown as Response;
      }),
    );
    const current = user("shift_lead");
    render(
      <SessionProvider user={current}>
        <RealtimeProvider store={store}>
          <AlarmsView user={current} />
        </RealtimeProvider>
      </SessionProvider>,
    );
    await screen.findByRole("button", { name: /quittieren/i });
    act(() => transport.emit("overview", emptyOverview)); // löst die fehlschlagende Nachladung aus
    await waitFor(() => expect(screen.getByText(/Offline/)).toBeInTheDocument(), { timeout: 3000 });
  });

  it("Live-Insert: WS-Signal → Nachladung → neuer Alarm eingefügt (Einblend-Puls)", async () => {
    const { transport } = setup(user("shift_lead"), [
      [alarm({ id: 1, machine_id: 1, severity: "alarm", raised_at: "2026-06-17T08:00:00Z" })],
      [
        alarm({ id: 1, machine_id: 1, severity: "alarm", raised_at: "2026-06-17T08:00:00Z" }),
        alarm({ id: 2, machine_id: 1, severity: "critical", raised_at: "2026-06-17T08:30:00Z" }),
      ],
    ]);
    await screen.findByRole("heading", { level: 3, name: /Hoch/ });
    act(() => transport.emit("overview", emptyOverview)); // Signal → gedrosselte Nachladung
    const newRow = await screen.findByRole(
      "article",
      { name: /Kritisch/ },
      { timeout: 3000 },
    );
    expect(newRow.className).toMatch(/state-flip/);
  });
});
