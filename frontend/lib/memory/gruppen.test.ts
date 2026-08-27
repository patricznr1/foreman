// ============================================================
//  FOREMAN Frontend — lib/memory/gruppen.test.ts
//  Zweck: Die Aufteilung des fusionierten Ergebnisses in Blöcke je Quelle.
//  Warum das Fälle wert ist: Die Blöcke stehen unter derselben Liste, aus der
//         sie gebildet werden. Jede Abweichung — ein Treffer doppelt, einer
//         fehlt, eine andere Reihenfolge — wäre für den Werker eine zweite,
//         widersprechende Antwort auf dieselbe Frage.
// ============================================================
import { describe, expect, it } from "vitest";
import { anzahlBestaetigt, gruppiereNachQuelle } from "./gruppen";
import type { ArchiveHitView, SourceType } from "./types";

function treffer(
  source: SourceType,
  id: number,
  rank: number,
  foundBy: SourceType[] = [source],
): ArchiveHitView {
  return {
    source,
    id,
    machineId: 1,
    timestamp: "2026-08-20T09:00:00Z",
    excerpt: "Auszug",
    detail: {},
    rank,
    foundBy,
  };
}

describe("gruppiereNachQuelle", () => {
  it("teilt die Treffer nach ihrem Quelltyp auf", () => {
    const gruppen = gruppiereNachQuelle([
      treffer("note", 1, 0),
      treffer("maintenance", 2, 1),
      treffer("note", 3, 2),
    ]);

    expect(gruppen.map((g) => g.source)).toEqual(["note", "maintenance"]);
    expect(gruppen[0]?.hits.map((h) => h.id)).toEqual([1, 3]);
    expect(gruppen[1]?.hits.map((h) => h.id)).toEqual([2]);
  });

  it("verliert und erfindet keinen Treffer", () => {
    // Die tragende Zusicherung: Die Bloecke zeigen GENAU die Liste darueber.
    // Ohne sie koennte eine spaetere Filterregel still Treffer verschlucken,
    // und die Aufteilung widerspraeche der Rangliste, aus der sie stammt.
    const liste = [
      treffer("note", 1, 0),
      treffer("memory", 0, 1),
      treffer("alarm", 5, 2),
      treffer("maintenance", 7, 3),
      treffer("note", 9, 4),
    ];

    const verteilt = gruppiereNachQuelle(liste).flatMap((g) => g.hits);

    expect(verteilt).toHaveLength(liste.length);
    expect(new Set(verteilt)).toEqual(new Set(liste));
  });

  it("behaelt innerhalb eines Blocks die Reihenfolge des Rangs", () => {
    // Die Fusion hat die Reihenfolge bestimmt. Eine zweite Sortierung waere
    // eine zweite Aussage darueber, was relevanter ist.
    const gruppen = gruppiereNachQuelle([
      treffer("note", 30, 0),
      treffer("note", 10, 1),
      treffer("note", 20, 2),
    ]);

    expect(gruppen[0]?.hits.map((h) => h.rank)).toEqual([0, 1, 2]);
    expect(gruppen[0]?.hits.map((h) => h.id)).toEqual([30, 10, 20]);
  });

  it("laesst leere Quellen weg", () => {
    // Ein Block „Alarm — 0 Treffer" bei jeder Suche ist kein Hinweis, sondern
    // Rauschen. Welche Quellen befragt wurden, sagt der Herkunfts-Stempel.
    const gruppen = gruppiereNachQuelle([treffer("note", 1, 0)]);

    expect(gruppen.map((g) => g.source)).toEqual(["note"]);
  });

  it("haelt die Reihenfolge der Bloecke fest, egal wie die Treffer kommen", () => {
    // AUFBAU-KONTROLLE: Ohne feste Reihenfolge spraengen die Bloecke zwischen
    // zwei Suchen, je nachdem welche Quelle zufaellig zuerst traf.
    const einmal = gruppiereNachQuelle([
      treffer("memory", 0, 0),
      treffer("alarm", 5, 1),
      treffer("note", 1, 2),
    ]);
    const andersherum = gruppiereNachQuelle([
      treffer("note", 1, 0),
      treffer("alarm", 5, 1),
      treffer("memory", 0, 2),
    ]);

    expect(einmal.map((g) => g.source)).toEqual(["note", "alarm", "memory"]);
    expect(andersherum.map((g) => g.source)).toEqual(["note", "alarm", "memory"]);
  });

  it("ordnet einen bestaetigten Treffer seiner EIGENEN Quelle zu", () => {
    // Ein Treffer, den Notiz und Gedaechtnis gefunden haben, IST eine Notiz.
    // Ihn in beide Bloecke zu legen hiesse, denselben Vorgang zweimal zu
    // zeigen — genau das hat die Zusammenfuehrung gerade abgeschafft.
    const gruppen = gruppiereNachQuelle([treffer("note", 7, 0, ["note", "memory"])]);

    expect(gruppen).toHaveLength(1);
    expect(gruppen[0]?.source).toBe("note");
  });

  it("ergibt fuer eine leere Liste keine Bloecke", () => {
    expect(gruppiereNachQuelle([])).toEqual([]);
  });
});

describe("anzahlBestaetigt", () => {
  it("zaehlt die Treffer, die mehr als eine Quelle gefunden hat", () => {
    const anzahl = anzahlBestaetigt([
      treffer("note", 1, 0, ["note", "memory"]),
      treffer("note", 2, 1),
      treffer("maintenance", 3, 2, ["maintenance", "memory"]),
    ]);

    expect(anzahl).toBe(2);
  });

  it("zaehlt einen Einzelfund nicht mit", () => {
    // AUFBAU-KONTROLLE: Eine Zahl, die immer der Trefferzahl entspricht, belegt
    // nichts — sie behauptete Einigkeit, wo jede Quelle fuer sich stand.
    expect(anzahlBestaetigt([treffer("note", 1, 0), treffer("memory", 0, 1)])).toBe(0);
  });
});
