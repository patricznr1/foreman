// ============================================================
//  FOREMAN Frontend — lib/memory/verknuepfung.test.ts
//  Zweck: Die Brücke zwischen ausgelieferten Treffern und der Verknüpfungs-Logik.
//  Warum sie einen eigenen Test braucht: Beide Fehler, gegen die hier geprüft wird,
//         sind STILL. Fällt die Kennung auf die Rohkennung zurück, ziehen sich alle
//         Erinnerungen (id = 0) zu einer Gruppe zusammen und React vergibt denselben
//         Key mehrfach — die Ansicht zeigt dann eine erfundene Verdichtung. Fällt das
//         Bauteil beim Übersetzen weg, verschwindet die einzige Beziehung, die über
//         die Maschinengrenze trägt, ohne dass irgendetwas rot wird.
// ============================================================
import { describe, expect, it } from "vitest";
import { deriveRelations } from "./relations";
import type { ArchiveHitView } from "./types";
import { alsGedaechtnisTreffer, zurueck } from "./verknuepfung";

/** Ein Treffer, wie ihn `assembleArchiveResult` ausliefert. */
function treffer(rang: number, teil: Partial<ArchiveHitView> = {}): ArchiveHitView {
  return {
    source: "memory",
    // Erinnerungen tragen keinen Primärschlüssel — das Backend setzt fest 0.
    id: 0,
    machineId: 3,
    timestamp: "2026-06-10T08:00:00+00:00",
    excerpt: "Auszug",
    detail: {},
    rank: rang,
    foundBy: ["memory"],
    ...teil,
  };
}

describe("alsGedaechtnisTreffer", () => {
  it("gibt jedem Treffer eine eigene Kennung, auch wenn alle id = 0 tragen", () => {
    // DER TRAGENDE FALL. Über die Rohkennung wären das drei Treffer mit dem
    // Schlüssel 0 — die Verdichtung machte daraus eine Gruppe, die es nicht gibt.
    const übersetzt = alsGedaechtnisTreffer([treffer(0), treffer(1), treffer(2)]);
    expect(übersetzt.map((t) => t.id)).toEqual([0, 1, 2]);
    expect(new Set(übersetzt.map((t) => t.id)).size).toBe(3);
  });

  it("trägt das Bauteil mit", () => {
    const [t] = alsGedaechtnisTreffer([
      treffer(0, { detail: { bauteilart: "valve", bauteil: "Pneumatikventil Achse 2" } }),
    ]);
    expect(t?.componentType).toBe("valve");
    expect(t?.componentLabel).toBe("Pneumatikventil Achse 2");
  });

  it("macht aus einem fehlenden oder leeren Feld null, nicht einen leeren Text", () => {
    // AUFBAU-KONTROLLE: Ein leerer Text gruppierte sonst alle bauteillosen Treffer
    // unter dem Schlüssel "" zu einer gemeinsamen Bauteil-Beziehung zusammen.
    const [ohne] = alsGedaechtnisTreffer([treffer(0)]);
    const [leer] = alsGedaechtnisTreffer([treffer(0, { detail: { bauteilart: "  " } })]);
    expect(ohne?.componentType).toBeNull();
    expect(leer?.componentType).toBeNull();
  });

  it("leitet die Nähe-Stufe aus dem Rang ab, nicht aus einem erfundenen Wert", () => {
    const übersetzt = alsGedaechtnisTreffer([treffer(0), treffer(1), treffer(2)]);
    expect(übersetzt[0]?.strength).toBe("stark");
    expect(übersetzt.at(-1)?.strength).toBe("entfernt");
  });
});

describe("zurueck", () => {
  it("findet über den Rang den vollen Treffer wieder", () => {
    const hits = [treffer(0, { excerpt: "A" }), treffer(1, { excerpt: "B" })];
    const übersetzt = alsGedaechtnisTreffer(hits);
    expect(zurueck([übersetzt[1]!], hits).map((h) => h.excerpt)).toEqual(["B"]);
  });

  it("lässt einen Rang ausserhalb der Liste weg statt undefined durchzureichen", () => {
    const hits = [treffer(0)];
    const fremd = alsGedaechtnisTreffer([treffer(0), treffer(1)]);
    expect(zurueck(fremd, hits)).toHaveLength(1);
  });
});

describe("Beziehung über das Bauteil", () => {
  it("verbindet zwei VERSCHIEDENE Maschinen über ein geteiltes Bauteil", () => {
    // Der Fall, für den das Gedächtnis da ist: Ein Roboter und ein Förderer teilen
    // eine Ventilbauart. Über die Maschine allein ist dieser Zusammenhang nicht zu
    // finden — keine der drei anderen Beziehungen sieht ihn.
    const hits = [
      treffer(0, { machineId: 10, detail: { bauteilart: "valve", bauteil: "Pneumatikventil" } }),
      treffer(1, { machineId: 4, detail: { bauteilart: "valve", bauteil: "Pneumatikventil" } }),
    ];
    const relations = deriveRelations(alsGedaechtnisTreffer(hits));
    const bauteil = relations.find((r) => r.type === "same_component");
    expect(bauteil).toBeDefined();
    expect(bauteil?.reason).toContain("Pneumatikventil");
    expect(bauteil?.reason).toContain("2 Maschinen");
  });

  it("schweigt, wenn alle Treffer an DERSELBEN Maschine hängen", () => {
    // DIE TRAGENDE BEDINGUNG. Ohne sie stünde neben "Gleiche Maschine" immer auch
    // "Gleiches Bauteil" und sagte dasselbe zweimal — die Verknüpfungs-Ansicht sähe
    // reicher aus, als sie ist. Der Erkenntniswert liegt im Sprung über die
    // Maschinengrenze, nicht im Bauteil an sich.
    const hits = [
      treffer(0, { machineId: 10, detail: { bauteilart: "valve" } }),
      treffer(1, { machineId: 10, detail: { bauteilart: "valve" } }),
    ];
    const relations = deriveRelations(alsGedaechtnisTreffer(hits));
    expect(relations.some((r) => r.type === "same_component")).toBe(false);
    // Gegenprobe zum Aufbau: Die Maschinen-Beziehung greift hier sehr wohl — der
    // Fall ist also nicht einfach leer.
    expect(relations.some((r) => r.type === "same_machine")).toBe(true);
  });

  it("verbindet nicht über verschiedene Bauteilarten", () => {
    const hits = [
      treffer(0, { machineId: 10, detail: { bauteilart: "valve" } }),
      treffer(1, { machineId: 4, detail: { bauteilart: "bearing" } }),
    ];
    const relations = deriveRelations(alsGedaechtnisTreffer(hits));
    expect(relations.some((r) => r.type === "same_component")).toBe(false);
  });
});
