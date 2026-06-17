// ============================================================
//  FOREMAN Frontend — components/prediction/decision-action.test.tsx
//  Zweck: HITL — Quittieren/Verwerfen mit Begründungs-Pflicht, auditierbar; und
//         der sichtbare Hinweis, dass keine Anlage geschaltet wird.
// ============================================================
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DecisionAction } from "./decision-action";

describe("DecisionAction", () => {
  it("bei erhöhtem Risiko ist die Quittier-Begründung Pflicht (Bestätigen erst nach Eingabe)", async () => {
    const user = userEvent.setup();
    const onDecide = vi.fn();
    render(<DecisionAction decision="elevated_risk" onDecide={onDecide} />);
    await user.click(screen.getByRole("button", { name: "Quittieren" }));
    expect(screen.getByText(/Pflicht/)).toBeInTheDocument();
    const confirm = screen.getByRole("button", { name: "Bestätigen" });
    expect(confirm).toBeDisabled();
    await user.type(screen.getByRole("textbox"), "Schmierung vorgezogen");
    expect(confirm).toBeEnabled();
    await user.click(confirm);
    expect(onDecide).toHaveBeenCalledWith("acknowledged", "Schmierung vorgezogen");
  });

  it("Verwerfen verlangt IMMER eine Begründung", async () => {
    const user = userEvent.setup();
    render(<DecisionAction decision="normal" onDecide={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "Verwerfen" }));
    expect(screen.getByText(/Pflicht/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Bestätigen" })).toBeDisabled();
  });

  it("Quittieren bei geringem Risiko erlaubt sofortiges Bestätigen (Begründung optional)", async () => {
    const user = userEvent.setup();
    const onDecide = vi.fn();
    render(<DecisionAction decision="normal" onDecide={onDecide} />);
    await user.click(screen.getByRole("button", { name: "Quittieren" }));
    expect(screen.getByText(/optional/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Bestätigen" }));
    expect(onDecide).toHaveBeenCalledWith("acknowledged", null);
  });

  it("nennt sichtbar, dass die Anlage nicht geschaltet wird (HITL)", () => {
    render(<DecisionAction decision="normal" onDecide={vi.fn()} />);
    expect(screen.getByText(/nicht geschaltet/)).toBeInTheDocument();
  });
});
