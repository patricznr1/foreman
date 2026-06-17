// ============================================================
//  FOREMAN Frontend — components/capture/category-buttons.test.tsx
//  Zweck: Sichert die mehrkanaligen Kategorie-Buttons (Auswahl, aria-pressed,
//         Toggle) — kein Dropdown, vom Werker manuell gewählt.
// ============================================================
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CategoryButtons } from "./category-buttons";

describe("CategoryButtons", () => {
  it("zeigt alle drei Kategorien als Buttons (kein Dropdown)", () => {
    render(<CategoryButtons value={null} onChange={() => {}} />);
    expect(screen.getByRole("button", { name: /Routine/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Auffällig/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Kritisch/ })).toBeInTheDocument();
    // kein <select> / Dropdown
    expect(screen.queryByRole("combobox")).toBeNull();
  });

  it("markiert die gewählte Kategorie mehrkanalig (aria-pressed)", () => {
    render(<CategoryButtons value="kritisch" onChange={() => {}} />);
    expect(screen.getByRole("button", { name: /Kritisch/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /Routine/ })).toHaveAttribute("aria-pressed", "false");
  });

  it("meldet die manuelle Auswahl", async () => {
    const onChange = vi.fn();
    render(<CategoryButtons value={null} onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: /Auffällig/ }));
    expect(onChange).toHaveBeenCalledWith("auffaellig");
  });

  it("hebt die Wahl bei erneutem Tap auf (optionale Kategorie)", async () => {
    const onChange = vi.fn();
    render(<CategoryButtons value="routine" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: /Routine/ }));
    expect(onChange).toHaveBeenCalledWith(null);
  });

  it("sperrt alle Buttons im disabled-Zustand", () => {
    render(<CategoryButtons value={null} onChange={() => {}} disabled />);
    for (const name of [/Routine/, /Auffällig/, /Kritisch/]) {
      expect(screen.getByRole("button", { name })).toBeDisabled();
    }
  });
});
