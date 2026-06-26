// ============================================================
//  FOREMAN Frontend — components/memory/memory-search-bar.test.tsx
//  Zweck: Stichwort-Suchzeile des Archivs — Eingabe löst mit allen Quellen aus;
//         offline deaktiviert mit Grund; Maschinen-Filter + Quellen-Toggles nur für
//         Rollen mit Filter; Deaktivieren einer Quelle entfernt sie aus sources[].
// ============================================================
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { MemorySearchBar } from "./memory-search-bar";

describe("MemorySearchBar (Archiv)", () => {
  it("nimmt ein Stichwort und löst beim Absenden mit allen Quellen aus", async () => {
    const onSubmit = vi.fn();
    render(<MemorySearchBar onSubmit={onSubmit} busy={false} canFilter={false} machines={[]} />);
    await userEvent.type(screen.getByLabelText(/Stichwort/), "Fett");
    await userEvent.click(screen.getByRole("button", { name: "Suchen" }));
    expect(onSubmit).toHaveBeenCalledWith("Fett", null, ["note", "maintenance", "alarm"]);
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
    expect(screen.getByRole("button", { name: "Suchen" })).toBeDisabled();
    expect(screen.getByText(/Offline/)).toBeInTheDocument();
  });

  it("zeigt Maschinen-Filter und Quellen-Toggles nur für Rollen mit Filter", () => {
    const { rerender } = render(
      <MemorySearchBar onSubmit={vi.fn()} busy={false} canFilter={false} machines={[7]} />,
    );
    expect(screen.queryByLabelText("Maschine")).toBeNull();
    expect(screen.queryByRole("group", { name: "Quellen" })).toBeNull();
    rerender(<MemorySearchBar onSubmit={vi.fn()} busy={false} canFilter machines={[7]} />);
    expect(screen.getByLabelText("Maschine")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Quellen" })).toBeInTheDocument();
  });

  it("Default: alle drei Quellen-Toggles sind aktiv (aria-pressed)", () => {
    render(<MemorySearchBar onSubmit={vi.fn()} busy={false} canFilter machines={[]} />);
    for (const name of ["Schichtnotizen", "Wartung", "Alarme"]) {
      expect(screen.getByRole("button", { name })).toHaveAttribute("aria-pressed", "true");
    }
  });

  it("Deaktivieren einer Quelle entfernt sie aus dem sources[]-Argument des Requests", async () => {
    const onSubmit = vi.fn();
    render(<MemorySearchBar onSubmit={onSubmit} busy={false} canFilter machines={[]} />);
    await userEvent.type(screen.getByLabelText(/Stichwort/), "Fett");
    await userEvent.click(screen.getByRole("button", { name: "Wartung" }));
    await userEvent.click(screen.getByRole("button", { name: "Suchen" }));
    expect(onSubmit).toHaveBeenCalledWith("Fett", null, ["note", "alarm"]);
  });

  it("alle Quellen deaktiviert → Absenden gesperrt mit Hinweis", async () => {
    const onSubmit = vi.fn();
    render(<MemorySearchBar onSubmit={onSubmit} busy={false} canFilter machines={[]} />);
    for (const name of ["Schichtnotizen", "Wartung", "Alarme"]) {
      await userEvent.click(screen.getByRole("button", { name }));
    }
    expect(screen.getByRole("button", { name: "Suchen" })).toBeDisabled();
    expect(screen.getByText(/Mindestens eine Quelle/)).toBeInTheDocument();
  });

  it("ein Deep-Link-Wechsel setzt Maschinen-Filter und Quellen-Toggles zurück", async () => {
    const onSubmit = vi.fn();
    const { rerender } = render(
      <MemorySearchBar onSubmit={onSubmit} busy={false} canFilter machines={[7]} defaultQuery="alt" />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Wartung" })); // eine Quelle deaktivieren
    rerender(
      <MemorySearchBar onSubmit={onSubmit} busy={false} canFilter machines={[7]} defaultQuery="neu" />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Suchen" }));
    expect(onSubmit).toHaveBeenCalledWith("neu", null, ["note", "maintenance", "alarm"]);
  });
});
