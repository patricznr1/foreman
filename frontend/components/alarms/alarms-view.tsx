// ============================================================
//  FOREMAN Frontend — components/alarms/alarms-view.tsx
//  Zweck: Orchestrator der Alarm-Sicht (Sektion C). Rollen-Varianten (Matrix 3.1)
//         als sauberer Komponenten-Split (keine bedingten Hooks): Manager → reines
//         Aggregat; Schichtleiter → Liste + Live-Zähler aus dem overview-Aggregat;
//         Werker/Techniker → scoped Liste (eigene Maschinen, keine overview-Abos).
//         Bindet die reine Assemblierungs-Pipeline an die Echtzeit-Schicht, führt
//         lokalen UI-State (Filter/Gruppierung/Shelving/Aufklappen), Degradation
//         (offline → gecacht + Stempel + Quittieren deaktiviert) und die A11y-
//         Ansagen je Dringlichkeit.
//  Architektur-Einordnung: Sicht-Komponente (Schicht 3, client).
// ============================================================
"use client";

import { useEffect, useMemo, useState } from "react";
import type { AlarmRead, CurrentUser, FleetOverviewOut } from "@/lib/api/contracts";
import { assembleAlarmView, defaultFilter } from "@/lib/alarms/assemble";
import { countByPriorityFromOverview } from "@/lib/alarms/counts";
import { alarmRoleView, machineInScope } from "@/lib/alarms/roles";
import { severityToPriority } from "@/lib/alarms/priority";
import type { AlarmFilter, GroupMode, MachineMeta } from "@/lib/alarms/types";
import { useAlarms } from "@/lib/alarms/use-alarms";
import { useRealtimeStore } from "@/lib/realtime/realtime-context";
import { useTopicView } from "@/lib/state/use-topic";
import { FiveState } from "@/lib/ui/five-states";
import { AlarmAggregate } from "./alarm-aggregate";
import { AlarmFilterBar } from "./alarm-filter-bar";
import { AlarmList } from "./alarm-list";
import { AlarmSituationHeader } from "./alarm-situation-header";

const SHELF_MS = 15 * 60 * 1000;
const OVERVIEW_TOPICS = ["overview"] as const;

export function AlarmsView({ user }: { user: CurrentUser }) {
  const roleView = alarmRoleView(user.role);
  // aggregateOnly bleibt der Pfad für die restriktive Fallback-Sicht (unbekannte
  // Rolle, default-deny) — der manager ist jetzt Vollzugriff (§21.9).
  if (roleView.aggregateOnly) {
    return <AlarmAggregate />;
  }
  if (user.role === "manager") {
    return <ManagerAlarmsView user={user} />;
  }
  if (user.role === "shift_lead") {
    return <LeadAlarmsView user={user} />;
  }
  return <ScopedAlarmsView user={user} />;
}

/** Schichtleiter: Live-Zähler + Maschinen-Stammdaten aus dem overview-Aggregat. */
function LeadAlarmsView({ user }: { user: CurrentUser }) {
  const store = useRealtimeStore();
  const overview = useTopicView(store, "overview").data as FleetOverviewOut | undefined;
  return (
    <AlarmsWorkspace user={user} overview={overview} signalTopics={OVERVIEW_TOPICS} canAcknowledge />
  );
}

/** Manager (Werksleiter-/Vorführ-Vollzugriff, §21.9): das Lagebild als Überblicks-
 *  Kopf ÜBER der vollen Alarmliste — Überblick PLUS Detail statt Aggregat-Sackgasse.
 *  overview-Abo liefert Labels + Lagebild; Scope „all" (roleView) zeigt die ganze
 *  Flotte; Quittieren erlaubt (HITL-Status-Aktion, KEINE Anlagen-Aktorik). */
