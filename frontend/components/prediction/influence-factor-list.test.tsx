// ============================================================
//  FOREMAN Frontend — components/prediction/influence-factor-list.test.tsx
//  Zweck: Faktoren farbunabhängig (Wort + Balken) + Hidden-Term-Scan im DOM
//         (kein Verfahrensname / kein roher Tag); Werker knapp, Techniker Detail.
// ============================================================
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { toFactorRows } from "@/lib/prediction/factors";
import { SAMPLE_FACTORS } from "@/lib/prediction/testing/fixtures";
import { InfluenceFactorList } from "./influence-factor-list";

const FORBIDDEN = /shap|lightgbm|gradient|boosting|__|\b(mean|slope|rms|roc|std)\b/i;

describe("InfluenceFactorList", () => {
  it("Werker (knapp): höchstens zwei Faktoren", () => {
    render(<InfluenceFactorList factors={toFactorRows(SAMPLE_FACTORS)} detail={false} />);
    const region = screen.getByRole("region", { name: "Einflussfaktoren" });
    expect(within(region).getAllByRole("listitem").length).toBeLessThanOrEqual(2);
  });

  it("Techniker (Detail): alle Faktoren", () => {
    const rows = toFactorRows(SAMPLE_FACTORS);
    render(<InfluenceFactorList factors={rows} detail={true} />);
    expect(screen.getAllByRole("listitem").length).toBe(rows.length);
  });

  it("Hidden-Term-Scan: kein Verfahrensname / kein roher Tag im sichtbaren Text", () => {
    render(<InfluenceFactorList factors={toFactorRows(SAMPLE_FACTORS)} detail={true} />);
    const region = screen.getByRole("region", { name: "Einflussfaktoren" });
    expect(region.textContent ?? "").not.toMatch(FORBIDDEN);
  });

  it("trägt die Richtung als Wort (farbunabhängig, nicht nur Farbe)", () => {
    render(<InfluenceFactorList factors={toFactorRows(SAMPLE_FACTORS)} detail={true} />);
    expect(screen.getAllByText(/treibt das Risiko hoch|senkt das Risiko/).length).toBeGreaterThan(0);
  });
});
