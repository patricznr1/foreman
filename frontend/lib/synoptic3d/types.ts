// ============================================================
//  FOREMAN Frontend — lib/synoptic3d/types.ts
//  Zweck: Die THREE-freien Datentypen der Live-3D-Linie (Anlagen-Synoptik 3D).
//         Trennt die datengetriebene Mechanik (Anordnung, Status, Swap-Naht) sauber
//         vom Renderer — diese Typen kennen weder WebGL noch DOM und sind die
//         Grundlage der reinen, ohne UI testbaren View-State-Schicht.
//  Architektur-Einordnung: View-State (Schicht 2), ohne UI/Transport testbar.
// ============================================================
import type { MachineStatus } from "@/lib/api/contracts";
import type { PlaceholderProportions } from "./placeholder-proportions";

/** Punkt im Szenenraum (Meter). x = Materialflussrichtung, y = Höhe (Boden = 0), z = quer. */
export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

/**
 * Eine angeordnete Maschine der Linie. Trägt alles, was Renderer UND Klick-Vertrag
 * brauchen: die DB-id (Klick-Ziel → kanonische Maschinenkarte), die Stufe der
 * Linien-Sequenz, den Live-Status (für die Status-Farbe) und die Boden-Zentrum-
 * Position. Render-agnostisch — der Renderer liest hieraus, schreibt nicht zurück.
 */
export interface MachinePlacement {
  /** DB-Primärschlüssel aus /overview — das Klick-Ziel (machineHref → /machines/{id}). */
  machineId: number;
  /** Hallensprache-Label der Maschine (z. B. „Fügepresse 2"). */
  label: string;
  /** Rohe Maschinenklasse aus /overview (feeder/servo_press/…); null = ohne Klasse. */
  machineClass: string | null;
  /** Hallensprache-Stufe der Linien-Sequenz (Fördern/Pressen/…). */
  stage: string;
  /** Komponierter Live-Status (Quelle der Status-Farbe). */
  status: MachineStatus;
  /** Boden-Zentrum-Pivot im Szenenraum (x = Flussrichtung, y = 0, z = 0). */
  position: Vec3;
  /** Proportionaler Blockout der Klasse (grobe Silhouette). */
  proportions: PlaceholderProportions;
  /** 0-basierter Ordinalwert der Stufe unter den tatsächlich vorhandenen Stufen. */
  stageIndex: number;
  /** 0-basierte Position innerhalb der Stufe (Schwester-Reihenfolge). */
  indexInStage: number;
}
