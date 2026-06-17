// ============================================================
//  FOREMAN Frontend — components/prediction/confidence-band.test.tsx
//  Zweck: Konfidenz-Band — verbale Stufe + grober Bereich + Vorlauf, keine
//         Scheingenauigkeit (kein roher Prozentwert).
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { deriveConfidence } from "@/lib/prediction/confidence";
import { makePrediction } from "@/lib/prediction/testing/fixtures";
import { ConfidenceBand } from "./confidence-band";

describe("ConfidenceBand", () => {
  it("zeigt verbale Stufe, groben Bereich und Vorlauf — keinen rohen Prozentwert", () => {
    render(
      <ConfidenceBand
        confidence={deriveConfidence(makePrediction({ probability: 0.82, decision_threshold: 0.5 }))}
        horizonH={336}
      />,
    );
    expect(screen.getByText("hohes Risiko")).toBeInTheDocument();
    expect(screen.getByText(/ca\. 80/)).toBeInTheDocument();
    expect(screen.getByText(/Vorlauf: 14 Tage/)).toBeInTheDocument();
    expect(screen.queryByText(/82\s*%/)).toBeNull();
  });
});
