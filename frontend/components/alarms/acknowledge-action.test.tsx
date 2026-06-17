// ============================================================
//  FOREMAN Frontend — components/alarms/acknowledge-action.test.tsx
//  Zweck: HITL-Quittierung — zweistufig, Pflicht-Kontext bei kritisch, läuft gegen
//         die REALE Drift-Route; NEGATIVTEST: sendet ausschließlich den /acknowledge-
//         Status-Pfad (kein Anlagen-Schreibpfad); Rollen-/Offline-Sperren mit Grund.
// ============================================================
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { isAlarmStatusActionPath } from "@/lib/alarms/acknowledge";
import { alarm, machines, NOW, noNew, noShelf } from "@/lib/alarms/testing/fixtures";
import type { AlarmViewModel } from "@/lib/alarms/types";
import { buildAlarmViewModel } from "@/lib/alarms/view-model";
import { AcknowledgeAction } from "./acknowledge-action";

const ctx = { machines, shelf: noShelf, now: NOW, newIds: noNew };
const vm = (over = {}): AlarmViewModel => buildAlarmViewModel(alarm(over), ctx);

afterEach(cleanup);

describe("AcknowledgeAction — HITL zweistufig", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("kritische Drift-Warnung: Pflicht-Kontext, dann POST gegen die reale Route", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ ...alarm({ id: 42 }), acknowledged_at: "2026-06-17T09:00:00Z" }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const onAck = vi.fn();
    const user = userEvent.setup();

    render(
      <AcknowledgeAction
        vm={vm({ id: 42, code: "DRIFT", severity: "critical" })}
        canAcknowledge
        online
        onAcknowledged={onAck}
      />,
    );

    await user.click(screen.getByRole("button", { name: /quittieren/i }));
    // Stufe 2: Pflicht-Begründung; Bestätigen erst nach Eingabe aktiv.
    const confirm = screen.getByRole("button", { name: /Bestätigen/ });
    expect(confirm).toBeDisabled();
    await user.type(screen.getByRole("textbox"), "Lager geprüft, unkritisch");
    expect(confirm).toBeEnabled();
    await user.click(confirm);

    await waitFor(() => expect(onAck).toHaveBeenCalled());
    const calledUrl = fetchMock.mock.calls[0]?.[0] as string;
    expect(calledUrl).toBe("/api/v1/reasoners/drift/alarms/42/acknowledge");
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe("POST");
  });

  it("NEGATIVTEST: jede gesendete URL ist ein Alarm-Status-Pfad, nie eine Schaltung", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => alarm({ id: 7 }) });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();

    render(
      <AcknowledgeAction
        vm={vm({ id: 7, code: "DRIFT", severity: "alarm" })}
        canAcknowledge
        online
        onAcknowledged={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: /quittieren/i }));
    await user.click(screen.getByRole("button", { name: /Bestätigen/ }));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    for (const call of fetchMock.mock.calls) {
      expect(isAlarmStatusActionPath(call[0] as string)).toBe(true);
    }
  });

  it("Nicht-Drift: keine generische Route → deaktiviert mit Grund (kein POST möglich)", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    render(
      <AcknowledgeAction
        vm={vm({ id: 3, code: null, severity: "critical" })}
        canAcknowledge
        online
        onAcknowledged={vi.fn()}
      />,
    );
    expect(screen.getByText(/Route für diese Alarmklasse noch nicht/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /quittieren/i })).toBeNull();
  });

  it("Werker (kein Quittieren) → keine Aktion sichtbar", () => {
    const { container } = render(
      <AcknowledgeAction
        vm={vm({ code: "DRIFT", severity: "critical" })}
        canAcknowledge={false}
        online
        onAcknowledged={vi.fn()}
      />,
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("Offline → deaktiviert mit Grund", () => {
    render(
      <AcknowledgeAction
        vm={vm({ code: "DRIFT", severity: "critical" })}
        canAcknowledge
        online={false}
        onAcknowledged={vi.fn()}
      />,
    );
    expect(screen.getByText(/Offline/)).toBeInTheDocument();
  });

  it("Schließen gibt den Fokus an den Auslöser zurück (WCAG 2.4.3)", async () => {
    vi.stubGlobal("fetch", vi.fn());
    const user = userEvent.setup();
    render(
      <AcknowledgeAction
        vm={vm({ code: "DRIFT", severity: "alarm" })}
        canAcknowledge
        online
        onAcknowledged={vi.fn()}
      />,
    );
    const trigger = screen.getByRole("button", { name: /quittieren/i });
    await user.click(trigger);
    await user.click(screen.getByRole("button", { name: "Abbrechen" }));
    expect(document.activeElement).toBe(trigger);
  });

  it("403 vom Server → harte Grenze, kein Retry-Angebot (HITL)", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: false, status: 403, json: async () => ({}) });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    render(
      <AcknowledgeAction
        vm={vm({ code: "DRIFT", severity: "alarm" })}
        canAcknowledge
        online
        onAcknowledged={vi.fn()}
      />,
    );
    await user.click(screen.getByRole("button", { name: /quittieren/i }));
    await user.click(screen.getByRole("button", { name: /Bestätigen/ }));
    expect(await screen.findByText(/nicht erlaubt/)).toBeInTheDocument();
    expect(screen.queryByText(/erneut versuchen/)).toBeNull();
  });

  it("bereits quittiert → maskierter Stempel statt Aktion (kein Klartext)", () => {
    render(
      <AcknowledgeAction
        vm={vm({
          code: "DRIFT",
          severity: "critical",
          acknowledged_at: "2026-06-17T08:30:00Z",
          acknowledged_by: "v1:a7f3e8c2b9",
        })}
        canAcknowledge
        online
        onAcknowledged={vi.fn()}
      />,
    );
    expect(screen.getByText(/#a7f3e8/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /quittieren/i })).toBeNull();
  });
});
