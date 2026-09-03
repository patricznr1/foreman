// ============================================================
//  FOREMAN Frontend — lib/machine/use-machine-trend.test.tsx
//  Zweck: Die beiden Aussagen, die der Trend-Hook über das LADEFENSTER macht —
//         `loadedFromMs` (bis wohin ist wirklich abgerufen worden?) und
//         `refetching` (steht eine Anfrage aus, während schon ein Bild dasteht?).
//         Beide speisen Marken im Diagramm, und beide können nur in EINE Richtung
//         falsch sein, die auffällt: eine Fläche, die „nichts gemessen" behauptet,
//         wo in Wahrheit niemand gefragt hat.
//  Warum eigene Fälle: Der Fehlerzweig darf die Fortschrittsmarke NICHT
//         fortschreiben. Ein Wegfehler (Netz, Zeitüberschreitung, 500) sagt nichts
//         über den Bereich aus, den er nicht geholt hat — und die zugehörige
//         Schraffur verschwände sonst genau dann, wenn sie gebraucht wird.
//  Architektur-Einordnung: Test der View-State-Schicht (Schicht 2/3).
// ============================================================
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { MachineTrendOut } from "@/lib/api/contracts";
import { RealtimeProvider } from "@/lib/realtime/realtime-context";
import { RealtimeStore } from "@/lib/realtime/realtime-store";
import { FakeTransport } from "@/lib/realtime/testing/fake-transport";

import { useMachineTrend } from "./use-machine-trend";

const STUNDE_MS = 3_600_000;
/** Fester Zeitanker. `Date.now` wird darauf festgenagelt — die Marke ist eine Zahl. */
const NOW = Date.parse("2026-06-17T11:00:00Z");

/**
 * Zwei Punkte, die BEWUSST NICHT am linken Rand des Ladefensters liegen: Der erste
 * Messwert ist 10:00, der Anfang eines 24-h-Fensters wäre 16.06. 11:00. Damit
 * unterscheidet jede Zusicherung unten die Anfrage-Quelle von `samples[0].t` —
 * eine Herleitung aus dem ersten Messwert machte aus einer echten Messlücke am
 * linken Rand eine erfundene Ladelücke und wäre hier sofort rot.
 */
const historisch: MachineTrendOut = {
  machine_id: 7,
  data_point_id: 42,
  data_point_name: "spindle_temp",
  unit: "°C",
  measurement_type: "temperature",
  normal_min: 10,
  normal_max: 20,
  truncated: false,
  profile_band: null,
  points: [
    { bucket: "2026-06-17T10:00:00Z", avg: 15, min: 14, max: 16, last: 15 },
    { bucket: "2026-06-17T10:30:00Z", avg: 16, min: 15, max: 17, last: 16 },
  ],
};

interface Fetchsteuerung {
  /** Löst die zuletzt abgesetzte Anfrage erfolgreich auf. */
  erfuelle: (daten: MachineTrendOut) => Promise<void>;
  /** Lässt die zuletzt abgesetzte Anfrage am WEG scheitern (Netz, Zeitablauf). */
  verwirf: (fehler: Error) => Promise<void>;
  aufrufe: () => number;
}

/**
 * Stellt `fetch` durch eine Anfrage, die von Hand aufgelöst wird. Der Zeitraum
 * ZWISCHEN Absenden und Antwort ist der eigentliche Prüfgegenstand — er existiert
 * bei einem sofort auflösenden Mock gar nicht.
 */
function stelleFetch(): Fetchsteuerung {
  let offen: { gut: (daten: MachineTrendOut) => void; schlecht: (fehler: Error) => void } | null =
    null;
  let n = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn(() => {
      n += 1;
      return new Promise<Response>((resolve, reject) => {
        offen = {
          gut: (daten) => resolve({ ok: true, status: 200, json: async () => daten } as Response),
          schlecht: (fehler) => reject(fehler),
        };
      });
    }),
  );
  const abschliessen = async (aktion: () => void): Promise<void> => {
    await act(async () => {
      aktion();
      // Die Kette hat ein `async`-Glied (response.json) — ein Mikrotask-Tick reicht
      // nicht, deshalb wird hier bis zur Ruhe durchgelassen.
      await Promise.resolve();
      await Promise.resolve();
    });
  };
  return {
    erfuelle: (daten) =>
      abschliessen(() => {
        if (offen === null) throw new Error("keine offene Anfrage");
        offen.gut(daten);
      }),
    verwirf: (fehler) =>
      abschliessen(() => {
        if (offen === null) throw new Error("keine offene Anfrage");
        offen.schlecht(fehler);
      }),
    aufrufe: () => n,
  };
}

function starte(hours: number) {
  // EIN Store je Lauf — ein je Bild neu gebauter Store würde die Abo-Wirkung des
  // Providers bei jedem Rendern neu aufziehen und den Ladepfad verfälschen.
  const store = new RealtimeStore(new FakeTransport());
  const wrapper = ({ children }: { children: ReactNode }) => (
    <RealtimeProvider store={store}>{children}</RealtimeProvider>
  );
  return renderHook(
    (props: { hours: number }) =>
      useMachineTrend({
        machineId: 7,
        dataPointId: 42,
        dataPointName: "spindle_temp",
        hours: props.hours,
      }),
    { wrapper, initialProps: { hours } },
  );
}

