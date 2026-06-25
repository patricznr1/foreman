// ============================================================
//  FOREMAN Frontend — lib/synoptic3d/layout.test.ts
//  Zweck: Prüft die datengetriebene Anordnung der Linie ohne THREE/DOM —
//         12 Maschinen in kanonischer Sequenz, Materialfluss entlang +x, kranke
//         Maschine zwischen gesunden Schwestern, Stufen-Lücke > Intra-Lücke,
//         Zentrierung, Rand-/Sonderfälle.
//  Architektur-Einordnung: Test (Schicht 1), reine Logik.
// ============================================================
import { describe, expect, it } from "vitest";

import { buildLineLayout } from "./layout";
import type { MachinePlacement } from "./types";
import { makeMachineStatus, makeParkMachines } from "./testing/fixtures";

/** Kante-zu-Kante-Lücke zwischen zwei in +x benachbarten Maschinen. */
function edgeGap(left: MachinePlacement, right: MachinePlacement): number {
  const leftRightEdge = left.position.x + left.proportions.width / 2;
  const rightLeftEdge = right.position.x - right.proportions.width / 2;
  return rightLeftEdge - leftRightEdge;
}

describe("buildLineLayout", () => {
  it("ordnet die 12 Park-Maschinen in kanonischer Stufen-Sequenz an", () => {
    const placements = buildLineLayout(makeParkMachines());

    expect(placements).toHaveLength(12);
    // Stufe (kanonisch) → id je Klasse: Fördern(5,6) → Pressen(7,8,9) →
    // Handling(1,2,3,4) → Bestücken(10,11) → Endkontrolle(12).
    expect(placements.map((p) => p.machineId)).toEqual([5, 6, 7, 8, 9, 1, 2, 3, 4, 10, 11, 12]);
    expect(placements.map((p) => p.stage)).toEqual([
      "Fördern",
      "Fördern",
      "Pressen",
      "Pressen",
      "Pressen",
      "Handling",
      "Handling",
      "Handling",
      "Handling",
      "Bestücken",
      "Bestücken",
      "Endkontrolle",
    ]);
  });

  it("legt die Materialfluss-Richtung als streng steigendes x an", () => {
    const placements = buildLineLayout(makeParkMachines());
    for (let i = 1; i < placements.length; i += 1) {
      expect(placements[i]!.position.x).toBeGreaterThan(placements[i - 1]!.position.x);
    }
  });

  it("stellt eine kranke Maschine räumlich zwischen ihre gesunden Schwestern", () => {
    // Reihenfolge bewusst gemischt — die Sortierung muss PR-02 (id 8) in die Mitte holen.
    const presses = [
      makeMachineStatus({ id: 9, machine_class: "servo_press", status: "healthy" }),
      makeMachineStatus({ id: 7, machine_class: "servo_press", status: "healthy" }),
      makeMachineStatus({ id: 8, machine_class: "servo_press", status: "drift_active" }),
    ];
    const placements = buildLineLayout(presses);

    expect(placements.map((p) => p.machineId)).toEqual([7, 8, 9]);
    const [pr1, pr2, pr3] = placements as [MachinePlacement, MachinePlacement, MachinePlacement];
    expect(pr2.machineId).toBe(8);
    expect(pr2.status).toBe("drift_active");
    // Die einzige nicht-gesunde steht zwischen zwei gesunden — der Differenzierer wird räumlich.
    expect(pr1.status).toBe("healthy");
    expect(pr3.status).toBe("healthy");
    expect(pr2.position.x).toBeGreaterThan(pr1.position.x);
    expect(pr2.position.x).toBeLessThan(pr3.position.x);
  });

  it("trennt Stufen mit größerer Lücke als Maschinen innerhalb einer Stufe", () => {
    const placements = buildLineLayout(makeParkMachines(), { intraGap: 1, stageGap: 3 });

    // FD-01 (id5) → FD-02 (id6): gleiche Stufe → Intra-Lücke.
    const intra = edgeGap(placements[0]!, placements[1]!);
    // FD-02 (id6) → PR-01 (id7): Stufenwechsel → Stufen-Lücke.
    const between = edgeGap(placements[1]!, placements[2]!);

    expect(intra).toBeCloseTo(1, 6);
    expect(between).toBeCloseTo(3, 6);
    expect(between).toBeGreaterThan(intra);
  });

  it("zentriert die Linie um den Ursprung (x)", () => {
    const placements = buildLineLayout(makeParkMachines());
    const first = placements[0]!;
    const last = placements[placements.length - 1]!;
    const leftEdge = first.position.x - first.proportions.width / 2;
    const rightEdge = last.position.x + last.proportions.width / 2;
    expect(leftEdge).toBeCloseTo(-rightEdge, 6);
  });

  it("zählt stageIndex und indexInStage je Stufe korrekt", () => {
    const placements = buildLineLayout(makeParkMachines());
    const byId = new Map(placements.map((p) => [p.machineId, p]));

    expect(byId.get(5)).toMatchObject({ stageIndex: 0, indexInStage: 0 }); // FD-01
    expect(byId.get(6)).toMatchObject({ stageIndex: 0, indexInStage: 1 }); // FD-02
    expect(byId.get(7)).toMatchObject({ stageIndex: 1, indexInStage: 0 }); // PR-01
    expect(byId.get(9)).toMatchObject({ stageIndex: 1, indexInStage: 2 }); // PR-03
    expect(byId.get(1)).toMatchObject({ stageIndex: 2, indexInStage: 0 }); // AX-01
    expect(byId.get(12)).toMatchObject({ stageIndex: 4, indexInStage: 0 }); // VS-01
  });

  it("reiht unbekannte Klassen hinter die bekannten, fehlende ganz nach hinten", () => {
    const machines = [
      makeMachineStatus({ id: 1, machine_class: "feeder", status: "healthy" }),
      makeMachineStatus({ id: 2, machine_class: "welder", status: "healthy" }), // unbekannt
      makeMachineStatus({ id: 3, machine_class: null, status: "healthy" }), // fehlend
    ];
    const placements = buildLineLayout(machines);

    expect(placements.map((p) => p.machineId)).toEqual([1, 2, 3]);
    // Unbekannte Klasse behält ihren rohen Namen, fehlende wird „Ohne Klasse".
    expect(placements[1]!.stage).toBe("welder");
    expect(placements[2]!.stage).toBe("Ohne Klasse");
    // Beide bekommen den generischen Blockout (kein erfundenes Modell).
    expect(placements[1]!.proportions.shape).toBe("generic");
    expect(placements[2]!.proportions.shape).toBe("generic");
  });

  it("trennt zwei verschiedene Fremdklassen in eigene Stufen (kein Verschmelzen)", () => {
    const machines = [
      makeMachineStatus({ id: 1, machine_class: "welder", status: "healthy" }),
      makeMachineStatus({ id: 2, machine_class: "grinder", status: "healthy" }),
    ];
    const placements = buildLineLayout(machines, { intraGap: 1, stageGap: 3 });

    // Gleiche Ränge, aber distinkte Klassen → alphabetisch getrennt, eigene Stufen.
    expect(placements.map((p) => p.machineClass)).toEqual(["grinder", "welder"]);
    expect(placements[0]!.stageIndex).toBe(0);
    expect(placements[1]!.stageIndex).toBe(1);
    // Stufen-Lücke (stageGap), nicht Intra-Lücke, zwischen den beiden Fremdklassen.
    expect(edgeGap(placements[0]!, placements[1]!)).toBeCloseTo(3, 6);
  });

  it("liefert für eine leere Maschinenliste eine leere Anordnung", () => {
    expect(buildLineLayout([])).toEqual([]);
  });
});
