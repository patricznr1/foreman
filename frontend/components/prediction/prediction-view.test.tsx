// ============================================================
//  FOREMAN Frontend — components/prediction/prediction-view.test.tsx
//  Zweck: Rollen-Split — Werker ohne Trigger, Schichtleiter mit Trigger, Manager
//         nur Aggregat (kein Einzel-Vorschlag, kein Trigger). Fetch gemockt.
// ============================================================
import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { CurrentUser } from "@/lib/api/contracts";
import { PredictionView } from "./prediction-view";

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
    email: "schicht@halle.de",
    role: "worker",
    assigned_line_ids: [],
    assigned_machine_ids: [1],
    ...over,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("PredictionView — Rollen-Split", () => {
  it("Werker: kein Trigger, Ruhezustand", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => res(false, 404, {})));
    render(<PredictionView user={user({ role: "worker" })} />);
    expect(screen.queryByRole("button", { name: /Vorhersage anfordern/ })).toBeNull();
    expect(await screen.findByText(/Noch keine Erkenntnis/)).toBeInTheDocument();
  });

  it("Schichtleiter: Trigger vorhanden", () => {
    vi.stubGlobal("fetch", vi.fn(async () => res(false, 404, {})));
    render(<PredictionView user={user({ role: "shift_lead" })} />);
    expect(screen.getByRole("button", { name: /Vorhersage anfordern/ })).toBeInTheDocument();
  });

  it("Manager: nur Aggregat — kein Trigger, kein Einzel-Vorschlag", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => res(true, 200, [])));
    render(<PredictionView user={user({ role: "manager", assigned_machine_ids: [] })} />);
    expect(await screen.findByText(/Keine Vorhersagen vorhanden/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Vorhersage anfordern/ })).toBeNull();
  });
});
