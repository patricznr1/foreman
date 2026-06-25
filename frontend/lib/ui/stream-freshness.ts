// ============================================================
//  FOREMAN Frontend — lib/ui/stream-freshness.ts
//  Zweck: Leitet die EHRLICHE Frische des globalen Live-Badges aus ZWEI Wahrheiten
//         ab: dem WS-Transport (steht die Live-Verbindung?) UND dem Eingangs-Stream
//         (tickt der Zwilling-Worker fortlaufend?). „Live" NUR, wenn beides zutrifft
//         — ein WS-Connect über rein statischer Historie ist „Verlauf", kein Live.
//         Tickt der Stream, ist aber die Verbindung weg, bleibt der letzte Stand
//         „Gecacht" (eingefroren). So spiegelt das Badge dieselbe Wahrheit wie die
//         Plattform-Topologie-Kachel „Simulation (intern)".
//  Architektur-Einordnung: reine Logik (Schicht 2), ohne UI/Transport testbar.
// ============================================================
import type { Freshness } from "@/components/atoms/provenance-stamp";

/**
 * Frische des Live-Badges aus WS-Transport-Zustand und Eingangs-Stream-Zustand.
 * `wsLive` = die WS-Verbindung trägt einen frischen Snapshot; `streamActive` = der
 * Eingangs-Worker tickt. Reine Funktion.
 */
export function streamBadgeFreshness(wsLive: boolean, streamActive: boolean): Freshness {
  if (!streamActive) {
    // Kein laufender Eingangs-Stream → nur Historie. Niemals „Live" (kein Etikett
    // ohne Strom), unabhängig vom Verbindungszustand.
    return "history";
  }
  return wsLive ? "live" : "cached";
}
