// ============================================================
//  FOREMAN Frontend — lib/memory/time.ts
//  Zweck: Relative Zeitangabe in Hallensprache ("vor 3 Wochen") für Treffer-Karten
//         (Studie §4H: Zeit je Treffer). Reine Funktion mit injizierbarem jetzt
//         (testbar, kein verstecktes Date.now). Robust gegen ungültige Stempel.
//  Architektur-Einordnung: Darstellungs-Wording (Schicht 1/2). Reine Funktion.
// ============================================================

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;
const WEEK = 7 * DAY;
const MONTH = 30 * DAY;
const YEAR = 365 * DAY;

/** ISO-Stempel auf relative deutsche Angabe; ungültig/leer auf unbekannt. */
export function relativeTime(iso: string, now: Date = new Date()): string {
  const then = new Date(iso);
  const ts = then.getTime();
  if (Number.isNaN(ts)) {
    return "unbekannt";
  }
  const diff = now.getTime() - ts;
  // Zukunft und alles unter einer Minute: "soeben" (keine ungenaue 1-Minute-Angabe).
  if (diff < MINUTE) {
    return "soeben";
  }
  if (diff < HOUR) {
    const m = Math.floor(diff / MINUTE);
    return m === 1 ? "vor 1 Minute" : `vor ${m} Minuten`;
  }
  if (diff < DAY) {
    const h = Math.floor(diff / HOUR);
    return h === 1 ? "vor 1 Stunde" : `vor ${h} Stunden`;
  }
  if (diff < WEEK) {
    const d = Math.floor(diff / DAY);
    return d === 1 ? "gestern" : `vor ${d} Tagen`;
  }
  if (diff < MONTH) {
    const w = Math.floor(diff / WEEK);
    return w === 1 ? "vor 1 Woche" : `vor ${w} Wochen`;
  }
  if (diff < YEAR) {
    const mo = Math.floor(diff / MONTH);
    return mo === 1 ? "vor 1 Monat" : `vor ${mo} Monaten`;
  }
  const y = Math.floor(diff / YEAR);
  return y === 1 ? "vor 1 Jahr" : `vor ${y} Jahren`;
}
