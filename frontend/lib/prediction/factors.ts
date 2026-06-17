// ============================================================
//  FOREMAN Frontend — lib/prediction/factors.ts
//  Zweck: Block 2 (Einflussfaktoren) in Werker-Sprache (Studie §4E). Übersetzt die
//         technischen Feature-Tags ({datenpunkt}__{stat} bzw. drift__/maint__/
//         alarm__) in Hallensprache und leitet aus dem rohen Gewicht eine relative,
//         farbunabhängige Balkenlänge ab. PARAPHRASE-DISZIPLIN: der Verfahrensname
//         der Faktor-Zerlegung wird NIE sichtbar (kein „shap"/„tree"/„boosting"),
//         der rohe Tag erscheint nie im UI, die rohe Gewichts-Zahl nie.
//  Architektur-Einordnung: View-State (Schicht 2). Reine Funktion.
// ============================================================
import type { TopFactor } from "@/lib/api/contracts";
import type { FactorRow } from "./types";

/** Voll benannte Sonder-Features (kein {name}__{stat}-Muster). */
const SPECIAL_LABELS: Record<string, string> = {
  drift__count: "Auffälligkeiten in der Messreihe",
  drift__max_effect: "Stärke der Messreihen-Auffälligkeit",
  drift__hours_since_last: "Zeit seit der letzten Auffälligkeit",
  maint__hours_since_last: "Zeit seit der letzten Wartung",
  alarm__count: "Alarme im Beobachtungszeitraum",
};

/** Statistik-Suffix → Hallensprache (Verfahrens-/Mathematik-Begriff bleibt verborgen). */
const STAT_LABELS: Record<string, string> = {
  mean: "im Mittel",
  std: "Schwankung",
  min: "Tiefstwert",
  max: "Spitzenwert",
  range: "Spannweite",
  rms: "Dauerbelastung",
  slope: "Verlauf",
  last: "aktueller Wert",
  last_minus_mean: "Abweichung vom Mittel",
  roc: "Änderungstempo",
  n: "Messdichte",
};

/** Technische Datenpunkt-Wortbausteine → deutsche Hallenbegriffe. */
const TOKEN_LABELS: Record<string, string> = {
  temp: "Temperatur",
  temperature: "Temperatur",
  vib: "Vibration",
  vibration: "Vibration",
  bearing: "Lager",
  spindle: "Spindel",
  motor: "Motor",
  load: "Last",
  pressure: "Druck",
  current: "Strom",
  voltage: "Spannung",
  speed: "Drehzahl",
  rpm: "Drehzahl",
  torque: "Drehmoment",
  flow: "Durchfluss",
  level: "Füllstand",
  lubrication: "Schmierung",
  lubric: "Schmierung",
  oil: "Öl",
  coolant: "Kühlmittel",
  humidity: "Feuchte",
  power: "Leistung",
  rms: "Effektivwert",
  acoustic: "Schall",
  noise: "Schall",
};

/** Einen Datenpunkt-Namen (single-underscore) in Hallensprache übersetzen. */
function humanizeDataPoint(name: string): string {
  const parts = name.split("_").filter((p) => p.length > 0);
  const mapped = parts.map((token) => {
    const lower = token.toLowerCase();
    if (TOKEN_LABELS[lower]) {
      return TOKEN_LABELS[lower];
    }
    // Unbekanntes Wort: erstes Zeichen groß, Rest klein (kein roher Tag, kein „__").
    return token.charAt(0).toUpperCase() + token.slice(1).toLowerCase();
  });
  return mapped.join(" ");
}

/**
 * Übersetzt einen Feature-Tag in ein Werker-Label. Reihenfolge: Sonder-Feature
 * (exakt) → {datenpunkt}__{stat} (am LETZTEN „__" trennen, da Namen single-_ tragen)
 * → Fallback (alle „_"/„__" zu Leerzeichen, kein roher Tag).
 */
export function humanizeFeature(feature: string): string {
  const special = SPECIAL_LABELS[feature];
  if (special) {
    return special;
  }
  const cut = feature.lastIndexOf("__");
  if (cut > 0) {
    const name = feature.slice(0, cut);
    const stat = feature.slice(cut + 2);
    const statLabel = STAT_LABELS[stat] ?? "";
    const dpLabel = humanizeDataPoint(name);
    return statLabel ? `${dpLabel} · ${statLabel}` : dpLabel;
  }
  // Fallback: nie der rohe Tag — Unterstriche zu Leerzeichen.
  return humanizeDataPoint(feature.replace(/__/g, "_"));
}

/**
 * Faktoren → geordnete Werker-Zeilen. Gewicht = |rohes Gewicht|, normiert auf den
 * stärksten Treiber (relative Balkenlänge, farbunabhängig). Absteigend nach Gewicht.
 * Faktoren mit Gewicht 0 werden ausgelassen (kein Treiber).
 */
export function toFactorRows(factors: readonly TopFactor[]): FactorRow[] {
  const magnitudes = factors.map((f) => Math.abs(f.shap));
  const maxMag = Math.max(0, ...magnitudes);
  const rows: FactorRow[] = factors
    .map((f, i) => ({
      key: f.feature,
      label: humanizeFeature(f.feature),
      direction: f.direction,
      weight: maxMag > 0 ? magnitudes[i]! / maxMag : 0,
    }))
    .filter((r) => r.weight > 0);
  rows.sort((a, b) => b.weight - a.weight);
  return rows;
}

/** Richtungs-Label (farbunabhängig, mit Wort UND in der UI mit Pfeil/Position). */
export const FACTOR_DIRECTION_LABEL: Record<TopFactor["direction"], string> = {
  increases_risk: "treibt das Risiko hoch",
  decreases_risk: "senkt das Risiko",
};
