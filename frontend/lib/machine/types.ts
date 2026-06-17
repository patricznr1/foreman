// ============================================================
//  FOREMAN Frontend — lib/machine/types.ts
//  Zweck: Abgeleitete View-State-Typen der Maschinen-Detail-Sicht (Sektion B).
//         Transport-agnostisch: der TimeSeriesChart liest NUR diese Typen, nie das
//         WS-/HTTP-Format direkt — so ist er gegen live, historisch und Testdaten
//         austauschbar (FE1-Prinzip §21.3, Studie §5.1/§5.5).
//  Architektur-Einordnung: View-State-Vertrag (Schicht 2/3, rein). Wächst mit B.
// ============================================================

/** Ein geplotteter Trend-Punkt (Minuten-Bucket) mit vorab geparster Epoche. */
export interface TrendSample {
  /** ISO-Minuten-Bucket (Schlüssel für den sprungfreien Merge live↔historisch). */
  bucket: string;
  /** `bucket` als Epoche (ms) — einmal geparst, für Geometrie + Sortierung. */
  t: number;
  avg: number;
  min: number;
  max: number;
  last: number | null;
}

/**
 * Eine fertige Sensor-Trendreihe: historischer Pull + Live-Rand zu EINER Reihe
 * verschmolzen, aufsteigend nach Zeit, ohne Bucket-Duplikate. Trägt das statische
 * Normalband mit; `profileBand` ist der reservierte, vorwärtskompatible Slot für
 * das F4-Eigenprofil-Overlay — derzeit immer `null` (kein erfundener Strich).
 */
export interface TrendSeries {
  dataPointId: number;
  dataPointName: string;
  unit: string | null;
  measurementType: string | null;
  normalMin: number | null;
  normalMax: number | null;
  /** Reserviert (F4-Eigenprofil) — bis dahin null; graceful weglassen, nie erfinden. */
  profileBand: null;
  samples: TrendSample[];
  /** Backend hat das Fenster gekappt (mehr Punkte als die Obergrenze). */
  truncated: boolean;
}

/** Richtung einer Normalband-Abweichung (Über-/Unterschreitung). */
export type DriftDirection = "over" | "under";

/**
 * Ein zusammenhängender Abschnitt, in dem der Trend das Normalband verlässt —
 * die Datengrundlage der Differenzfläche. Akzent (diff-over/diff-under + Schraffur),
 * NICHT Alarm-Rot: eine Beobachtung, kein Alarm (Studie §4B/§5.5).
 */
export interface DriftSegment {
  direction: DriftDirection;
  fromT: number;
  toT: number;
  samples: TrendSample[];
}