function ManagerAlarmsView({ user }: { user: CurrentUser }) {
  const store = useRealtimeStore();
  const overview = useTopicView(store, "overview").data as FleetOverviewOut | undefined;
  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <section aria-label="Alarm-Lagebild" className="px-4 pt-4">
        <AlarmSituationHeader overview={overview} />
      </section>
      <AlarmsWorkspace
        user={user}
        overview={overview}
        signalTopics={OVERVIEW_TOPICS}
        canAcknowledge
      />
    </div>
  );
}

/** Werker/Techniker: scoped auf zugewiesene Maschinen, KEINE overview-Abos. */
function ScopedAlarmsView({ user }: { user: CurrentUser }) {
  const topicsKey = user.assigned_machine_ids.join(",");
  const signalTopics = useMemo(
    () => user.assigned_machine_ids.map((id) => `machine:${id}`),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [topicsKey],
  );
  const canAcknowledge = alarmRoleView(user.role).canAcknowledge;
  return (
    <AlarmsWorkspace
      user={user}
      overview={undefined}
      signalTopics={signalTopics}
      canAcknowledge={canAcknowledge}
    />
  );
}

interface WorkspaceProps {
  user: CurrentUser;
  overview: FleetOverviewOut | undefined;
  signalTopics: readonly string[];
  canAcknowledge: boolean;
}

function AlarmsWorkspace({ user, overview, signalTopics, canAcknowledge }: WorkspaceProps) {
  const { state, newIds, stampedAt, refetch, fetchSeq } = useAlarms({ signalTopics });

  const machines = useMemo<ReadonlyMap<number, MachineMeta>>(() => {
    const map = new Map<number, MachineMeta>();
    if (overview) {
      for (const machine of overview.machines) {
        map.set(machine.id, { label: machine.label, lineId: machine.line_id });
      }
    }
    return map;
  }, [overview]);

  const liveCounts = useMemo(() => {
    if (!overview) {
      return undefined;
    }
    return countByPriorityFromOverview(overview, (id, lineId) =>
      machineInScope(user, id, lineId),
    );
  }, [overview, user]);

  const [filter, setFilter] = useState<AlarmFilter>(defaultFilter);
  const [groupMode, setGroupMode] = useState<GroupMode>("priority");
  const [shelf, setShelf] = useState<Map<number, number>>(() => new Map());
  const [expandedBundles, setExpandedBundles] = useState<Set<string>>(() => new Set());
  const [now, setNow] = useState(() => Date.now());

  // Tick nur, solange etwas zurückgestellt ist (Shelf-Ablauf sichtbar machen).
  useEffect(() => {
    if (shelf.size === 0) {
      return;
    }
    const handle = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(handle);
  }, [shelf.size]);

  const onShelve = (alarmId: number) =>
    setShelf((prev) => new Map(prev).set(alarmId, Date.now() + SHELF_MS));

  const onUnshelve = (alarmId: number) =>
    setShelf((prev) => {
      const next = new Map(prev);
      next.delete(alarmId);
      return next;
    });

  const onToggleBundle = (key: string) =>
    setExpandedBundles((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });

  return (
    <div className="flex h-full min-h-0 flex-col">
      <h1 className="sr-only">Alarme & Warnungen</h1>
      <FiveState state={state} label="Alarme">
        {(alarms, freshness) => (
          <AlarmsContent
            alarms={alarms}
            freshness={freshness}
            user={user}
            machines={machines}
            liveCounts={liveCounts}
            newIds={newIds}
            stampedAt={stampedAt}
            now={now}
            fetchSeq={fetchSeq}
            filter={filter}
            onFilterChange={setFilter}
            groupMode={groupMode}
            onGroupModeChange={setGroupMode}
            shelf={shelf}
            onShelve={onShelve}
            onUnshelve={onUnshelve}
            expandedBundles={expandedBundles}
            onToggleBundle={onToggleBundle}
            canAcknowledge={canAcknowledge}
            onAcknowledged={refetch}
          />
        )}
      </FiveState>
    </div>
  );
}

