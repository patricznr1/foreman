// ============================================================
//  FOREMAN Frontend — lib/memory/source.test.ts
//  Zweck: Quelltyp-Darstellung. Fordert ein, dass JEDE Quelle Label und
//         Kuerzel traegt (eine vergessene Quelle erschiene sonst unbeschriftet)
//         und dass der Listen-Schluessel auch dann eindeutig bleibt, wenn
//         mehrere Treffer dieselbe id tragen — Erinnerungen tragen alle id=0.
// ============================================================
import { describe, expect, it } from "vitest";
import { SOURCE_GLYPH, SOURCE_LABEL, hitKey } from "./source";
import type { ArchiveHitView, SourceType } from "./types";

/** Alle Quelltypen — bewusst hier wiederholt, damit eine neue Quelle auffaellt. */
const ALLE_QUELLEN: SourceType[] = ["note", "maintenance", "alarm", "memory"];

function treffer(teil: Partial<ArchiveHitView>): ArchiveHitView {
  return {
    source: "note",
    id: 1,
    machineId: 7,
    timestamp: "2026-08-20T09:00:00Z",
    excerpt: "Auszug",
    detail: {},
    rank: 0,
    ...teil,
  };
}

describe("SOURCE_LABEL / SOURCE_GLYPH", () => {
  it("jede Quelle traegt ein deutsches Label", () => {
    for (const quelle of ALLE_QUELLEN) {
      expect(SOURCE_LABEL[quelle], `Label fehlt: ${quelle}`).toBeTruthy();
    }
  });

  it("jede Quelle traegt ein Kuerzel als zweiten, farbunabhaengigen Kanal", () => {
    for (const quelle of ALLE_QUELLEN) {
      expect(SOURCE_GLYPH[quelle], `Kuerzel fehlt: ${quelle}`).toBeTruthy();
    }
  });

  it("die Kuerzel sind untereinander verschieden", () => {
    // Aufbau-Kontrolle: Zwei Quellen mit demselben Kuerzel waeren im Formkanal
    // nicht unterscheidbar — der zweite Kanal traegt dann nichts.
    const kuerzel = ALLE_QUELLEN.map((quelle) => SOURCE_GLYPH[quelle]);
    expect(new Set(kuerzel).size).toBe(ALLE_QUELLEN.length);
  });

  it("die Labels sind Hallensprache, kein Verfahrensbegriff", () => {
    // Die Gedaechtnis-Quelle ist der Kandidat fuer einen Verfahrensbegriff —
    // sie darf nicht nach Abruf, Vektor oder Substrat klingen (§8 Hidden-Term).
    const verboten = ["substrat", "vektor", "embedding", "recall", "nexus"];
    for (const quelle of ALLE_QUELLEN) {
      const label = SOURCE_LABEL[quelle].toLowerCase();
      for (const wort of verboten) {
        expect(label, `${quelle} nennt "${wort}"`).not.toContain(wort);
      }
    }
  });
});

describe("hitKey", () => {
  it("trennt zwei Erinnerungen, obwohl beide id=0 tragen", () => {
    // Der eigentliche Anlass: Eine Erinnerung hat keinen Primaerschluessel und
    // traegt deshalb id=0 (Backend, bewusst). Ein Schluessel aus Quelle+id waere
    // fuer ALLE Erinnerungstreffer derselbe.
    const erste = hitKey(treffer({ source: "memory", id: 0, rank: 0 }));
    const zweite = hitKey(treffer({ source: "memory", id: 0, rank: 1 }));
    expect(erste).not.toBe(zweite);
  });

  it("trennt gleiche id aus verschiedenen Quellen", () => {
    const notiz = hitKey(treffer({ source: "note", id: 42, rank: 0 }));
    const alarm = hitKey(treffer({ source: "alarm", id: 42, rank: 1 }));
    expect(notiz).not.toBe(alarm);
  });

  it("ist fuer denselben Treffer stabil", () => {
    const hit = treffer({ source: "maintenance", id: 5, rank: 3 });
    expect(hitKey(hit)).toBe(hitKey(hit));
  });

  it("bleibt ueber eine ganze Trefferliste eindeutig", () => {
    // Aufbau-Kontrolle zum ersten Test: Eine Liste, in der sich Quelle UND id
    // wiederholen, ist der realistische Fall bei eingeschalteter vierter Quelle.
    const liste = [
      treffer({ source: "memory", id: 0, rank: 0 }),
      treffer({ source: "memory", id: 0, rank: 1 }),
      treffer({ source: "memory", id: 0, rank: 2 }),
      treffer({ source: "note", id: 0, rank: 3 }),
    ];
    const schluessel = liste.map(hitKey);
    expect(new Set(schluessel).size).toBe(liste.length);
  });
});
