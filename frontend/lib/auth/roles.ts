// ============================================================
//  FOREMAN Frontend — lib/auth/roles.ts
//  Zweck: Rollenmatrix 3.1 als durchsetzbare Daten — Sektions-Zugriff (●/◐/○),
//         rollenspezifisches Landing, rollengefilterte Primärnavigation (≤ 7).
//         Das Frontend SPIEGELT die Backend-Autorisierung (default-deny), es
//         ersetzt sie nicht — der Server bleibt die Autorität (§20.4).
//  Architektur-Einordnung: Zugriffs-Spiegel (Schicht 1). Reine Logik, testbar.
//  Quelle: Designstudie §3.1 (Matrix) + §3.3 (Navigation).
// ============================================================
import type { Role } from "../api/contracts";

/** ● voll · ◐ reduziert/lesend · ○ kein Zugriff. */
export type Access = "full" | "reduced" | "none";

export type SectionId = "A" | "B" | "C" | "D" | "E" | "F" | "G" | "H" | "I" | "J";

/** Zugriffsmatrix exakt nach Studie §3.1. Zeile = Sektion, Spalte = Rolle. */
export const ACCESS_MATRIX: Record<SectionId, Record<Role, Access>> = {
  A: { worker: "none", shift_lead: "reduced", technician: "none", manager: "full" },
  B: { worker: "reduced", shift_lead: "full", technician: "full", manager: "reduced" },
  C: { worker: "reduced", shift_lead: "full", technician: "reduced", manager: "reduced" },
  D: { worker: "reduced", shift_lead: "full", technician: "full", manager: "reduced" },
  E: { worker: "reduced", shift_lead: "full", technician: "reduced", manager: "reduced" },
  F: { worker: "reduced", shift_lead: "full", technician: "full", manager: "full" },
  G: { worker: "full", shift_lead: "full", technician: "full", manager: "reduced" },
  H: { worker: "full", shift_lead: "full", technician: "full", manager: "reduced" },
  I: { worker: "none", shift_lead: "reduced", technician: "none", manager: "full" },
  J: { worker: "full", shift_lead: "full", technician: "full", manager: "reduced" },
};

export function accessFor(role: Role, section: SectionId): Access {
  // Defensiv: der Backend-`role` ist ein offener String. Eine unbekannte Rolle
  // darf NIE fälschlich Zugriff erben (default-deny) — Review-Fix.
  return ACCESS_MATRIX[section][role] ?? "none";
}

export function canAccessSection(role: Role, section: SectionId): boolean {
  return accessFor(role, section) !== "none";
}

/** Rollenspezifisches Landing (§3.3): Cockpit für Manager/Schichtleiter, sonst Maschinen. */
export const LANDING_ROUTE: Record<Role, string> = {
  manager: "/overview",
  shift_lead: "/overview",
  worker: "/machines",
  technician: "/machines",
};

/** Landing-Route mit Fallback für unbekannte Rollen (offener Backend-String). */
export function landingRoute(role: Role): string {
  return LANDING_ROUTE[role] ?? "/machines";
}

export interface NavItem {
  id: string;
  /** Deutsches UI-Label (Hallensprache). */
  label: string;
  href: string;
  /** Sichtbar, wenn die Rolle auf MINDESTENS einer dieser Sektionen Zugriff hat. */
  sections: SectionId[];
}

/** Primärnavigation (§3.3) — gruppiert, ≤ 7 Einträge. */
export const PRIMARY_NAV: readonly NavItem[] = [
  { id: "cockpit", label: "Cockpit", href: "/overview", sections: ["A"] },
  { id: "machines", label: "Linie & Maschinen", href: "/machines", sections: ["B"] },
  { id: "alarms", label: "Alarme", href: "/alarms", sections: ["C"] },
  // On-Demand-Reasoner unter einem Dach (gleiches Trigger→Provenance→Vorbehalt-Muster).
  { id: "insights", label: "Erkenntnisse", href: "/insights", sections: ["D", "E", "F", "G"] },
  { id: "memory", label: "Gedächtnis", href: "/memory", sections: ["H"] },
  { id: "capture", label: "Erfassung", href: "/capture", sections: ["J"] },
  { id: "platform", label: "Plattform", href: "/platform", sections: ["I"] },
];

/** Rollengefilterte Navigation — kein Eintrag ohne zugehörige Aktion (§3.1/Prinzip 5). */
export function visibleNav(role: Role): NavItem[] {
  return PRIMARY_NAV.filter((item) =>
    item.sections.some((section) => canAccessSection(role, section)),
  );
}
