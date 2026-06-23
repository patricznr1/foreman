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

/** Ein Korridorpunkt des Eigenprofil-Bands (Epoche vorab geparst, wie TrendSample). */
export interface ProfileBandPoint {
  /** `bucket` als Epoche (ms) — deckt sich mit dem zugehörigen TrendSample. */
  t: number;
  lower: number;
  mid: number;
  upper: number;
}

/**
 * Das zustandsspezifische F4-Eigenprofil-Band: der gelernte Erwartungskorridor je
 * Bucket (`mid` = Zustands-Median, `lower`/`upper` = `median +/- k*sigma`). `computedAt`
 * ist der Profil-Stand (ms) — keine vorgetäuschte Live-Aktualität.
 */
export interface ProfileBand {
  computedAt: number;
  effectSizeK: number;
  points: ProfileBandPoint[];
}

/**
 * Eine fertige Sensor-Trendreihe: historischer Pull + Live-Rand zu EINER Reihe
 * verschmolzen, aufsteigend nach Zeit, ohne Bucket-Duplikate. Trägt das statische
 * Normalband mit; `profileBand` ist das F4-Eigenprofil-Overlay — null, wenn kein/zu
 * junges Profil vorliegt (graceful weglassen, nie erfinden).
 */
export interface TrendSeries {
  dataPointId: number;
  dataPointName: string;
  unit: string | null;
  measurementType: string | null;
  normalMin: number | null;
  normalMax: number | null;
  /** F4-Eigenprofil-Korridor; null = kein/zu junges Profil (kein erfundener Strich). */
  profileBand: ProfileBand | null;
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
