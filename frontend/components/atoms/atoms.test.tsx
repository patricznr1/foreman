// ============================================================
//  FOREMAN Frontend — components/atoms/atoms.test.tsx
//  Zweck: Plattform-Atome erfüllen ihre verbindlichen Eigenschaften:
//         StatusIndicator mehrkanalig (Farbe + Form + Label), KpiTile nie nackt
//         (Wert + Zustand), ProvenanceStamp trägt Frische/Stand + KI-Kennzeichnung.
//  Architektur-Einordnung: Quality-Gate (Akzeptanzkriterium Atome).
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { KpiTile } from "./kpi-tile";
import { ProvenanceStamp } from "./provenance-stamp";
import { StatusIndicator } from "./status-indicator";

describe("StatusIndicator — mehrkanalig (Farbe + Form + Label)", () => {
  it("trägt alle drei Kanäle", () => {
    render(<StatusIndicator status="failure" />);
    // Kanal Label
    const wrapper = screen.getByRole("img", { name: "Ausfall" });
    // Kanal Form (FCSM-Kürzel)
    expect(wrapper).toHaveTextContent("F");
    // Kanal Farbe (state-Token-Fill)
    expect(wrapper.querySelector(".bg-state-failure")).not.toBeNull();
  });

  it("vermittelt Bedeutung nicht allein über Farbe (aria-label + Kürzel)", () => {
    render(<StatusIndicator status="ok" />);
    const wrapper = screen.getByRole("img", { name: "Normal" });
    expect(wrapper).toHaveTextContent("OK");
  });
});

describe("KpiTile — nie nackte Zahl (Prinzip 6)", () => {
  it("zeigt Wert mit Label und Zustands-Indikator", () => {
    render(<KpiTile label="Offene Alarme" value={3} status="check" />);
    expect(screen.getByText("Offene Alarme")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Funktionsprüfung" })).toBeInTheDocument();
  });
});

describe("ProvenanceStamp — Herkunft/Frische + AI-Act-Kennzeichnung", () => {
  it("zeigt gecachten Stand", () => {
    render(<ProvenanceStamp freshness="cached" stampedAt={new Date("2026-06-16T12:30:00Z")} />);
    expect(screen.getByText(/Gecacht/)).toBeInTheDocument();
  });

  it("kennzeichnet KI-erzeugten Inhalt (AI-Act-Transparenz)", () => {
    render(<ProvenanceStamp freshness="live" aiGenerated />);
    expect(screen.getByText("KI-erzeugt")).toBeInTheDocument();
  });

  it("zeigt 'Verlauf' mit Stand (kein Live), wenn nur Historie vorliegt", () => {
    render(<ProvenanceStamp freshness="history" stampedAt={new Date("2026-06-25T12:30:00Z")} />);
    const stamp = screen.getByText(/Verlauf/);
    expect(stamp).toBeInTheDocument();
    // Ehrlich: kein grüner Live-Punkt über statischer Historie.
    expect(document.querySelector(".bg-state-ok")).toBeNull();
    expect(screen.queryByText(/Live/)).toBeNull();
  });
});
