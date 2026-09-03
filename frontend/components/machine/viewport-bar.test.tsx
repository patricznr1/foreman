// ============================================================
//  FOREMAN Frontend — components/machine/viewport-bar.test.tsx
//  Zweck: Sichert die Bedienleiste des Sensortrend-Ausschnitts. Schwerpunkte:
//         GENAU EINE Live-Region für die Sektion, der feste Text des Jetzt-Knopfes,
//         die Spiegelung der Grenzen in `disabled` samt sichtbarem Grund, die
//         Vorzeichen der gemeldeten Absichten und die zurückgelesene Schnellwahl.
//         Kein Layout nötig: der Zeitanker kommt als `nowMs`-Requisite herein.
// ============================================================
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { MAX_SPAN_MS, MIN_SPAN_MS, presetViewport, type TrendViewport } from "@/lib/machine/viewport";

import { ViewportBar, type ViewportBarProps } from "./viewport-bar";

const NOW = Date.UTC(2026, 8, 2, 12, 0, 0);
const MINUTE = 60_000;
const HOUR = 60 * MINUTE;

/** Ein stehender Ausschnitt der Breite `spanMs`, dessen rechter Rand `behindMs` zurückliegt. */
function frozen(behindMs: number, spanMs: number): TrendViewport {
  const endMs = NOW - behindMs;
  return { mode: "frozen", startMs: endMs - spanMs, endMs };
}

function renderBar(overrides: Partial<ViewportBarProps> = {}) {
  const props: ViewportBarProps = {
    viewport: presetViewport("day"),
    nowMs: NOW,
    announcement: "",
    onQuickPick: vi.fn(),
    onZoom: vi.fn(),
    onPan: vi.fn(),
    onNow: vi.fn(),
    ...overrides,
  };
  return { props, ...render(<ViewportBar {...props} />) };
}

/** Nur die fünf Ausschnitts-Knöpfe — ohne die Knöpfe der Schnellwahl daneben. */
function controls() {
  return within(screen.getByRole("group", { name: "Ausschnitt bedienen" }));
}

