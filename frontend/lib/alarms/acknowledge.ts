// ============================================================
//  FOREMAN Frontend — lib/alarms/acknowledge.ts
//  Zweck: HITL-Quittierung als ALARM-STATUS-Aktion (Studie §4C, drei Haltungen).
//         HARTE GRENZE: Quittieren/Eskalieren/Zurückstellen schreiben NUR den
//         Quittier-Status am Alarm-Objekt — NIE eine Anlagen-Aktorik. Diese Schicht
//         löst genau einen erlaubten Status-Pfad auf und verweigert jeden anderen.
//         Reale Route (Inventar): POST /api/v1/reasoners/drift/alarms/{id}/acknowledge
//         (Response AlarmRead). Eine generische Quittier-Route existiert im Backend
//         NOCH NICHT → für Nicht-Drift-Alarme ist sie ein markierter Anschlusspunkt.
//  Architektur-Einordnung: Reine Ableitung + Sicherheits-Invariante (Schicht 2).
// ============================================================
import { DRIFT_ALARM_CODE } from "@/lib/api/contracts";
import type { AlarmViewModel, Priority } from "./types";

interface AckTarget {
  id: number;
  code: string | null;
}

/**
 * Auflösung des realen Quittier-Endpunkts (relativ, läuft über den BFF-Proxy).
 * NUR Drift-Warnungen haben eine echte Backend-Route. Für andere Alarme gibt es
 * (noch) keine generische Status-Route → null (vorbereiteter Anschlusspunkt).
 * Gibt es eine Route, ist sie GARANTIERT ein Status-Suffix `…/acknowledge` —
 * niemals ein schaltender Pfad.
 */
export function acknowledgeEndpoint(alarm: AckTarget): string | null {
  if (alarm.code !== DRIFT_ALARM_CODE) {
    return null;
  }
  return `/api/v1/reasoners/drift/alarms/${alarm.id}/acknowledge`;
}

/**
 * SICHERHEITS-INVARIANTE (Negativtest-Anker): ein Pfad ist nur dann eine erlaubte
 * Alarm-Status-Aktion, wenn er auf `/acknowledge` endet und unter einem bekannten
 * Alarm-Status-Namespace liegt. Alles andere (insb. jeder Anlagen-/Aktor-Pfad) ist
 * verboten. Die Aktions-Schicht prüft das, BEVOR sie irgendetwas sendet.
 */
export function isAlarmStatusActionPath(path: string): boolean {
  return /^\/api\/v1\/reasoners\/drift\/alarms\/\d+\/acknowledge$/.test(path);
}

/** Pflicht-Kontext beim Quittieren (zweistufig mit Begründung) — bei kritisch. */
export function requiresAckContext(priority: Priority): boolean {
  return priority === "critical";
}

/** Warum eine Quittierung gerade nicht möglich ist (Hallensprache, mit Grund). */
export type AckDisabledReason = "offline" | "no-route" | "no-permission" | null;

export function ackDisabledReason(options: {
  online: boolean;
  canAcknowledge: boolean;
  endpoint: string | null;
}): AckDisabledReason {
  if (!options.canAcknowledge) {
    return "no-permission";
  }
  if (!options.online) {
    return "offline";
  }
  if (options.endpoint === null) {
    return "no-route";
  }
  return null;
}

export const ACK_DISABLED_TEXT: Record<NonNullable<AckDisabledReason>, string> = {
  offline: "Offline — Quittieren nicht möglich (Stand siehe Stempel)",
  "no-route": "Quittier-Route für diese Alarmklasse noch nicht verfügbar",
  "no-permission": "Quittieren ist dieser Rolle nicht erlaubt",
};

/**
 * Auditierbarer Quittier-Datensatz (Studie §4C: wer/wann/warum). „Wer" entsteht
 * SERVER-seitig (acknowledged_by = HMAC-Token über die Session-user_id) — das
 * Frontend liefert nur den optionalen Grund. Diese Felder tragen schon den
 * Audit-Bezug für die spätere Sektion I (Audit-Trail).
 */
export interface AcknowledgeRecord {
  alarmId: number;
  /** Erfasster Zeitpunkt der Geste (Client) — der autoritative Stempel kommt vom Server. */
  atIso: string;
  /** Pflicht-Begründung bei kritisch, sonst optional. */
  reason: string | null;
}

export function buildAcknowledgeRecord(
  vm: Pick<AlarmViewModel, "id" | "priority">,
  reason: string | null,
  atIso: string,
): AcknowledgeRecord {
  const normalized = reason && reason.trim().length > 0 ? reason.trim() : null;
  // Vertrag (Audit-/Nachvollziehbarkeit): eine kritische Quittierung MUSS eine
  // Begründung tragen. Die UI verhindert das schon (Submit gesperrt) — hier die
  // zweite Linie, damit der Datensatz die Lücke nie öffnen kann.
  if (requiresAckContext(vm.priority) && normalized === null) {
    throw new Error("Kritische Quittierung erfordert eine Begründung");
  }
  return { alarmId: vm.id, atIso, reason: normalized };
}
