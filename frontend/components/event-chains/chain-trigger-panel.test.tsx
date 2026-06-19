// ============================================================
//  FOREMAN Frontend — components/event-chains/chain-trigger-panel.test.tsx
//  Zweck: On-Demand-Trigger — Ruhezustand, dann Rekonstruktion → Ergebnis
//         (TimelineNarrative) mit Herkunftsstempel.
// ============================================================
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { makeDetail } from "@/lib/event-chains/testing/fixtures";
import { ChainTriggerPanel } from "./chain-trigger-panel";

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

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("ChainTriggerPanel", () => {
  it("Ruhezustand: Trigger vorhanden, noch keine Kette", () => {
    vi.stubGlobal("fetch", vi.fn(async () => res(true, 201, makeDetail())));
    render(<ChainTriggerPanel anchorAlarmId={5} canPin={false} onOpenSibling={() => {}} />);
    expect(screen.getByRole("button", { name: /Kette rekonstruieren/ })).toBeInTheDocument();
    expect(screen.getByText(/Noch keine Kette/)).toBeInTheDocument();
  });

  it("Trigger → Ergebnis: rekonstruierte Erzählung mit Herkunftsstempel", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => res(true, 201, makeDetail())));
    render(<ChainTriggerPanel anchorAlarmId={5} canPin={false} onOpenSibling={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /Kette rekonstruieren/ }));
    expect(await screen.findByText(/Erzählt — rekonstruiert/)).toBeInTheDocument();
    expect(screen.getByText(/KI-erzeugt/)).toBeInTheDocument();
  });
});
