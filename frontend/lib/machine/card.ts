// ============================================================
//  FOREMAN Frontend — lib/machine/card.ts
//  Zweck: Reine View-State-Logik der kanonischen lebenden Maschinenkarte
//         (Studie §5.1, Ebene 2): formatiert Datenpunkt-Werte (deutsch), übersetzt
//         den ehrlichen Datenpunkt-Status in eine HALLENSPRACHE-Ansicht (Verdikt vs.
//         Beobachtung, kein internes Vokabular — Hidden-Term-Disziplin) und leitet
//         die ehrliche Frische ab (Stale = „Stand vor X" statt frisch zu tun).
//  Architektur-Einordnung: View-State (Schicht 2), ohne UI/Transport testbar.
// ============================================================
import type { DataPointStatus } from "@/lib/api/contracts";

/** Visueller Ton des Datenpunkt-Status: Verdikt laut, Beobachtung leise. */
export type DataPointTone = "alarm" | "observation" | "ok" | "unknown";

export interface DataPointStatusView {
  tone: DataPointTone;
  /** Kurzes Label in Hallensprache (kein internes Vokabular). */
  label: string;
}

// Deutscher Zahlenformatierer — Komma als Dezimaltrenner, max. 2 Nachkommastellen.
const NUMBER_FORMAT = new Intl.NumberFormat("de-DE", { maximumFractionDigits: 2 });

/** Formatiert den aktuellen Datenpunkt-Wert (deutsch); kein Wert → Gedankenstrich. */
export function formatDataPointValue(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return NUMBER_FORMAT.format(value);
}

// Verdikt-Stufen (drift_alarm/alarm) stammen aus gemeldeten Alarmen; Beobachtungs-
// Stufen (out_of_band/out_of_spec) aus dem Wert gegen ein bestehendes Band — bewusst
// leiser dargestellt (wie der Chart-Akzent: Beobachtung, kein Alarm). „Abweichung
// erkannt" deckt sich mit dem Maschinen-Status (wording.MACHINE_STATUS_LABEL).
const STATUS_VIEW: Record<DataPointStatus, DataPointStatusView> = {
  drift_alarm: { tone: "alarm", label: "Abweichung erkannt" },
  alarm: { tone: "alarm", label: "Offene Warnung" },
  out_of_band: { tone: "observation", label: "Außerhalb Normalbereich" },
  out_of_spec: { tone: "observation", label: "Außerhalb Spezifikation" },
  ok: { tone: "ok", label: "Normal" },
  unknown: { tone: "unknown", label: "Unbekannt" },
};

/** Übersetzt den ehrlichen Datenpunkt-Status in die Karten-Ansicht. */
export function dataPointStatusView(status: DataPointStatus): DataPointStatusView {
  return STATUS_VIEW[status];
}

export interface CardFreshness {
  /** Der Eingangs-Stream tickt fortlaufend → die Werte sind frisch. */
  live: boolean;
  /** Bei Stream-Stopp der ehrliche Stand („Stand vor X"); sonst null. */
  standText: string | null;
}

// Relative Hallensprache für den Stand des letzten Werts (injizierbares „jetzt").
function relativeAgo(atMs: number, nowMs: number): string {
  const seconds = Math.max(0, Math.floor((nowMs - atMs) / 1000));
  if (seconds < 60) {
    return "vor wenigen Sekunden";
  }
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) {
    return `vor ${minutes} Min`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `vor ${hours} Std`;
  }
  const days = Math.floor(hours / 24);
  return days === 1 ? "vor 1 Tag" : `vor ${days} Tagen`;
}

/**
 * Ehrliche Frische der Karte: tickt der Eingangs-Stream, sind die Werte live; ist er
 * gestoppt, wird der letzte bekannte Stand benannt statt Frische vorzutäuschen.
 * `lastReadingAtMs` ist der jüngste Reading-Stempel (oder null = nie ein Wert).
 */
export function cardFreshness(
  streamActive: boolean,
  lastReadingAtMs: number | null,
  nowMs: number,
): CardFreshness {
  if (streamActive) {
    return { live: true, standText: null };
  }
  // Kein bzw. ungültiger Zeitstempel (Date.parse → NaN bei korruptem ISO) → ehrlich
  // „kein Stand" statt „vor NaN".
  if (lastReadingAtMs === null || Number.isNaN(lastReadingAtMs)) {
    return { live: false, standText: null };
  }
  return { live: false, standText: `Stand ${relativeAgo(lastReadingAtMs, nowMs)}` };
}
