// ============================================================
//  FOREMAN Frontend — lib/alarms/types.ts
//  Zweck: Domänen-Typen der Alarm-Sicht (Sektion C). Das ABGELEITETE View-Modell
//         über dem realen Backend-Vertrag (AlarmRead). Drei Achsen der
//         Eskalationslogik (Studie §4C): Priorität (statisch), Lebenszyklus
//         (aktiv→quittiert→geklärt, + client-seitiges Zurückstellen) und
//         Aufmerksamkeitspuls (1-Hz, NUR unquittiert-kritisch). Rein, transport-frei.
//  Architektur-Einordnung: View-State-Ebene 2 (abgeleitet, §5.1). Kennt keinen Transport.
// ============================================================
import type { Fcsm } from "@/lib/ui/wording";

/** ISA-18.2-Prioritäts-Staffelung (abgeleitet aus der 5-stufigen Backend-Severity). */
export type Priority = "critical" | "high" | "medium" | "low" | "journal";

/** Aus den Zeitstempeln ableitbarer Lebenszyklus (Backend hat KEIN lifecycle-Feld). */
export type BaseLifecycle = "active" | "acknowledged" | "cleared";

/**
 * Angezeigter Lebenszyklus: Basis + client-seitiges „zurückgestellt" (shelved).
 * Shelving ist im Backend NICHT persistiert — es ist eine sichtbare, zeitlich
 * begrenzte Client-Überlagerung (nie stilles Verschwinden). „außer Dienst"
 * (out_of_service) ist als ISA-18.2-Zustand vorbereitet, aber ohne Backend-Signal
 * noch nicht verdrahtet (markierter Anschlusspunkt).
 */
export type DisplayLifecycle = BaseLifecycle | "shelved";

/** Stammdaten einer Maschine (aus dem overview-Aggregat) — für Label/Linien-Bezug. */
export interface MachineMeta {
  label: string;
  lineId: number | null;
}

/** Eine zeitlich begrenzte Zurückstellung (Shelving) — Client-State, sichtbar. */
export interface ShelfEntry {
  alarmId: number;
  /** Ablaufzeitpunkt (epoch ms). Nach Ablauf erscheint der Alarm wieder. */
  until: number;
}

/** Gruppierungsachse des Listenkopfes (Studie §4C). */
export type GroupMode = "priority" | "area" | "machine";

/** Lebenszyklus-Filter für die Liste. */
export type LifecycleFilter = "open" | "acknowledged" | "cleared" | "all";

/** Aktive Filter der Sicht (lokaler UI-State, in die reine Pipeline gereicht). */
export interface AlarmFilter {
  /** Sichtbare Prioritäten (leer = alle). */
  priorities: ReadonlySet<Priority>;
  /** Nur Drift-Warnungen zeigen. */
  driftOnly: boolean;
  /** Lebenszyklus-Auswahl. */
  lifecycle: LifecycleFilter;
}

/**
 * Das abgeleitete Zeilen-Modell: eine prioritätscodierte, lebenszyklus-bewusste
 * Sicht auf genau einen Alarm. Alles, was die `AlarmRow`-Komponente braucht —
 * sie rechnet selbst nichts mehr aus (rein präsentational).
 */
export interface AlarmViewModel {
  id: number;
  machineId: number;
  machineLabel: string;
  lineId: number | null;
  lineLabel: string | null;
  code: string | null;
  /** Kurztext (Hallensprache-Fallback, falls Backend-`message` leer). */
  message: string;
  severity: string;
  severityLabel: string;
  priority: Priority;
  priorityLabel: string;
  /** Zweiter, gelernter Kanal: NE-107-Zustandsklasse für den StatusIndicator. */
  fcsm: Fcsm;
  baseLifecycle: BaseLifecycle;
  lifecycle: DisplayLifecycle;
  isDrift: boolean;
  raisedAt: string;
  acknowledgedAt: string | null;
  /** Maskierte Form des HMAC-Tokens (#hex6) — nie Klartext (§8). */
  acknowledgedByMasked: string | null;
  /** Fertiges Label „quittiert von #hex6 um HH:MM" (oder null) — rein präsentational. */
  acknowledgedLabel: string | null;
  clearedAt: string | null;
  shelvedUntil: number | null;
  /** 1-Hz-Aufmerksamkeitspuls: NUR aktiv + kritisch + nicht zurückgestellt (ISA-18.2). */
  pulse: boolean;
  /** Frisch eingetroffen (für den einmaligen Einblend-Puls, kein Listen-Sprung). */
  isNew: boolean;
  /** Erwartete Bedienhandlung (Studie §4C) — Hallensprache. */
  expectedAction: string;
}

/**
 * Flood-Bündel: zusammengehörige Alarme einer vermuteten gemeinsamen Quelle
 * (Linie + Code) werden gebündelt dargestellt statt als N Einzelzeilen —
 * heuristisch (Backend hat kein Korrelations-Feld; markierter Anschlusspunkt).
 */
export interface AlarmBundle {
  key: string;
  lineId: number | null;
  sourceLabel: string;
  code: string | null;
  count: number;
  priority: Priority;
  members: AlarmViewModel[];
  /** Repräsentant (jüngster/dringlichster) für die gebündelte Zeile. */
  representative: AlarmViewModel;
  /**
   * Mind. ein Mitglied ist unquittiert-kritisch (pulst). Dann muss auch das
   * geschlossene Bündel den 1-Hz-Puls tragen — sonst verschwindet das
   * Unquittiert-Signal genau im dichtesten Fall (ISA-18.2: Blinken=unquittiert).
   */
  hasActiveCriticalPulse: boolean;
}

/** Ein Listen-Element: Einzelzeile oder Flood-Bündel. */
export type AlarmListItem =
  | { kind: "row"; row: AlarmViewModel }
  | { kind: "bundle"; bundle: AlarmBundle };

/**
 * Flach virtualisierbares Sicht-Element (uniforme Slot-Höhe): Gruppenkopf,
 * Einzelzeile oder Bündel. Die Liste virtualisiert über diese flache Folge —
 * nur Sichtbares im DOM (Studie §5.1).
 */
export type VisualRow =
  | { kind: "header"; id: string; label: string; count: number; priority: Priority | null }
  | { kind: "row"; id: string; row: AlarmViewModel }
  | { kind: "bundle"; id: string; bundle: AlarmBundle };

/** Prioritäts-Zähler für den Listenkopf („2 kritisch · 5 hoch · 11 mittel"). */
export type PriorityCounts = Record<Priority, number>;

/** Ergebnis der reinen Assemblierungs-Pipeline. */
export interface AlarmView {
  rows: VisualRow[];
  counts: PriorityCounts;
  driftCount: number;
  /** Sichtbare Einzelalarme (nach Filter), inkl. gebündelter Mitglieder. */
  total: number;
}
