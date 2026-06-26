// ============================================================
//  FOREMAN Frontend — components/memory/archive-result-card.test.tsx
//  Zweck: Archiv-Treffer-Karte — Quellen-Glyph je source_type, Wortlaut-Auszug,
//         Maschine, quellenspezifische Detail-Chips. SCHLICHT: KEINE Relevanz-Stufe
//         (kein Prozent/„Rang/Nähe"), KEIN Autor, KEINE erfundene Auflösung.
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ArchiveHitView } from "@/lib/memory/types";
import { ArchiveResultCard } from "./archive-result-card";

function hit(over: Partial<ArchiveHitView> = {}): ArchiveHitView {
  return {
    source: "note",
    id: 1,
    machineId: 12,
    timestamp: "2026-06-10T08:00:00+00:00",
    excerpt: "Lager läuft heiß, zu wenig Fett.",
    detail: { shift: "Früh" },
    rank: 0,
    ...over,
  };
}

describe("ArchiveResultCard", () => {
  it("spiegelt den Quellen-Glyph je source_type (Notiz/Wartung/Alarm)", () => {
    const { rerender } = render(<ArchiveResultCard hit={hit({ source: "note" })} largeCards={false} />);
    expect(screen.getByLabelText("Schichtnotiz")).toBeInTheDocument();
    rerender(
      <ArchiveResultCard
        hit={hit({ source: "maintenance", detail: { type: "lubrication" } })}
        largeCards={false}
      />,
    );
    expect(screen.getByLabelText("Wartung")).toBeInTheDocument();
    rerender(
      <ArchiveResultCard
        hit={hit({ source: "alarm", detail: { severity: "warning", category: "process", code: "ILL-7" } })}
        largeCards={false}
      />,
    );
    expect(screen.getByLabelText("Alarm")).toBeInTheDocument();
  });

  it("zeigt Auszug, Maschine und Quell-Details — KEIN Prozent, KEINE Relevanz-Stufe, KEIN Autor", () => {
    render(
      <ArchiveResultCard
        hit={hit({
          source: "alarm",
          excerpt: "Beleuchtung in Halle 2 defekt.",
          detail: { severity: "warning", category: "process", code: "ILL-7" },
        })}
        largeCards={false}
      />,
    );
    expect(screen.getByText("Beleuchtung in Halle 2 defekt.")).toBeInTheDocument();
    expect(screen.getByText(/Maschine 12/)).toBeInTheDocument();
    expect(screen.getByText(/Schwere: warning/)).toBeInTheDocument();
    expect(screen.getByText(/Bereich: process/)).toBeInTheDocument();
    expect(screen.getByText(/Code ILL-7/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/%/);
    expect(screen.queryByText(/Rang/)).toBeNull();
    expect(screen.queryByText(/Nähe/)).toBeNull();
  });

  it("verlinkt zur Maschine (B), wenn ein Maschinenbezug besteht", () => {
    render(<ArchiveResultCard hit={hit({ machineId: 7 })} largeCards={false} />);
    expect(screen.getByRole("link", { name: "An Maschine ansehen" })).toHaveAttribute(
      "href",
      "/machines/7",
    );
  });

  it("ohne Maschinenbezug: kein Maschinen-Link", () => {
    render(<ArchiveResultCard hit={hit({ machineId: null })} largeCards={false} />);
    expect(screen.queryByRole("link", { name: "An Maschine ansehen" })).toBeNull();
    expect(screen.getByText(/ohne Maschinenbezug/)).toBeInTheDocument();
  });
});
