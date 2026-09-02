// ============================================================
//  FOREMAN Frontend — lib/prediction/use-prediction-retry.test.ts
//  Zweck: Die Wiederholung einer verworfenen Empfehlung.
//  Warum sie eigene Fälle verdient: Das Backend verwirft eine Empfehlung hart,
//         wenn sie eine unbelegte Zahl trägt oder den Simulations-Vorbehalt
//         umdeutet (422). Ein streuendes Modell kann beim nächsten Mal etwas
//         Belegbares liefern — jede ANDERE Lage wiederholt sich dagegen
//         unverändert. Wer das nicht trennt, verbrennt bei jedem Netzfehler das
//         Dreifache an Zeit und Geld, ohne dass es je auffiele.
//  Die zweite Gefahr ist stiller: eine Wiederholung, die auch dort läuft, wo der
//         erste Versuch längst geglückt ist. Der Aufbau-Kontroll-Zwilling unten
//         fordert deshalb GENAU EINEN Aufruf im Erfolgsfall ein.
// ============================================================
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MAX_VERSUCHE, usePrediction } from "./use-prediction";

afterEach(() => {
  vi.unstubAllGlobals();
});

const VORHERSAGE = { id: 24, machine_id: 3, probability: 0.87, horizon_h: 336 };
const EMPFEHLUNG = { id: 7, prediction_id: 24, created_at: "2026-09-02T10:00:00Z" };

/**
 * Stellt `fetch` und spielt für die EMPFEHLUNG eine Folge von Statuscodes ab.
 * Die Vorhersage glückt immer — hier geht es nur um den zweiten Schritt.
 *
 * Gezählt wird, wie oft die Empfehlung wirklich angefordert wurde. Das ist die
 * eigentliche Zusicherung: Ein Test, der nur die Meldung prüft, bliebe grün,
 * wenn die Schleife gar nicht oder endlos liefe.
 */
function stelleFetch(statusfolge: number[]): { empfehlungsaufrufe: () => number } {
  let n = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (String(url).endsWith("/recommendation") && init?.method === "POST") {
        const status = statusfolge[n] ?? 500;
        n += 1;
        return {
          ok: status < 400,
          status,
          json: async () => EMPFEHLUNG,
        } as Response;
      }
      return { ok: true, status: 201, json: async () => VORHERSAGE } as Response;
    }),
  );
  return { empfehlungsaufrufe: () => n };
}

function starte() {
  // `autoload: false` — der Ladeweg beim Mount würde sonst eigene Aufrufe zählen.
  const hook = renderHook(() => usePrediction({ machineId: 3, autoload: false }));
  act(() => {
    hook.result.current.trigger();
  });
  return hook;
}

describe("Wiederholung einer verworfenen Empfehlung", () => {
  it("verworfen, dann belegbar: der zweite Versuch trägt das Ergebnis", async () => {
    const { empfehlungsaufrufe } = stelleFetch([422, 201]);
    const { result } = starte();

    await waitFor(() => expect(result.current.phase.kind).toBe("result"));
    expect(empfehlungsaufrufe()).toBe(2);
  });

  it("AUFBAU-KONTROLLE: gleich belegbar → genau EIN Aufruf", async () => {
    // Ohne diesen Fall bliebe der Test darüber auch dann grün, wenn IMMER
    // wiederholt würde — dann kostete jede geglückte Empfehlung das Dreifache.
    const { empfehlungsaufrufe } = stelleFetch([201]);
    const { result } = starte();

    await waitFor(() => expect(result.current.phase.kind).toBe("result"));
    expect(empfehlungsaufrufe()).toBe(1);
  });

  it("DIE TRAGENDE UNTERSCHEIDUNG: eine Störung des Weges wird NICHT wiederholt", async () => {
    // 500 heisst „der Weg ist gestört", nicht „der Inhalt hat den Guard nicht
    // bestanden". Ein zweiter Versuch fände dieselbe Störung vor.
    const { empfehlungsaufrufe } = stelleFetch([500, 201]);
    const { result } = starte();

    await waitFor(() => expect(result.current.phase.kind).toBe("error"));
    expect(empfehlungsaufrufe()).toBe(1);
  });

  it("auch ein fehlender Gegenstand (404) wird nicht wiederholt", async () => {
    const { empfehlungsaufrufe } = stelleFetch([404, 201]);
    const { result } = starte();

    await waitFor(() => expect(result.current.phase.kind).toBe("error"));
    expect(empfehlungsaufrufe()).toBe(1);
  });

  it("dreimal verworfen: es wird aufgegeben, und die Meldung nennt die Zahl", async () => {
    const { empfehlungsaufrufe } = stelleFetch([422, 422, 422, 201]);
    const { result } = starte();

    await waitFor(() => expect(result.current.phase.kind).toBe("error"));
    expect(empfehlungsaufrufe()).toBe(MAX_VERSUCHE);
    const phase = result.current.phase;
    expect(phase.kind === "error" && phase.message).toContain(String(MAX_VERSUCHE));
    expect(phase.kind === "error" && phase.message).toContain("belegbar");
  });

  it("der laufende Versuch ist ablesbar", async () => {
    stelleFetch([422, 422, 422]);
    const { result } = starte();
    await waitFor(() => expect(result.current.phase.kind).toBe("error"));
    expect(result.current.versuch).toBe(MAX_VERSUCHE);
  });

  it("beim nächsten Auslösen steht die alte Zahl nicht mehr da", async () => {
    // DAS FENSTER, auf das es ankommt — und es ist schmal: Zwischen dem Auslösen
    // und dem ersten Empfehlungs-Versuch läuft die VORHERSAGE. Ohne das
    // Zurücksetzen stünde in dieser Zeit noch die Zahl des vorigen Laufs in der
    // Anzeige („Versuch 3 von 3 läuft"), obwohl noch gar kein Versuch läuft.
    //
    // Ein Test, der erst NACH dem Lauf prüft, kann das nie sehen: Die Schleife
    // setzt den Zähler in ihrem ersten Durchgang ohnehin auf 1. Deshalb wird die
    // Vorhersage hier angehalten und mitten im Fenster nachgesehen.
    stelleFetch([422, 422, 422]);
    const { result } = starte();
    await waitFor(() => expect(result.current.phase.kind).toBe("error"));
    expect(result.current.versuch).toBe(MAX_VERSUCHE);

    let gibVorhersageFrei: () => void = () => {};
    const vorhersageHaengt = new Promise<void>((aufloesen) => {
      gibVorhersageFrei = aufloesen;
    });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (String(url).endsWith("/recommendation")) {
          return { ok: true, status: 201, json: async () => EMPFEHLUNG } as Response;
        }
        await vorhersageHaengt;
        return { ok: true, status: 201, json: async () => VORHERSAGE } as Response;
      }),
    );

    act(() => {
      result.current.trigger();
    });
    await waitFor(() => expect(result.current.phase.kind).toBe("processing"));
    expect(result.current.versuch).toBe(1);

    await act(async () => {
      gibVorhersageFrei();
      await vorhersageHaengt;
    });
    await waitFor(() => expect(result.current.phase.kind).toBe("result"));
  });
});
