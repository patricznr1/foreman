// ============================================================
//  FOREMAN Frontend — components/memory/relation-view.test.tsx
//  Zweck: Verknüpfungs-Ansicht — Label + Begründung (farbunabhängig); reservierte
//         Typen (Klasse/Ursache) ehrlich als folgt markiert, nicht erfunden.
// ============================================================
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RelationView } from "./relation-view";

describe("RelationView", () => {
  it("zeigt Beziehungen farbunabhängig per Label und faktischer Begründung", () => {
    render(
      <RelationView
        relations={[{ type: "same_machine", hitIds: [1, 2], reason: "2 Hinweise an Maschine 7" }]}
      />,
    );
    expect(screen.getByText("Gleiche Maschine")).toBeInTheDocument();
    expect(screen.getByText("2 Hinweise an Maschine 7")).toBeInTheDocument();
  });

  it("markiert reservierte Verknüpfungstypen ehrlich als folgt", () => {
    render(<RelationView relations={[]} />);
    expect(screen.getByText(/Keine gemeinsamen Bezüge/)).toBeInTheDocument();
    expect(screen.getByText(/Maschinenklasse.*gemeinsame Ursache folgt/)).toBeInTheDocument();
  });
});
