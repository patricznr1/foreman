// ============================================================
//  FOREMAN Frontend — components/capture/capture-view.test.tsx
//  Zweck: Sichert den Rollen-Split: erfassende Rollen bekommen das Formular, der
//         Manager (liest, erfasst nicht) eine reduzierte Lese-/Hinweis-Ansicht.
// ============================================================
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { makeUser } from "@/lib/capture/testing/fixtures";
import { CaptureView } from "./capture-view";

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubMachines() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, status: 200, json: async () => [] }) as Response),
  );
}

describe("CaptureView — Rollen", () => {
  it("zeigt dem Werker das Erfassungs-Formular (Kernnutzer)", () => {
    stubMachines();
    render(<CaptureView user={makeUser({ role: "worker" })} initialMachineId={null} />);
    expect(screen.getByLabelText(/Was hast du beobachtet/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Notiz speichern/ })).toBeInTheDocument();
  });

  it("zeigt dem Manager das Formular — er ist das Vorführprofil (seit 01.09.2026)", () => {
    // GEÄNDERT AM 01.09.2026. Vorher forderte dieser Fall das Gegenteil ein:
    // „zeigt dem Manager KEIN Formular, sondern den Lese-Hinweis".
    //
    // Der Grund steht in `lib/capture/roles.ts`: GROUND_TRUTH §21 beschreibt
    // das Login als Vorführprofil, und `POST /worker_notes` kennt kein
    // `require_roles` — der Server nahm die Notiz seit jeher an.
    //
    // WAS DABEI VERLOREN GEHT, geprüft und für unerheblich befunden: Der
    // Lese-Zweig trug den einzigen Verweis auf „Gedächtnis". Der zeigt auf
    // `/memory`, und das leitet dauerhaft auf `/archive` um — erreichbar über
    // die Befehlspalette und die Querverweise der Vorhersage.
    stubMachines();
    render(<CaptureView user={makeUser({ role: "manager" })} initialMachineId={null} />);
    expect(screen.getByLabelText(/Was hast du beobachtet/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Notiz speichern/ })).toBeInTheDocument();
  });

  it("zeigt einer unbekannten Rolle weiterhin NUR den Lese-Hinweis", () => {
    // AUFBAU-KONTROLLE: Der Lese-Zweig ist nicht tot, er trägt jetzt den
    // default-deny. Ohne diesen Fall könnte er unbemerkt verfallen — und mit
    // ihm die Zusicherung, dass eine unbekannte Backend-Rolle nichts erfasst.
    stubMachines();
    render(<CaptureView user={makeUser({ role: "auditor" as never })} initialMachineId={null} />);
    expect(screen.queryByLabelText(/Was hast du beobachtet/)).toBeNull();
    expect(screen.queryByRole("button", { name: /Notiz speichern/ })).toBeNull();
    expect(screen.getByRole("link", { name: /Gedächtnis/ })).toHaveAttribute("href", "/memory");
  });
});
