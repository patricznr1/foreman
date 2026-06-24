// ============================================================
//  FOREMAN Frontend — components/event-chains/chains-view.test.tsx
//  Zweck: Rollen-Split — Manager nur Aggregat (keine Liste/keine Erzählung),
//         Schichtleiter mit Anker triggert, Werker liest ohne Trigger.
// ============================================================
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CurrentUser } from "@/lib/api/contracts";
import { ChainsView } from "./chains-view";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

function res(ok: boolean, status: number, data: unknown): Response {
  return { ok, status, json: async () => data } as unknown as Response;
}

function user(over: Partial<CurrentUser> = {}): CurrentUser {
  return {
    id: 1,
    email: "u@halle.de",
    role: "worker",
    assigned_line_ids: [],
    assigned_machine_ids: [7],
    ...over,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ChainsView — Rollen-Split", () => {
  it("Manager (Vollzugriff): volle Sicht – gespeicherte Ketten + Rekonstruieren mit Anker", async () => {
    // Werksleiter-/Vorführprofil (§21.15): keine Aggregat-Sackgasse mehr — der
    // manager liest die volle Erzählung und kann selbst rekonstruieren (Trigger).
    vi.stubGlobal("fetch", vi.fn(async () => res(true, 200, [])));
    render(<ChainsView user={user({ role: "manager" })} anchorAlarmId={5} machineId={null} />);
    expect(await screen.findByText(/Gespeicherte Ketten/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Kette rekonstruieren/ })).toBeInTheDocument();
  });

  it("Schichtleiter mit Anker: Trigger vorhanden", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => res(true, 200, [])));
    render(<ChainsView user={user({ role: "shift_lead" })} anchorAlarmId={5} machineId={null} />);
    expect(await screen.findByRole("button", { name: /Kette rekonstruieren/ })).toBeInTheDocument();
  });

  it("Werker mit Anker: kein Trigger, nur Lesen", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => res(true, 200, [])));
    render(<ChainsView user={user({ role: "worker" })} anchorAlarmId={5} machineId={null} />);
    expect(screen.queryByRole("button", { name: /Kette rekonstruieren/ })).toBeNull();
    expect(screen.getByText(/dem Schichtleiter vorbehalten/)).toBeInTheDocument();
  });
});
