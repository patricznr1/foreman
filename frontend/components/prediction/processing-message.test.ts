// ============================================================
//  FOREMAN Frontend — components/prediction/processing-message.test.ts
//  Zweck: Der Wartetext sagt ab dem zweiten Versuch, WARUM es länger dauert.
//  Warum das eine Zusicherung ist und keine Formulierungsfrage: Eine Empfehlung
//         wird verworfen, wenn sie eine unbelegte Zahl trägt. Der nächste Versuch
//         kostet nochmal eine halbe Minute. Wer davor eine Wartemeldung sieht,
//         die beim dritten Versuch genauso aussieht wie beim ersten, hält das
//         System für hängend — und bricht ab, kurz bevor es liefert.
// ============================================================
import { describe, expect, it } from "vitest";

import { MAX_VERSUCHE } from "@/lib/prediction/use-prediction";
import { processingMessage } from "./prediction-panel";

describe("Wartetext der Ausfalleinschätzung", () => {
  it("erster Versuch: der gewöhnliche Text, ohne Zahlen", () => {
    const text = processingMessage(1);
    expect(text).not.toContain("Versuch");
    expect(text).toContain("vergangene Verläufe");
  });

  it("ab dem zweiten: nennt den laufenden Versuch UND den Grund", () => {
    const text = processingMessage(2);
    expect(text).toContain(`Versuch 2 von ${MAX_VERSUCHE}`);
    // Der Grund gehört dazu. Ein blosses "Versuch 2 von 3" liest sich wie ein
    // Defekt; "die vorige Fassung war nicht belegbar" sagt, dass gearbeitet wird.
    expect(text).toContain("belegbar");
  });

  it("AUFBAU-KONTROLLE: 0 und negative Werte kippen nicht in den Versuchstext", () => {
    // `versuch` kommt aus dem Hook und ist dort nie < 1. Fiele die Untergrenze
    // weg, stünde "Versuch 0 von 3" in der Anzeige — eine Zahl, die es nicht gibt.
    expect(processingMessage(0)).not.toContain("Versuch");
    expect(processingMessage(-1)).not.toContain("Versuch");
  });
});
