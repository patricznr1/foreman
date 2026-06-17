// ============================================================
//  FOREMAN Frontend — components/machine/time-window-picker.test.tsx
//  Zweck: Sichert den Zeitfenster-Umschalter (Schicht/Tag/Woche).
// ============================================================
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TimeWindowPicker } from "./time-window-picker";

describe("TimeWindowPicker", () => {
  it("zeigt die Fenster, markiert das aktive und meldet die Auswahl", () => {
    const onChange = vi.fn();
    render(<TimeWindowPicker value="day" onChange={onChange} />);
    expect(screen.getByRole("button", { name: "Tag" })).toHaveAttribute("aria-pressed", "true");
    const week = screen.getByRole("button", { name: "Woche" });
    expect(week).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(week);
    expect(onChange).toHaveBeenCalledWith("week");
  });
});
