// ============================================================
//  FOREMAN Frontend — lib/alarms/view-model.ts
//  Zweck: Bau EINES abgeleiteten Zeilen-Modells (AlarmViewModel) aus einem realen
//         AlarmRead + Kontext (Maschinen-Stammdaten, Shelving, „jetzt", Neu-IDs).
//         Hier laufen die drei Eskalations-Achsen zusammen: Priorität (Severity→Tier),
//         Lebenszyklus (Zeitstempel + Shelving) und der 1-Hz-Puls (nur unquittiert-
//         kritisch). Plus die NE-107-Zustandsklasse je Zeile (zweiter Kanal).
//  Architektur-Einordnung: Reine Ableitung (Schicht 2). Ohne UI testbar.
// ============================================================
import type { AlarmRead } from "@/lib/api/contracts";
import type { Fcsm } from "@/lib/ui/wording";
import { severityLabel } from "@/lib/ui/wording";
import { deriveBaseLifecycle, expectedAction, isDriftAlarm } from "./lifecycle";
import { acknowledgedByLabel, maskAcknowledgedBy } from "./mask";
import { PRIORITY_LABEL, severityToPriority } from "./priority";
import type { AlarmViewModel, DisplayLifecycle, MachineMeta, Priority } from "./types";

export interface BuildContext {
  /** machine_id → Stammdaten (aus dem overview-Aggregat). */
  machines: ReadonlyMap<number, MachineMeta>;
  /** alarmId → Ablaufzeitpunkt der Zurückstellung (epoch ms). */
  shelf: ReadonlyMap<number, number>;
  /** „jetzt" als epoch ms (injiziert — deterministisch testbar). */
  now: number;
  /** Frisch eingetroffene Alarm-IDs (für den Einblend-Puls). */
  newIds: ReadonlySet<number>;
}

/**
 * NE-107-Zustandsklasse je Alarm (zweiter, gelernter Kanal neben der Priorität).
 * Drift = „außerhalb Spezifikation" (S, die weichere Klasse). Harte hohe Priorität
 * = „Ausfall" (F). Mittel = S, niedrig/Journal = „Wartung nötig" (M).
 */
export function fcsmForAlarm(priority: Priority, isDrift: boolean): Fcsm {
  if (isDrift) {
    return "outofspec";
  }
  switch (priority) {
    case "critical":
    case "high":
      return "failure";
    case "medium":
      return "outofspec";
    case "low":
    case "journal":
      return "maintenance";
  }
}

function resolveShelf(
  shelf: ReadonlyMap<number, number>,
  alarmId: number,
  now: number,
  baseLifecycle: DisplayLifecycle,
): number | null {
  // Nur aktive Alarme lassen sich zurückstellen; abgelaufene Zurückstellung verfällt.
  if (baseLifecycle !== "active") {
    return null;
  }
  const until = shelf.get(alarmId);
  if (until !== undefined && until > now) {
    return until;
  }
  return null;
}

export function buildAlarmViewModel(alarm: AlarmRead, ctx: BuildContext): AlarmViewModel {
  const meta = ctx.machines.get(alarm.machine_id);
  const machineLabel = meta?.label ?? `Maschine ${alarm.machine_id}`;
  const lineId = meta?.lineId ?? null;
  const lineLabel = lineId !== null ? `Linie ${lineId}` : null;

  const priority = severityToPriority(alarm.severity);
  const isDrift = isDriftAlarm(alarm);
  const baseLifecycle = deriveBaseLifecycle(alarm);
  const shelvedUntil = resolveShelf(ctx.shelf, alarm.id, ctx.now, baseLifecycle);
  const lifecycle: DisplayLifecycle = shelvedUntil !== null ? "shelved" : baseLifecycle;

  const message =
    alarm.message && alarm.message.trim().length > 0
      ? alarm.message
      : isDrift
        ? "Abweichung gegen das Eigenprofil"
        : "Alarm ohne Kurztext";

  return {
    id: alarm.id,
    machineId: alarm.machine_id,
    machineLabel,
    lineId,
    lineLabel,
    code: alarm.code,
    message,
    severity: alarm.severity,
    severityLabel: severityLabel(alarm.severity),
    priority,
    priorityLabel: PRIORITY_LABEL[priority],
    fcsm: fcsmForAlarm(priority, isDrift),
    baseLifecycle,
    lifecycle,
    isDrift,
    raisedAt: alarm.raised_at,
    acknowledgedAt: alarm.acknowledged_at,
    acknowledgedByMasked: maskAcknowledgedBy(alarm.acknowledged_by),
    acknowledgedLabel: acknowledgedByLabel(alarm.acknowledged_by, alarm.acknowledged_at),
    clearedAt: alarm.cleared_at,
    shelvedUntil,
    // 1-Hz-Aufmerksamkeitspuls: NUR unquittiert-kritisch (ISA-18.2: Blinken =
    // unquittiert, nicht Severity). Quittieren/Zurückstellen/Klären stoppt ihn.
    pulse: priority === "critical" && lifecycle === "active",
    isNew: ctx.newIds.has(alarm.id),
    expectedAction: expectedAction(priority, lifecycle, isDrift),
  };
}
