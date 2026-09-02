// ============================================================
//  FOREMAN Frontend — components/machine/machine-trend-panel-gesten.test.tsx
//  Zweck: Das Panel reicht Gesten UNVERAENDERT nach oben durch.
//  ANLASS (02.09.2026, an dieser Stelle gemessen): Eine Mutation, die beim
//         Durchreichen das Vorzeichen dreht (`onPan={(f) => onPan(-f)}`), lief
//         durch ALLE 79 Tests des Ordners, ohne dass einer rot wurde. Der Fehler
//         zeigt sich erst am Geraet — der Inhalt laeuft der Hand entgegen —, und
//         das ist die teuerste Sorte: Sie ueberlebt jede Pruefung und faellt dem
//         Werker auf.
//  WARUM DIE FLAECHE HIER ERSETZT WIRD: Ihre eigene Umrechnung ist in
//         trend-viewport-surface.test.tsx mit 19 Gegenproben belegt; hier geht es
//         allein um die NAHTSTELLE. Die echten Zeiger-Ereignisse dafuer zu bauen
//         waere in jsdom aufwendig (PointerEvent und Touch gibt es dort nicht) und
//         wuerde die Naht hinter der Gestenmathematik verstecken.
//  DIE FALLE, gegen die das gebaut ist: Die Flaeche dreht das Vorzeichen aus
//         `gesture.ts` bereits GENAU EINMAL — ein Zeigerweg nach rechts zieht den
//         Ausschnitt in die Vergangenheit. Wer beim Verdrahten ein zweites Mal
//         dreht, hebt das auf.
// ============================================================
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DataPointRead, MachineTrendOut } from "@/lib/api/contracts";
import { RealtimeProvider } from "@/lib/realtime/realtime-context";
import { RealtimeStore } from "@/lib/realtime/realtime-store";
import { FakeTransport } from "@/lib/realtime/testing/fake-transport";

import type { TrendViewportSurfaceProps } from "./trend-viewport-surface";
import { MachineTrendPanel } from "./machine-trend-panel";

vi.mock("./trend-viewport-surface", () => ({
  TrendViewportSurface: ({ onPan, onZoom, onGestureEnd, children }: TrendViewportSurfaceProps) => (
    <div>
      <button type="button" onClick={() => onPan(0.2)}>
        probe-pan
      </button>
      <button type="button" onClick={() => onZoom(2, 0.75)}>
        probe-zoom
      </button>
      <button type="button" onClick={() => onGestureEnd()}>
        probe-ende
      </button>
      {children}
    </div>
  ),
}));

const NOW = Date.parse("2026-06-17T12:00:00Z");

const dataPoint: DataPointRead = {
  id: 42,
  machine_id: 7,
  component_id: null,
  name: "spindle_temp",
  unit: "°C",
  kind: "analog",
  measurement_type: "temperature",
  source: "simulation",
  address: null,
  normal_min: 10,
  normal_max: 20,
  created_at: "2026-06-01T00:00:00Z",
};

// Die Huelle rendert ihre Kinder — und damit die Gestenflaeche — erst, wenn
// Daten da sind. Ohne echte Punkte gaebe es die Sonden-Knoepfe gar nicht, und
// der Test bliebe an einer Kulisse haengen statt an der Naht.
const historical: MachineTrendOut = {
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

afterEach(() => {
  vi.unstubAllGlobals();
});

async function zeige() {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok: true, json: async () => historical }),
  );
  const onPan = vi.fn();
  const onZoom = vi.fn();
  const onGestureEnd = vi.fn();
  const store = new RealtimeStore(new FakeTransport());
  render(
    <RealtimeProvider store={store}>
      <MachineTrendPanel
        machineId={7}
        dataPoint={dataPoint}
        viewport={{ mode: "follow", spanMs: 24 * 3_600_000 }}
        hours={24}
        onPan={onPan}
        onZoom={onZoom}
        onGestureEnd={onGestureEnd}
        nowMs={NOW}
      />
    </RealtimeProvider>,
  );
  // Auf das geladene Bild warten: Vorher gibt es die Flaeche nicht.
  await screen.findByRole("button", { name: "probe-pan" });
  return { onPan, onZoom, onGestureEnd };
}

describe("MachineTrendPanel — Gesten-Naht", () => {
  it("DER TRAGENDE FALL: das Vorzeichen des Schubs bleibt unveraendert", async () => {
    const { onPan } = await zeige();
    await userEvent.click(screen.getByRole("button", { name: "probe-pan" }));

    // +0,2 hinein, +0,2 hinaus. Ein `-f` an der Naht macht daraus −0,2, und der
    // Ausschnitt liefe der Hand entgegen.
    expect(onPan).toHaveBeenCalledWith(0.2);
    expect(onPan).not.toHaveBeenCalledWith(-0.2);
  });

  it("Faktor UND Ankeranteil des Zooms kommen in dieser Reihenfolge an", async () => {
    // Vertauschte Argumente waeren besonders heimtueckisch: Beide sind Zahlen,
    // beide plausibel, und `zoomViewport` klemmt den Anker auf 0..1 — ein Faktor 2
    // als Anker landete stillschweigend auf 1 (rechter Rand).
    const { onZoom } = await zeige();
    await userEvent.click(screen.getByRole("button", { name: "probe-zoom" }));
    expect(onZoom).toHaveBeenCalledWith(2, 0.75);
  });

  it("das Gestenende erreicht die Sicht — sonst bleibt die Ansage stumm", async () => {
    const { onGestureEnd } = await zeige();
    await userEvent.click(screen.getByRole("button", { name: "probe-ende" }));
    expect(onGestureEnd).toHaveBeenCalledTimes(1);
  });
});
