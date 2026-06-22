// ============================================================
//  FOREMAN Frontend — lib/platform/roles.ts
//  Zweck: Rollen-Varianten der Sektion I (Studie-Matrix §4I / ACCESS_MATRIX.I):
//         Manager sieht ALLES (Topologie + Audit-Trail); Schichtleiter sieht NUR
//         die Topologie (Verbindungsstatus, kein Audit-Bezug) — und der FE ruft
//         GET /api/v1/audit für ihn GAR NICHT auf (gäbe 403). Werker/Techniker
//         haben keinen Zugang (der Server-Guard requireSection("I") ist die
//         eigentliche Grenze; das hier ist nur die UX-Spiegelung). Default-deny.
//  Architektur-Einordnung: Zugriffs-Spiegel (Schicht 2). Reine Logik.
// ============================================================
import type { Role } from "@/lib/api/contracts";

export interface PlatformRoleView {
  /** Darf das Topologie-Lagebild sehen. */
  canViewTopology: boolean;
  /** Darf den Audit-Trail sehen — UND nur dann ruft der FE GET /api/v1/audit auf. */
  canViewAudit: boolean;
  /**
   * Sieht die Topologie MIT Audit-abgeleiteten Details (MCP-Konsumentenzahl,
   * jüngste Abruf-Aktivität). Nur Manager; das Backend filtert ohnehin
   * (include_audit), das hier hält die UX ehrlich.
   */
  seesTopologyAuditDetail: boolean;
}

const ROLE_VIEW: Record<Role, PlatformRoleView> = {
  // Werker: kein Zugang (Server-Guard blockt; Spiegel = alles aus).
  worker: { canViewTopology: false, canViewAudit: false, seesTopologyAuditDetail: false },
  // Schichtleiter: nur das Topologie-Lagebild, kein Audit (kein Audit-Aufruf).
  shift_lead: { canViewTopology: true, canViewAudit: false, seesTopologyAuditDetail: false },
  // Techniker: kein Zugang.
  technician: { canViewTopology: false, canViewAudit: false, seesTopologyAuditDetail: false },
  // Manager: volle Sicht — Topologie inkl. Audit-Details + Audit-Trail.
  manager: { canViewTopology: true, canViewAudit: true, seesTopologyAuditDetail: true },
};

/** Restriktivster Default für unbekannte Backend-Rollen (default-deny). */
const DENY_VIEW: PlatformRoleView = {
  canViewTopology: false,
  canViewAudit: false,
  seesTopologyAuditDetail: false,
};

export function platformRoleView(role: Role): PlatformRoleView {
  return ROLE_VIEW[role] ?? DENY_VIEW;
}
