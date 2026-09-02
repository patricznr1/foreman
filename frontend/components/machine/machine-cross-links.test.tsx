// ============================================================
//  FOREMAN Frontend — components/machine/machine-cross-links.test.tsx
//  Zweck: Sichert die Schnellaktionen als reine Navigation/Anforderung (HITL:
//         keine Anlagen-Schaltung), das Rollen-Gating — und seit dem 02.09.2026
//         die Trennung zwischen WEGFÜHREN und EINBLENDEN.
//  Die Trennung ist der Punkt: Vorhersage und Ereigniskette öffnen an Ort und
//         Stelle, weil man sie neben Sensorverlauf und offenen Alarmen beurteilt.
//         Die Notiz-Erfassung führt weiterhin weg — sie ist ein eigenes Formular
//         mit eigenem Absenden. Wer das vermischt, verliert entweder den
//         Zusammenhang oder baut ein Formular in eine Lesesicht.
// ============================================================
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { MachineCrossLinks } from "./machine-cross-links";

const IDS = { vorhersageId: "v1", kettenId: "k1" } as const;

function zeige(over: Partial<React.ComponentProps<typeof MachineCrossLinks>> = {}) {
  const onToggle = vi.fn();
  render(
    <MachineCrossLinks
      machineId={7}
      canCaptureNote
      canRequestPrediction
      offen={null}
      onToggle={onToggle}
      {...IDS}
      {...over}
    />,
  );
  return { onToggle };
}

describe("MachineCrossLinks", () => {
  it("die Notiz-Erfassung führt weiterhin weg — sie ist ein eigenes Formular", () => {
    zeige();
    expect(screen.getByRole("link", { name: /Notiz/ })).toHaveAttribute(
      "href",
      expect.stringContaining("/capture"),
    );
  });

  it("Vorhersage und Ereigniskette sind SCHALTER, keine Verweise", () => {
    // DIE TRAGENDE ZUSICHERUNG. Als Verweis führten sie aus der Maschinensicht
    // heraus, und der Zusammenhang — Sensorverlauf, offene Alarme, Stammdaten —
    // stünde beim Beurteilen nicht mehr daneben.
    zeige();
    expect(screen.getByRole("button", { name: /Vorhersage/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Ereigniskette/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Vorhersage/ })).toBeNull();
    expect(screen.queryByRole("link", { name: /Ereigniskette/ })).toBeNull();
  });

  it("meldet dem Bediener, was offen ist — auch ohne Sicht auf den Bereich", async () => {
    // `aria-expanded` und `aria-controls` sind nicht Zierde: Wer die Sicht mit
    // einer Vorlesehilfe bedient, erfährt sonst nie, dass der Knopf etwas
    // aufgeklappt hat, und sucht das Ergebnis vergeblich.
    zeige({ offen: "vorhersage" });
    const vorhersage = screen.getByRole("button", { name: /Vorhersage/ });
    expect(vorhersage).toHaveAttribute("aria-expanded", "true");
    expect(vorhersage).toHaveAttribute("aria-controls", IDS.vorhersageId);
    expect(screen.getByRole("button", { name: /Ereigniskette/ })).toHaveAttribute(
      "aria-expanded",
      "false",
    );
  });

  it("die Beschriftung sagt, was der nächste Druck tut", async () => {
    // Ein Knopf, der geöffnet noch „Vorhersage anfordern" heisst, verspricht eine
    // zweite Anforderung — er schliesst aber.
    zeige({ offen: "vorhersage" });
    expect(screen.getByRole("button", { name: "Vorhersage ausblenden" })).toBeInTheDocument();
  });

  it("meldet den Druck mit der richtigen Kennung nach oben", async () => {
    const { onToggle } = zeige();
    await userEvent.click(screen.getByRole("button", { name: /Ereigniskette/ }));
    expect(onToggle).toHaveBeenCalledWith("ketten");
    await userEvent.click(screen.getByRole("button", { name: /Vorhersage/ }));
    expect(onToggle).toHaveBeenCalledWith("vorhersage");
  });

  it("Werker ohne Vorhersage-Recht: kein Vorhersage-Schalter", () => {
    // Das Gating bleibt, wo es war — der Umbau auf Schalter darf es nicht
    // aufweichen. Genau dieser Fall stand schon vor dem Umbau hier.
    zeige({ canRequestPrediction: false });
    expect(screen.queryByRole("button", { name: /Vorhersage/ })).toBeNull();
    // Aufbau-Kontrolle: die Ereigniskette ist trotzdem da — der Fall oben prüft
    // nicht bloss, dass gar nichts gerendert wurde.
    expect(screen.getByRole("button", { name: /Ereigniskette/ })).toBeInTheDocument();
  });
});
