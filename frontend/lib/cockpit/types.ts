// ============================================================
//  FOREMAN Frontend — lib/cockpit/types.ts
//  Zweck: Abgeleitete View-State-Typen des Flotten-Cockpits (Sektion A). Rein,
//         transport-agnostisch: die DriftHeatmap und die KPI-Reihe lesen NUR diese
//         Typen, nie das WS-/HTTP-Format direkt — so sind sie gegen live, gecacht
//         und Testdaten austauschbar (FE1-Prinzip §21.3, Studie §5.1/§5.5).
//  Architektur-Einordnung: View-State-Vertrag (Schicht 2/3, rein). Wächst mit A.
// ============================================================
import type { MachineStatus } from "@/lib/api/contracts";
import type { Fcsm } from "@/lib/ui/wording";

/**
 * Geltungsbereich des Cockpits (Föderations-Achse, §3.3/§4A). Klasse und Linie
 * sind reale Backend-Felder (machine_class/line_id) → client-seitig filterbar.
 * Die Mehr-WERK-Ebene ist markiertes Zielbild (FOREMAN ist Single-Tenant: eine
 * Instanz = ein Werk), daher hier KEIN Werk-Feld — der Zielbild-Marker lebt im View.
 */
export interface CockpitScope {
  machineClass: string | null;
  lineId: number | null;
}

/**
 * Art der Zell-Auffälligkeit — der zweite, farbunabhängige Kanal (Schraffur-Richtung,
 * §5.2/§5.8). Beantwortet die Leitfrage „wo brennt es (warning) — und wo bahnt sich
 * etwas an (drift)?". `healthy` trägt keine Schraffur.
 */
export type CellKind = "healthy" | "drift" | "warning";

/** Diskrete Abweichungs-Intensität: 0 = ruhig (Normalbetrieb), 1..5 = heatmap-1..5. */
export type DeviationLevel = 0 | 1 | 2 | 3 | 4 | 5;

/** Eine Heatmap-Zelle = eine Maschine. Rein abgeleitet, transport-agnostisch. */
export interface HeatmapCell {
  machineId: number;
  label: string;
  machineClass: string | null;
  lineId: number | null;
  status: MachineStatus;
  /** Komponierter Status → FCSM-Indikator (mehrkanaliges Symbol je Zelle). */
  fcsm: Fcsm;
  /** Abweichungs-Intensität (0..5) → entsättigte sequenzielle Palette (heatmap-1..5). */
  level: DeviationLevel;
  /** Schraffur-/Richtungskanal: brennt (warning) vs. bahnt sich an (drift). */
  kind: CellKind;
  openAlarmCount: number;
  /** Offene kritische + Notfall-Alarme (für Prioritätsspalte/KPI). */
  criticalCount: number;
}

/**
 * Eine Heatmap-Zeile = eine Maschinenklasse. Die Kerninnovation (§4A): gleiche Typen
 * nebeneinander, damit systematische Drift über die Klasse sichtbar wird, die pro
 * Maschine im Rauschen verschwindet.
 */
export interface HeatmapRow {
  /** Klassen-Schlüssel (Backend-`machine_class`) oder null (ohne Klasse). */
  machineClass: string | null;
  /** Anzeige-Label in Hallensprache (null → „Ohne Klasse"). */
  label: string;
  cells: HeatmapCell[];
  /** Zahl der abweichenden Maschinen (level > 0) in der Zeile. */
  deviatingCount: number;
  /** Systematische Drift: Mehrheit der Klasse driftet → Zeile wird hervorgehoben. */
  systematic: boolean;
}

/** Die fertige Heatmap-Matrix (Zeilen = Klassen, Spalten = Maschinen), nach Scope. */
export interface HeatmapMatrix {
  rows: HeatmapRow[];
  /** Gesamtzahl Maschinen nach Scope-Filter (für Leer-/Degradationszustände). */
  machineCount: number;
}
