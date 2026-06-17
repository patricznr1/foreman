// ============================================================
//  FOREMAN Frontend — components/machine/machine-cross-links.test.tsx
//  Zweck: Sichert die Schnellaktionen/Verbindungen als reine Navigation/Anforderung
//         (HITL: keine Anlagen-Schaltung) und das Rollen-Gating.
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MachineCrossLinks } from "./machine-cross-links";

describe("MachineCrossLinks", () => {
  it("Schichtleiter: Notiz + Vorhersage + Ereigniskette als Navigation", () => {
    render(<MachineCrossLinks machineId={7} canCaptureNote canRequestPrediction />);
    expect(screen.getByRole("link", { name: /Notiz/ })).toHaveAttribute(
      "href",
      expect.stringContaining("/capture"),
    );
    expect(screen.getByRole("link", { name: /Vorhersage/ })).toHaveAttribute(
      "href",
      expect.stringContaining("/insights/prediction"),
    );
    expect(screen.getByRole("link", { name: /Ereigniskette/ })).toHaveAttribute(
      "href",
      expect.stringContaining("/insights"),
    );
  });

  it("Werker ohne Vorhersage-Recht: kein Vorhersage-Trigger", () => {
    render(<MachineCrossLinks machineId={7} canCaptureNote canRequestPrediction={false} />);
    expect(screen.queryByRole("link", { name: /Vorhersage/ })).toBeNull();
  });
});
