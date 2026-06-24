// ============================================================
//  FOREMAN Frontend — components/event-chains/sibling-chains.test.tsx
//  Zweck: Schwesterketten-Querverweise — navigierbar nur bei realem Ziel (Button →
//         onOpen); nicht-anspringbare Verweise klar gekennzeichnet (Icon + Tooltip,
//         KEIN toter Button); leer → der Block erscheint gar nicht.
// ============================================================
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SiblingModel } from "@/lib/event-chains/types";
import { SiblingChains } from "./sibling-chains";

afterEach(cleanup);

function sibling(over: Partial<SiblingModel> = {}): SiblingModel {
  return {
    recallRef: "r1",
    machineId: 2,
    machineClass: "servo_press",
    explanationId: null,
    basis: "gleiche Klasse",
    excerpt: "ähnlicher Verlauf",
    navigable: false,
    ...over,
  };
}

describe("SiblingChains", () => {
  it("leer → der Block erscheint nicht (kein Fake-Leerzustand)", () => {
    const { container } = render(<SiblingChains siblings={[]} onOpen={vi.fn()} />);
    expect(container.firstChild).toBeNull();
  });

  it("navigierbarer Verweis → Button, der onOpen mit der explanationId auslöst", async () => {
    const onOpen = vi.fn();
    const user = userEvent.setup();
    render(
      <SiblingChains siblings={[sibling({ explanationId: 42, navigable: true })]} onOpen={onOpen} />,
    );
    await user.click(screen.getByRole("button", { name: /springen/ }));
    expect(onOpen).toHaveBeenCalledWith(42);
  });

  it("nicht-anspringbar → KEIN Button, sichtbar gekennzeichnet mit Tooltip", () => {
    render(
      <SiblingChains siblings={[sibling({ navigable: false, explanationId: null })]} onOpen={vi.fn()} />,
    );
    // Kein toter Klick: nicht-anspringbare Verweise sind keine Buttons.
    expect(screen.queryByRole("button")).toBeNull();
    // ... aber klar als „noch keine Kette" gekennzeichnet (Hinweis + Tooltip).
    const hint = screen.getByText(/Keine gespeicherte Kette zum Anspringen/);
    expect(hint).toHaveAttribute("title");
  });
});
