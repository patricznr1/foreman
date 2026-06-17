// ============================================================
//  FOREMAN Frontend — components/cockpit/hidden-term.test.tsx
//  Zweck: Hidden-Term-Gate für Sektion A (GROUND_TRUTH §21.14, Studie §1.1/§4A). Das
//         Cockpit erscheint AUSSCHLIESSLICH in Hallensprache: das sichtbare Wording
//         (und die Screenreader-Labels) paraphrasieren „Drift" → „Abweichung" und
//         tragen kein internes Verfahrens-/Bibliotheks-/Implementierungs-Vokabular
//         (`DriftHeatmap`/`Schraffur`/`Intensität`/Roh-Enums/Stack-Namen). Render-
//         basierter Scan über sichtbaren DOM-Text + aria-Labels (wie memory/capture).
// ============================================================
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { MachineStatusOut } from "@/lib/api/contracts";
import { buildCockpitKpis } from "@/lib/cockpit/kpis";
import { buildHeatmapMatrix } from "@/lib/cockpit/matrix";
import { buildPriorityEntries } from "@/lib/cockpit/priority";

import { CockpitKpiRow } from "./cockpit-kpi-row";
import { CockpitScopeBar } from "./cockpit-scope-bar";
import { DriftHeatmap } from "./drift-heatmap";
import { PriorityColumn } from "./priority-column";

// Interne Begriffe, die im Sichtbaren NIE auftauchen dürfen (Paraphrase-Disziplin).
const FORBIDDEN = [
  "drift",
  "kipped",
  "fcsm",
  "severity",
  "schraffur",
  "intensität",
  "heatmap-fläche",
  "reasoner",
  "nexus",
  "river",
  "adwin",
  "pgvector",
  "lightgbm",
  "shap",
  "embedding",
  "drift_active",
  "open_warning",
  "machine_class",
];

const MACHINES: MachineStatusOut[] = [
  { id: 1, label: "Presse 1", line_id: 2, machine_class: "Presse", status: "healthy", open_alarm_count: 0, open_by_severity: {}, last_alarm_at: null },
  { id: 2, label: "Presse 2", line_id: 2, machine_class: "Presse", status: "drift_active", open_alarm_count: 1, open_by_severity: { warning: 1 }, last_alarm_at: null },
  { id: 3, label: "Spindel 1", line_id: 2, machine_class: "Spindel", status: "open_warning", open_alarm_count: 2, open_by_severity: { critical: 1, warning: 1 }, last_alarm_at: null },
];

/** Sammelt den gesamten nutzer-/screenreader-sichtbaren Text (Text + aria-Labels + titles). */
function visibleText(): string {
  const parts: string[] = [document.body.textContent ?? ""];
  for (const el of Array.from(document.querySelectorAll("[aria-label]"))) {
    parts.push(el.getAttribute("aria-label") ?? "");
  }
  for (const el of Array.from(document.querySelectorAll("title"))) {
    parts.push(el.textContent ?? "");
  }
  return parts.join(" ").toLowerCase();
}

describe("Hidden-Term-Scan (Sektion A)", () => {
  it("das gesamte Cockpit nutzt nur Hallensprache (kein internes Vokabular)", () => {
    const matrix = buildHeatmapMatrix(MACHINES);
    const kpis = buildCockpitKpis(MACHINES);
    render(
      <div>
        <CockpitScopeBar scope={{ machineClass: "Presse", lineId: 2 }} />
        <CockpitKpiRow kpis={kpis} history={{ availability: [90, 80], criticalOpen: [0, 1], driftCount: [0, 1] }} />
        <DriftHeatmap matrix={matrix} />
        <PriorityColumn entries={buildPriorityEntries(MACHINES)} />
      </div>,
    );

    // Eine Zelle ansteuern, damit auch die Mini-Vorschau gescannt wird.
    fireEvent.click(screen.getByRole("gridcell", { name: /Spindel 1/ }));

    const text = visibleText();
    for (const term of FORBIDDEN) {
      expect(text.includes(term)).toBe(false);
    }
  });
});
