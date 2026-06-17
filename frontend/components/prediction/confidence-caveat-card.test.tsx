// ============================================================
//  FOREMAN Frontend — components/prediction/confidence-caveat-card.test.tsx
//  Zweck: Vier-Block fester Reihenfolge; Konfidenz ⊕ Vorbehalt im SELBEN Rahmen;
//         Vorbehalt nicht wegklappbar; keine Scheingenauigkeit.
// ============================================================
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { predictionRoleView } from "@/lib/prediction/roles";
import {
  DETERMINISTIC_CAVEAT,
  makePrediction,
  makeRecommendation,
} from "@/lib/prediction/testing/fixtures";
import { assemblePredictionCard } from "@/lib/prediction/view-model";
import { ConfidenceCaveatCard } from "./confidence-caveat-card";

vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

function buildCard() {
  const result = assemblePredictionCard(makePrediction(), makeRecommendation());
  if (!result.ok) {
    throw new Error("Fixture sollte eine gültige Karte ergeben");
  }
  return result.card;
}

describe("ConfidenceCaveatCard", () => {
  it("rendert die vier Blöcke in FESTER Reihenfolge (Zahl → Warum → Tu-das → Aber-bedenke)", () => {
    render(
      <ConfidenceCaveatCard
        card={buildCard()}
        roleView={predictionRoleView("shift_lead")}
        onDecide={() => {}}
      />,
    );
    const article = screen.getByRole("article");
    const order = [...article.querySelectorAll("[data-block]")].map((b) => b.getAttribute("data-block"));
    expect(order).toEqual(["confidence", "factors", "recommendation", "caveat"]);
  });

  it("zeigt Konfidenz UND Vorbehalt im SELBEN Rahmen (man sieht das eine nie ohne das andere)", () => {
    render(<ConfidenceCaveatCard card={buildCard()} roleView={predictionRoleView("worker")} />);
    const article = screen.getByRole("article");
    expect(article.querySelector('[data-block="confidence"]')).not.toBeNull();
    expect(article.querySelector('[data-block="caveat"]')).not.toBeNull();
    expect(within(article).getByText(DETERMINISTIC_CAVEAT)).toBeInTheDocument();
  });

  it("der Vorbehalt ist NICHT wegklappbar (kein details/summary, kein Aufklapp-Button im Block)", () => {
    render(<ConfidenceCaveatCard card={buildCard()} roleView={predictionRoleView("worker")} />);
    const caveat = document.querySelector('[data-block="caveat"]') as HTMLElement;
    expect(caveat.closest("details")).toBeNull();
    expect(within(caveat).queryByRole("button")).toBeNull();
  });

  it("zeigt KEINE Scheingenauigkeit: kein roher Prozentwert 82, aber die verbale Stufe", () => {
    render(<ConfidenceCaveatCard card={buildCard()} roleView={predictionRoleView("worker")} />);
    expect(screen.queryByText(/82\s*%/)).toBeNull();
    expect(screen.getByText("hohes Risiko")).toBeInTheDocument();
  });
});
