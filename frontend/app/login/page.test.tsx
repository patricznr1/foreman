// ============================================================
//  FOREMAN Frontend — app/login/page.test.tsx
//  Zweck: Der Grund, den die Fassade nennt, muss am Terminal ANKOMMEN. Die
//         Seite ebnete jede Ablehnung auf „bitte Zugangsdaten prüfen" ein —
//         damit blieb die reparierte Unterscheidung Eingabe/Ausfall unsichtbar.
//  Aufbau-Kontroll-Zwilling: derselbe Aufbau zeigt bei zwei verschiedenen
//         Fassaden-Antworten zwei verschiedene Sätze und bei Erfolg gar keinen.
//         Eine Seite, die pauschal einen Satz setzt, fällt damit auf.
//  Architektur-Einordnung: Quality-Gate (npm test).
// ============================================================
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { push, refresh } = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh }) }));

import LoginPage from "./page";

/** Antwort der BFF-Route auf `POST /api/session`. */
function fassadeAntwortet(status: number, body: unknown): void {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

/**
 * Anmeldeversuch mit einer Adresse, die der BROWSER durchlässt (`type="email"`)
 * und das Backend ablehnt. Gemessen gegen `EmailStr`: `werker@halle3.local` →
 * 422 („part after the @-sign is a special-use domain"). Genau dieser Spalt ist
 * der reale Weg in den 422 — ein Hallen-Namensraum ohne öffentliche Domäne.
 * `werker.halle3` (ohne @) taugt hier NICHT: das blockiert schon das Formular.
 */
async function anmelden(): Promise<void> {
  render(<LoginPage />);
  await userEvent.type(screen.getByLabelText("E-Mail"), "werker@halle3.local");
  await userEvent.type(screen.getByLabelText("Passwort"), "passwort");
  await userEvent.click(screen.getByRole("button", { name: "Anmelden" }));
}

describe("Anmelde-Seite — der genannte Grund kommt an", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    push.mockReset();
  });

  it("zeigt bei Eingabefehler (400) den Satz der Fassade, nicht den Sammeltext", async () => {
    fassadeAntwortet(400, { detail: "E-Mail-Adresse hat kein gültiges Format" });

    await anmelden();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "E-Mail-Adresse hat kein gültiges Format",
    );
  });

  it("zeigt bei echtem Ausfall (502) den Dienst-Satz — anderer Text, gleicher Aufbau", async () => {
    fassadeAntwortet(502, { detail: "Authentifizierungsdienst nicht erreichbar" });

    await anmelden();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Authentifizierungsdienst nicht erreichbar",
    );
  });

  it("fällt auf den Sammeltext zurück, wenn die Antwort keinen Grund nennt", async () => {
    fassadeAntwortet(500, {});

    await anmelden();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Anmeldung fehlgeschlagen — bitte Zugangsdaten prüfen.",
    );
  });

  it("KONTROLLE: bei Erfolg keine Meldung, sondern Sprung aufs Landing", async () => {
    fassadeAntwortet(200, {
      id: 3,
      email: "diagnose@example.com",
      role: "worker",
      assigned_line_ids: [],
      assigned_machine_ids: [],
    });

    await anmelden();

    expect(screen.queryByRole("alert")).toBeNull();
    expect(push).toHaveBeenCalled();
  });
});
