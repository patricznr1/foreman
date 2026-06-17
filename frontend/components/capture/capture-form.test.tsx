// ============================================================
//  FOREMAN Frontend — components/capture/capture-form.test.tsx
//  Zweck: Integrationstest des Erfassungs-Flusses: Happy-Path (senden →
//         Bestätigung), Pflichtfeld, classification MITgesendet (Anschlusspunkt),
//         Offline-Puffer (Degradation), HITL (kein Aktor-Pfad), Maschinen-Vorauswahl.
// ============================================================
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { WorkerNoteRead } from "@/lib/api/contracts";
import { OUTBOX_KEY, readOutbox } from "@/lib/capture/outbox";
import { captureRoleView } from "@/lib/capture/roles";
import { makeMachine, makeUser } from "@/lib/capture/testing/fixtures";
import type { MachinesState } from "@/lib/capture/use-machines";
import { CaptureForm } from "./capture-form";

const NOTE: WorkerNoteRead = {
  id: 1,
  machine_id: 2,
  shift: "Frühschicht",
  text: "[PERSON] meldet Lager heiß",
  classification: null,
  author: "v1:ab12cd34",
  created_at: "2026-06-17T15:00:00+00:00",
};

const READY: MachinesState = {
  kind: "ready",
  machines: [makeMachine({ id: 2, label: "Drehbank 2" }), makeMachine({ id: 3, label: "Fräse 3" })],
};

/** fetch-Double: POST → 201; jeder GET (Suche/Vorschläge) → leere Liste. */
function stubFetch() {
  const mock = vi.fn(async (_url: string, init?: RequestInit) => {
    if (init?.method === "POST") {
      return { status: 201, json: async () => NOTE } as Response;
    }
    return { ok: true, status: 200, json: async () => [] } as Response;
  });
  vi.stubGlobal("fetch", mock);
  return mock;
}

function setOnline(value: boolean) {
  Object.defineProperty(navigator, "onLine", { value, configurable: true });
}

function lastPostBody(mock: ReturnType<typeof stubFetch>): Record<string, unknown> | null {
  const post = mock.mock.calls.find((call) => (call[1] as RequestInit | undefined)?.method === "POST");
  if (!post) {
    return null;
  }
  return JSON.parse((post[1] as RequestInit).body as string);
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.localStorage.clear();
  setOnline(true);
});

const worker = makeUser({ role: "worker", assigned_machine_ids: [2, 3] });
const roleView = captureRoleView("worker");

describe("CaptureForm — Happy-Path", () => {
  it("sendet die Notiz und bestätigt 'Notiz erfasst'", async () => {
    setOnline(true);
    const mock = stubFetch();
    render(
      <CaptureForm user={worker} roleView={roleView} machinesState={READY} initialMachineId={null} />,
    );
    await userEvent.type(screen.getByLabelText(/Was hast du beobachtet/), "Lager läuft heiß");
    await userEvent.click(screen.getByRole("button", { name: /Notiz speichern/ }));

    await waitFor(() => expect(screen.getByText("Notiz erfasst.")).toBeInTheDocument());
    const body = lastPostBody(mock);
    expect(body?.text).toBe("Lager läuft heiß");
    // Rückfluss-Hinweis (B-Historie + H-Suche) sichtbar gemacht.
    expect(screen.getByText(/Maschinen-Historie/)).toBeInTheDocument();
  });

  it("HITL: sendet AUSSCHLIESSLICH an den worker_notes-POST — kein Aktor-Pfad", async () => {
    const mock = stubFetch();
    render(
      <CaptureForm user={worker} roleView={roleView} machinesState={READY} initialMachineId={null} />,
    );
    await userEvent.type(screen.getByLabelText(/Was hast du beobachtet/), "Beobachtung");
    await userEvent.click(screen.getByRole("button", { name: /Notiz speichern/ }));
    await waitFor(() => {
      const post = mock.mock.calls.find((c) => (c[1] as RequestInit | undefined)?.method === "POST");
      expect(post?.[0]).toBe("/api/v1/worker_notes");
    });
  });
});

describe("CaptureForm — Pflichtfeld", () => {
  it("sperrt Speichern bei leerer Beobachtung (mit Grund)", () => {
    stubFetch();
    render(
      <CaptureForm user={worker} roleView={roleView} machinesState={READY} initialMachineId={null} />,
    );
    expect(screen.getByRole("button", { name: /Notiz speichern/ })).toBeDisabled();
    expect(screen.getByText(/Beobachtung eingeben/)).toBeInTheDocument();
  });
});

describe("CaptureForm — Kategorie mitgesendet (Anschlusspunkt)", () => {
  it("schickt classification im POST mit, wenn der Werker sie wählt", async () => {
    const mock = stubFetch();
    render(
      <CaptureForm user={worker} roleView={roleView} machinesState={READY} initialMachineId={null} />,
    );
    await userEvent.type(screen.getByLabelText(/Was hast du beobachtet/), "Späne bläulich");
    await userEvent.click(screen.getByRole("button", { name: /Kritisch/ }));
    await userEvent.click(screen.getByRole("button", { name: /Notiz speichern/ }));
    await waitFor(() => expect(lastPostBody(mock)?.classification).toBe("kritisch"));
  });
});

describe("CaptureForm — Offline-Puffer (Degradation)", () => {
  it("puffert lokal und meldet 'wird gesendet, sobald online' — kein POST", async () => {
    setOnline(false);
    const mock = stubFetch();
    render(
      <CaptureForm user={worker} roleView={roleView} machinesState={READY} initialMachineId={2} />,
    );
    await userEvent.type(screen.getByLabelText(/Was hast du beobachtet/), "Notiz ohne Netz");
    await userEvent.click(screen.getByRole("button", { name: /Notiz speichern/ }));

    await waitFor(() => expect(screen.getByText(/wird gesendet, sobald wieder Netz/)).toBeInTheDocument());
    // Kein Sende-POST offline …
    expect(mock.mock.calls.some((c) => (c[1] as RequestInit | undefined)?.method === "POST")).toBe(false);
    // … aber die Notiz liegt in der lokalen Queue (überlebt bis zum Senden).
    const queued = readOutbox(window.localStorage);
    expect(queued).toHaveLength(1);
    expect(queued[0]?.payload.text).toBe("Notiz ohne Netz");
    expect(queued[0]?.payload.machine_id).toBe(2);
    expect(window.localStorage.getItem(OUTBOX_KEY)).not.toBeNull();
  });
});

describe("CaptureForm — Kontext-Vorauswahl", () => {
  it("wählt die übergebene Maschine vor (aus ?machine=)", () => {
    stubFetch();
    render(
      <CaptureForm user={worker} roleView={roleView} machinesState={READY} initialMachineId={3} />,
    );
    expect(screen.getByRole("button", { name: "Fräse 3" })).toHaveAttribute("aria-pressed", "true");
  });
});