interface ContentProps {
  alarms: AlarmRead[];
  freshness: "live" | "cached";
  user: CurrentUser;
  machines: ReadonlyMap<number, MachineMeta>;
  liveCounts: ReturnType<typeof countByPriorityFromOverview> | undefined;
  newIds: ReadonlySet<number>;
  stampedAt: Date | null;
  now: number;
  fetchSeq: number;
  filter: AlarmFilter;
  onFilterChange: (filter: AlarmFilter) => void;
  groupMode: GroupMode;
  onGroupModeChange: (mode: GroupMode) => void;
  shelf: ReadonlyMap<number, number>;
  onShelve: (alarmId: number) => void;
  onUnshelve: (alarmId: number) => void;
  expandedBundles: ReadonlySet<string>;
  onToggleBundle: (key: string) => void;
  canAcknowledge: boolean;
  onAcknowledged: () => void;
}

function AlarmsContent(props: ContentProps) {
  const { alarms, freshness, user, newIds } = props;
  const online = freshness === "live";

  const view = assembleAlarmView(alarms, {
    machines: props.machines,
    shelf: props.shelf,
    now: props.now,
    newIds,
    filter: props.filter,
    groupMode: props.groupMode,
    expandedBundles: props.expandedBundles,
    // Scope ist ein UX-Filter (keine AuthZ — die /alarms-Route ist server-seitig
    // nicht scope-gefiltert, siehe PR-Hinweis). Solange die Maschine→Linie-
    // Zuordnung (overview) für den Schichtleiter noch fehlt, NICHT vorschnell
    // ausblenden (sonst leerer Flash, bis der WS-Snapshot da ist) — fail-open.
    visibleMachine: (id, lineId) => {
      if (user.role === "shift_lead" && !props.machines.has(id)) {
        return true;
      }
      return machineInScope(user, id, lineId);
    },
    liveCounts: props.liveCounts,
  });

  // A11y-Ansagen je Dringlichkeit (§5.8): kritisch/hoch assertiv, sonst höflich.
  const freshCritical = alarms.filter(
    (alarm) =>
      newIds.has(alarm.id) &&
      (severityToPriority(alarm.severity) === "critical" ||
        severityToPriority(alarm.severity) === "high"),
  ).length;
  const freshOther = newIds.size - freshCritical;
  // Wiederholungs-Nonce (für Screenreader still): zwei gleichlautende Ansagen in
  // Folge (z. B. erneut „2 neue dringende Alarme") müssen die Live-Region trotzdem
  // erneut auslösen — sonst wird die zweite Charge verschluckt (§5.8).
  const nonce = props.fetchSeq % 2 === 1 ? " " : "";
  const assertiveMessage =
    freshCritical > 0 ? `${freshCritical} neue dringende Alarme${nonce}` : undefined;
  const politeMessage = freshOther > 0 ? `${freshOther} neue Alarme${nonce}` : undefined;

  return (
    <>
      <AlarmFilterBar
        counts={view.counts}
        driftCount={view.driftCount}
        freshness={freshness}
        stampedAt={props.stampedAt}
        filter={props.filter}
        onFilterChange={props.onFilterChange}
        groupMode={props.groupMode}
        onGroupModeChange={props.onGroupModeChange}
      />
      {view.total === 0 ? (
        <div className="flex flex-1 items-center justify-center p-8" role="status">
          <span className="inline-flex items-center gap-2 text-body text-fg-muted">
            <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full bg-state-ok" />
            Keine offenen Alarme — Anlage ruhig.
          </span>
        </div>
      ) : (
        <AlarmList
          rows={view.rows}
          canAcknowledge={props.canAcknowledge}
          online={online}
          onAcknowledged={props.onAcknowledged}
          onShelve={props.onShelve}
          onUnshelve={props.onUnshelve}
          expandedBundles={props.expandedBundles}
          onToggleBundle={props.onToggleBundle}
          politeMessage={politeMessage}
          assertiveMessage={assertiveMessage}
        />
      )}
    </>
  );
}
