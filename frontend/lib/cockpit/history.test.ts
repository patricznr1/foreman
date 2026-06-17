// ============================================================
//  FOREMAN Frontend — lib/cockpit/history.test.ts
//  Zweck: Sichert den reinen Ring-Puffer der KPI-Sparklines + die Trendrichtung.
// ============================================================
import { describe, expect, it } from "vitest";

import { pushSample, trendOf } from "./history";

describe("pushSample", () => {
  it("hängt an und liefert eine neue Liste (immutable)", () => {
    const before = [1, 2];
    const after = pushSample(before, 3);
    expect(after).toEqual([1, 2, 3]);
    expect(before).toEqual([1, 2]); // unverändert
  });

  it("kappt auf die Obergrenze (älteste fallen weg)", () => {
    const result = pushSample([1, 2, 3], 4, 3);
    expect(result).toEqual([2, 3, 4]);
  });
});

describe("trendOf", () => {
  it("zu kurze Spur → gleichbleibend", () => {
    expect(trendOf([])).toBe("flat");
    expect(trendOf([5])).toBe("flat");
  });

  it("erkennt steigend/fallend/gleichbleibend aus erstem vs. letztem Wert", () => {
    expect(trendOf([1, 5])).toBe("up");
    expect(trendOf([5, 1])).toBe("down");
    expect(trendOf([3, 9, 3])).toBe("flat");
  });
});