describe("ViewportBar", () => {
  it("hält GENAU EINE Live-Region für die ganze Leiste bereit und spricht nur durch sie", () => {
    // Belegt die tragende Zusicherung: Drei gestapelte Sensoren teilen sich EINE
    // Ansage. Wäre die Statuszeile (oder ein Panel) eine zweite Live-Region,
    // kündigte eine Vorlesehilfe denselben Vorgang mehrfach an.
    // ROT WIRD DIESER TEST, wenn der Statuszeile role="status"/aria-live gegeben
    // wird — oder wenn die Region erst mit ihrem Text in den Baum kommt.
    const { container, rerender, props } = renderBar({ announcement: "" });

    expect(screen.getAllByRole("status")).toHaveLength(1);
    expect(container.querySelectorAll("[aria-live]")).toHaveLength(1);

    const region = screen.getByRole("status");
    expect(region).toHaveAttribute("aria-live", "polite");
    expect(region.textContent).toBe("");

    rerender(<ViewportBar {...props} announcement="Ausschnitt 2 Stunden bis jetzt, folgt dem Live-Rand" />);
    expect(screen.getByRole("status").textContent).toBe(
      "Ausschnitt 2 Stunden bis jetzt, folgt dem Live-Rand",
    );
    expect(screen.getAllByRole("status")).toHaveLength(1);
  });

  it("zeigt „Jetzt“ genau im festen Zustand — im Folge-Modus gar nicht", () => {
    // Beide Richtungen: der Ausweg aus dem festen Zustand existiert genau dann,
    // wenn man ihn braucht, und belegt sonst keinen Platz in der Handschuh-Leiste.
    // ROT, wenn „Jetzt“ unbedingt gerendert wird.
    renderBar({ viewport: presetViewport("day") });
    expect(controls().queryByRole("button", { name: /Jetzt/ })).toBeNull();
    cleanup();

    renderBar({ viewport: frozen(3 * HOUR, 2 * HOUR) });
    expect(controls().getByRole("button", { name: /Jetzt/ })).toBeEnabled();
  });

  it("lässt den Text des Jetzt-Knopfes fest, während der Abstand daneben hochzählt", () => {
    // Ein Label, das sich selbst verändert, lässt das Ziel unter der greifenden
    // Hand wandern — mit Handschuh ein echtes Problem. Der zählende Teil gehört
    // deshalb in die Statuszeile daneben.
    // ROT, sobald der Abstand in den Knopftext oder in sein aria-label wandert.
    renderBar({ viewport: frozen(2 * HOUR + 14 * MINUTE, 2 * HOUR) });
    const early = controls().getByRole("button", { name: /Jetzt/ });
    const earlyText = early.textContent;
    const earlyLabel = early.getAttribute("aria-label");
    expect(earlyText).toBe("Jetzt");
    expect(screen.getByText(/steht fest · 2 Stunden 14 Minuten hinter dem Live-Rand/)).toBeInTheDocument();
    cleanup();

    renderBar({ viewport: frozen(5 * HOUR + 30 * MINUTE, 2 * HOUR) });
    const later = controls().getByRole("button", { name: /Jetzt/ });
    expect(later.textContent).toBe(earlyText);
    expect(later.getAttribute("aria-label")).toBe(earlyLabel);
    // Aufbau-Kontrolle im selben Test: der Abstand hat sich wirklich geändert —
    // sonst belegte die Gleichheit oben nur, dass beide Bilder identisch sind.
    expect(screen.getByText(/steht fest · 5 Stunden 30 Minuten hinter dem Live-Rand/)).toBeInTheDocument();
  });

  it("sperrt „+“ am Auflösungsboden und nennt den Grund; darüber ist er frei", () => {
    // ROT, wenn die disabled-Bindung an isAtFloor durch ein festes false ersetzt
    // wird — oder wenn der Grund neben dem grauen Knopf fehlt.
    renderBar({ viewport: { mode: "follow", spanMs: MIN_SPAN_MS } });
    expect(controls().getByRole("button", { name: "Hineinzoomen" })).toBeDisabled();
    expect(screen.getByText("Feinste Auflösung: 1 Minute je Punkt")).toBeInTheDocument();
    cleanup();

    renderBar({ viewport: { mode: "follow", spanMs: 4 * MIN_SPAN_MS } });
    expect(controls().getByRole("button", { name: "Hineinzoomen" })).toBeEnabled();
    expect(screen.queryByText(/Feinste Auflösung/)).toBeNull();
  });

  it("sperrt „Älter“ an der 7-Tage-Wand und nennt den Grund; davor ist er frei", () => {
    // ROT, wenn die disabled-Bindung an isAtWall durch ein festes false ersetzt wird.
    renderBar({
      viewport: { mode: "frozen", startMs: NOW - MAX_SPAN_MS, endMs: NOW - MAX_SPAN_MS + 2 * HOUR },
    });
    expect(controls().getByRole("button", { name: /^Älter/ })).toBeDisabled();
    expect(screen.getByText("Älter als 7 Tage: kein Verlauf über diese Ansicht")).toBeInTheDocument();
    // Herauszoomen ist an der Wand NICHT gesperrt — die Spanne ist noch klein.
    expect(controls().getByRole("button", { name: "Herauszoomen" })).toBeEnabled();
    cleanup();

    renderBar({ viewport: presetViewport("day") });
    expect(controls().getByRole("button", { name: /^Älter/ })).toBeEnabled();
    expect(screen.queryByText(/kein Verlauf über diese Ansicht/)).toBeNull();
  });

  it("sperrt „−“ am weitesten Ausschnitt — und dort steht der Wand-Grund bereits", () => {
    // Fordert das Zusammenfallen ein, das der Quelltext behauptet: eine Spanne von
    // MAX_SPAN_MS reicht zwangsläufig bis an die Wand, deshalb braucht die Decke
    // keinen eigenen Begründungstext. ROT, sobald eines von beidem nicht mehr gilt.
    renderBar({ viewport: { mode: "follow", spanMs: MAX_SPAN_MS } });
    expect(controls().getByRole("button", { name: "Herauszoomen" })).toBeDisabled();
    expect(screen.getByText("Älter als 7 Tage: kein Verlauf über diese Ansicht")).toBeInTheDocument();
  });

  it("sperrt „Neuer“ am Live-Rand und gibt ihn im festen Zustand frei", () => {
    // ROT, wenn die disabled-Bindung an den Folge-Modus wegfällt.
    renderBar({ viewport: presetViewport("day") });
    expect(controls().getByRole("button", { name: /^Neuer/ })).toBeDisabled();
    expect(screen.getByText("folgt dem Live-Rand")).toBeInTheDocument();
    cleanup();

    renderBar({ viewport: frozen(3 * HOUR, 2 * HOUR) });
    expect(controls().getByRole("button", { name: /^Neuer/ })).toBeEnabled();
  });

  it("meldet genau die vereinbarten Absichten — samt Vorzeichen und Zoom-Richtung", () => {
    // Die Vorzeichen sind hier tragend: `panViewport` schiebt POSITIV Richtung
    // Live-Rand, `zoomViewport` zoomt mit Faktor > 1 HINEIN. Eine vertauschte Zahl
    // bewegt das Bild in die falsche Richtung, ohne zu werfen.
    // ROT bei jeder vertauschten Zahl.
    const onZoom = vi.fn();
    const onPan = vi.fn();
    const onNow = vi.fn();
    renderBar({ viewport: frozen(3 * HOUR, 2 * HOUR), onZoom, onPan, onNow });

    fireEvent.click(controls().getByRole("button", { name: "Herauszoomen" }));
    fireEvent.click(controls().getByRole("button", { name: "Hineinzoomen" }));
    expect(onZoom).toHaveBeenNthCalledWith(1, 0.5, 0.5);
    expect(onZoom).toHaveBeenNthCalledWith(2, 2, 0.5);

    fireEvent.click(controls().getByRole("button", { name: /^Älter/ }));
    fireEvent.click(controls().getByRole("button", { name: /^Neuer/ }));
    expect(onPan).toHaveBeenNthCalledWith(1, -0.25);
    expect(onPan).toHaveBeenNthCalledWith(2, 0.25);

    fireEvent.click(controls().getByRole("button", { name: /Jetzt/ }));
    expect(onNow).toHaveBeenCalledTimes(1);
  });

  it("liest die gedrückte Schnellwahl aus dem Ausschnitt zurück statt sie zu speichern", () => {
    // Ein gedrückter „Tag“-Knopf über einem 20-Minuten-Bild wäre eine
    // Falschaussage im Bedienelement selbst.
    // ROT, wenn statt matchPreset eine feste oder gemerkte ID durchgereicht wird.
    renderBar({ viewport: presetViewport("day") });
    expect(screen.getByRole("button", { name: "Tag" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Woche" })).toHaveAttribute("aria-pressed", "false");
    cleanup();

    renderBar({ viewport: { mode: "follow", spanMs: MIN_SPAN_MS } });
    for (const label of ["Schicht", "Tag", "Woche"]) {
      expect(screen.getByRole("button", { name: label })).toHaveAttribute("aria-pressed", "false");
    }
  });

  it("bleibt bei entarteten Ausschnitten lesbar: keine NaN, keine negativen Dauern", () => {
    // Spanne 0, ein rechter Rand hinter dem Jetzt und vertauschte Grenzen kommen
    // aus clampViewport nie heraus — aber ein NaN oder eine negative Dauer in einer
    // Beschriftung fällt beim Hinsehen nicht auf.
    // ROT, sobald eine der Dauern an `describeSpan` vorbei gerechnet wird.
    const { container: leer } = renderBar({ viewport: { mode: "follow", spanMs: 0 } });
    expect(leer.textContent).not.toMatch(/NaN/);
    expect(leer.textContent).not.toMatch(/-\d/);
    expect(within(leer).getByText("Ausschnitt: 0 Minuten")).toBeInTheDocument();
    cleanup();

    const { container: zukunft } = renderBar({
      viewport: { mode: "frozen", startMs: NOW, endMs: NOW + HOUR },
    });
    expect(zukunft.textContent).not.toMatch(/NaN/);
    expect(zukunft.textContent).not.toMatch(/-\d/);
    expect(within(zukunft).getByText(/steht fest · 0 Minuten hinter dem Live-Rand/)).toBeInTheDocument();
    cleanup();

    // Vertauschte Grenzen: die Spanne wäre negativ.
    const { container: verdreht } = renderBar({
      viewport: { mode: "frozen", startMs: NOW, endMs: NOW - HOUR },
    });
    expect(verdreht.textContent).not.toMatch(/NaN/);
    expect(verdreht.textContent).not.toMatch(/-\d/);
    expect(within(verdreht).getByText("Ausschnitt: 0 Minuten")).toBeInTheDocument();
  });

  it("gibt jedem Knopf der Leiste das Handschuh-Trefferziel", () => {
    // ≥56 px über die `touch-target`-Utility (§5.4). ROT, sobald ein Knopf sie
    // verliert — geprüft wird jeder einzeln, nicht ihre Anzahl.
    renderBar({ viewport: frozen(3 * HOUR, 2 * HOUR) });
    const buttons = controls().getAllByRole("button");
    expect(buttons).toHaveLength(5);
    for (const button of buttons) {
      expect(button).toHaveClass("touch-target");
    }
  });
});
