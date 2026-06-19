// ============================================================
//  FOREMAN Frontend — components/event-chains/timeline-narrative.test.tsx
//  Zweck: Belegt/Erzählt hart getrennt, gekoppeltes Hervorheben (Knoten ↔ Quell-
//         Chip), Hypothese-Kennzeichnung, KEINE Severity-Farbe in der Erzählung.
// ============================================================
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { makeDetail } from "@/lib/event-chains/testing/fixtures";
import type { ChainCardModel } from "@/lib/event-chains/types";
import { assembleChainCard } from "@/lib/event-chains/view-model";
import { TimelineNarrative } from "./timeline-narrative";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

function cardFor(over: Parameters<typeof makeDetail>[0] = {}): ChainCardModel {
  const result = assembleChainCard(makeDetail(over));
  if (!result.ok) {
    throw new Error("Fixture ungültig");
  }
  return result.card;
}

describe("TimelineNarrative", () => {
  it("zeigt beide Spalten hart getrennt (Belegt / Erzählt)", () => {
    render(<TimelineNarrative card={cardFor()} canPin={false} onOpenSibling={() => {}} />);
    expect(screen.getByText(/Belegt — Ereignisse/)).toBeInTheDocument();
    expect(screen.getByText(/Erzählt — rekonstruiert/)).toBeInTheDocument();
  });

  it("koppelt Knoten und Quell-Chip: Klick auf den Anker hebt sein Zitat hervor", () => {
    render(<TimelineNarrative card={cardFor()} canPin={false} onOpenSibling={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /Anker/ }));
    expect(screen.getByRole("button", { name: /Quelle alarm:1/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("kennzeichnet die Hypothese und nutzt KEINE Severity-Farbe", () => {
    render(
      <TimelineNarrative
        card={cardFor({ is_hypothesis: true, confidence: "low" })}
        canPin={false}
        onOpenSibling={() => {}}
      />,
    );
    expect(screen.getByText("Hypothese")).toBeInTheDocument();
    const html = document.body.innerHTML;
    for (const severity of [
      "alarm-critical",
      "alarm-high",
      "alarm-medium",
      "alarm-low",
      "alarm-emergency",
      "state-failure",
    ]) {
      expect(html).not.toContain(severity);
    }
  });
});