beforeEach(() => {
  vi.spyOn(Date, "now").mockReturnValue(NOW);
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("useMachineTrend — die Ladefenster-Marke", () => {
  it("steht vor der Antwort auf null und danach auf dem ANFANG DER ANFRAGE", async () => {
    // Belegt: Die Marke entsteht aus dem Fenster, das zurückkam — nicht beim
    // Absenden. Mutation, die genau das rötet: `setLoadedFromMs` vor den fetch
    // ziehen (Entwurf-1-Variante `now - hours*3.6e6`) — dann steht die Marke
    // schon in der ersten Zusicherung. Zweite Mutation: aus `samples[0].t`
    // ableiten — dann steht dort 10:00 statt 16.06. 11:00.
    const fetchSteuerung = stelleFetch();
    const { result } = starte(24);

    expect(result.current.loadedFromMs).toBeNull();

    await fetchSteuerung.erfuelle(historisch);

    await waitFor(() => expect(result.current.loadedFromMs).toBe(NOW - 24 * STUNDE_MS));
  });

  it("DER FEHLERZWEIG: ein gescheiterter Nachladeversuch schiebt die Marke NICHT", async () => {
    // Belegt die Fortschrittsmarken-Regel: Der Sprung von 24 h auf 72 h fragt einen
    // älteren Bereich an; scheitert der WEG, ist über diesen Bereich weiterhin
    // nichts bekannt. Die Marke bleibt deshalb auf dem alten, wirklich
    // beantworteten Anfang stehen.
    // Mutation, die das rötet: `setLoadedFromMs(requestedFromMs)` zusätzlich in den
    // `.catch()`-Zweig setzen.
    const fetchSteuerung = stelleFetch();
    const { result, rerender } = starte(24);
    await fetchSteuerung.erfuelle(historisch);
    await waitFor(() => expect(result.current.loadedFromMs).toBe(NOW - 24 * STUNDE_MS));

    rerender({ hours: 72 });
    await fetchSteuerung.verwirf(new Error("network"));

    await waitFor(() => expect(result.current.refetching).toBe(false));
    expect(result.current.loadedFromMs).toBe(NOW - 24 * STUNDE_MS);
    expect(fetchSteuerung.aufrufe()).toBe(2);
  });

  it("AUFBAU-KONTROLLE: derselbe Sprung mit geglückter Antwort schiebt die Marke sehr wohl", async () => {
    // Ohne diesen Zwilling bliebe der Fall darüber auch dann grün, wenn die Marke
    // nach dem ersten Erfolg überhaupt nie mehr fortgeschrieben würde — dann
    // schraffierte das Diagramm auf Dauer einen Bereich, den es längst hat.
    const fetchSteuerung = stelleFetch();
    const { result, rerender } = starte(24);
    await fetchSteuerung.erfuelle(historisch);
    await waitFor(() => expect(result.current.loadedFromMs).toBe(NOW - 24 * STUNDE_MS));

    rerender({ hours: 72 });
    await fetchSteuerung.erfuelle(historisch);

    await waitFor(() => expect(result.current.loadedFromMs).toBe(NOW - 72 * STUNDE_MS));
  });
});

describe("useMachineTrend — refetching", () => {
  it("ist beim allerersten Laden false — es steht noch kein Bild, das stehen bleiben könnte", async () => {
    // Belegt die zweite Hälfte der Bedingung. Mutation, die das rötet:
    // `refetching = !loaded` (ohne „Punkte im Bild") — dann meldete das Diagramm
    // schon beim Erstaufbau „wird geladen …" an einer Fläche, für die es noch gar
    // keinen Ausschnitt gibt.
    const fetchSteuerung = stelleFetch();
    const { result } = starte(24);

    expect(result.current.refetching).toBe(false);
    expect(result.current.state.kind).toBe("loading");

    await fetchSteuerung.erfuelle(historisch);
    await waitFor(() => expect(result.current.state.kind).not.toBe("loading"));
    expect(result.current.refetching).toBe(false);
  });

  it("ist zwischen Absenden und Antwort true, sobald Punkte im Bild stehen", async () => {
    // Belegt die erste Hälfte: Beim Nachladen bleibt das alte Bild stehen (der
    // Zustand trägt weiter Daten), und genau währenddessen darf der noch nicht
    // abgerufene Rand „wird geladen …" sagen statt „noch nicht abgerufen".
    // Mutation, die das rötet: `!loaded` aus der Bedingung entfernen.
    const fetchSteuerung = stelleFetch();
    const { result, rerender } = starte(24);
    await fetchSteuerung.erfuelle(historisch);
    await waitFor(() => expect(result.current.state.kind).toBe("cached"));
    expect(result.current.refetching).toBe(false);

    rerender({ hours: 72 });

    expect(result.current.refetching).toBe(true);
    // Die Kurve steht dabei WEITER im Bild — der Ladezustand wird nicht erreicht.
    expect(result.current.state.kind).toBe("cached");

    await fetchSteuerung.erfuelle(historisch);
    await waitFor(() => expect(result.current.refetching).toBe(false));
  });
});
