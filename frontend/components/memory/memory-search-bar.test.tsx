// ============================================================
//  FOREMAN Frontend — components/memory/memory-search-bar.test.tsx
//  Zweck: Suchzeile — natürlichsprachliche Eingabe löst aus; offline deaktiviert
//         mit Grund; Maschinen-Filter nur für Rollen mit Filter.
// ============================================================
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MemorySearchBar } from "./memory-search-bar";

describe("MemorySearchBar", () => {
  it("nimmt eine natürlichsprachliche Eingabe und löst beim Absenden aus", async () => {
    const onSubmit = vi.fn();
    render(<MemorySearchBar onSubmit={onSubmit} busy={false} canFilter={false} machines={[]} />);
    await userEvent.type(screen.getByLabelText("Beschreiben Sie die Situation"), "Lager läuft heiß");
    await userEvent.click(screen.getByRole("button", { name: "Ähnliche Fälle finden" }));
    expect(onSubmit).toHaveBeenCalledWith("Lager läuft heiß", null);
  });

  it("deaktiviert das Absenden offline mit sichtbarem Grund", () => {
    render(
      <MemorySearchBar
        onSubmit={vi.fn()}
        busy={false}
        canFilter={false}
        machines={[]}
        disabledReason="Offline — neue Suche nicht möglich"
      />,
    );
    expect(screen.getByRole("button", { name: "Ähnliche Fälle finden" })).toBeDisabled();
    expect(screen.getByText(/Offline/)).toBeInTheDocument();
  });

  it("zeigt den Maschinen-Filter nur für Rollen mit Filter", () => {
    const { rerender } = render(
      <MemorySearchBar onSubmit={vi.fn()} busy={false} canFilter={false} machines={[7]} />,
    );
    expect(screen.queryByLabelText("Maschine")).toBeNull();
    rerender(<MemorySearchBar onSubmit={vi.fn()} busy={false} canFilter machines={[7]} />);
    expect(screen.getByLabelText("Maschine")).toBeInTheDocument();
  });
});
