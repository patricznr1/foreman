// ============================================================
//  FOREMAN Frontend — components/prediction/caveat-block.test.tsx
//  Zweck: Vorbehalt-Block — deterministischer Text, festes Symbol, Negativ-Guard.
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { deriveCaveat } from "@/lib/prediction/caveat";
import { DETERMINISTIC_CAVEAT, makeRecommendation } from "@/lib/prediction/testing/fixtures";
import { CaveatBlock } from "./caveat-block";

describe("CaveatBlock", () => {
  it("zeigt den deterministischen Vorbehalt mit festem Symbol (role=note)", () => {
    const caveat = deriveCaveat(makeRecommendation());
    expect(caveat).not.toBeNull();
    render(<CaveatBlock caveat={caveat!} />);
    const note = screen.getByRole("note", { name: "Vorbehalt" });
    expect(note).toBeInTheDocument();
    expect(screen.getByText(DETERMINISTIC_CAVEAT)).toBeInTheDocument();
    expect(note.querySelector("svg")).not.toBeNull();
  });

  it("nennt Datenbasis + Validierung in Hallensprache", () => {
    render(<CaveatBlock caveat={deriveCaveat(makeRecommendation())!} />);
    expect(screen.getByText("Simulation")).toBeInTheDocument();
    expect(screen.getByText("nicht an realen Ausfällen validiert")).toBeInTheDocument();
  });

  it("defensive zweite Linie: leerer Vorbehalt → Fehlerhinweis (role=alert), nie als Karte", () => {
    render(
      <CaveatBlock caveat={{ text: "", validationStatus: "simulation_only", dataRegime: "simulation" }} />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("Vorbehalt fehlt");
  });
});
