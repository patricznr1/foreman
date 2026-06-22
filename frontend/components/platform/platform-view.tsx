// ============================================================
//  FOREMAN Frontend — components/platform/platform-view.tsx
//  Zweck: Sektions-Einstieg I (Plattform/Audit, Studie §4I), Rollen-Split OHNE
//         bedingte Hooks: Manager sieht Topologie + Audit-Trail (Tabs, Topologie
//         als Lagebild ZUERST); Schichtleiter sieht NUR die Topologie — sein Zweig
//         mountet den Audit-Hook NIE, also ruft der FE GET /api/v1/audit für ihn
//         nicht auf (gäbe 403). Werker/Techniker erreichen die Sicht nicht (der
//         Server-Guard requireSection("I") ist die Grenze; hier default-deny).
//         HITL: die Sicht liest nur, schaltet nie. Kein WS-Live-Feed → HTTP-Snapshot
//         + bewusster, manueller Refresh.
//  Architektur-Einordnung: Sektions-Einstieg (Schicht 2, client).
// ============================================================
"use client";

import { useRef, useState } from "react";
import type { CurrentUser } from "@/lib/api/contracts";
import { platformRoleView } from "@/lib/platform/roles";
import { emptyAuditFilter, type AuditFilter } from "@/lib/platform/audit-filter";
import { useAudit } from "@/lib/platform/use-audit";
import { useTopology } from "@/lib/platform/use-topology";
import { ProvenanceStamp } from "@/components/atoms/provenance-stamp";
import { FiveState } from "@/lib/ui/five-states";
import { cx } from "@/lib/ui/cx";
import type { TopologyModel } from "@/lib/platform/types";
import { AuditFilters } from "./audit-filters";
import { AuditTable } from "./audit-table";
import { TopologyGraph } from "./topology-graph";
import { TopologyNodeMark } from "./topology-node-mark";

export interface PlatformViewProps {
  user: CurrentUser;
}

export function PlatformView({ user }: PlatformViewProps) {
  const view = platformRoleView(user.role);

  // Default-deny: ohne Topologie-Recht kein Inhalt (der Server-Guard greift zuvor).
  if (!view.canViewTopology) {
    return (
      <p role="status" className="rounded-lg border border-line-subtle bg-surface-raised p-4 text-body text-fg-muted">
        Diese Sicht ist Manager und Schichtleiter vorbehalten.
      </p>
    );
  }

  return (
    <section className="flex flex-col gap-5" aria-label="Plattform & Audit">
      <header className="flex flex-col gap-1">
        <h1 className="text-h1 text-fg-primary">Plattform &amp; Audit</h1>
        <p className="text-body text-fg-secondary">
          Mit welchen Quellen und Schnittstellen ist FOREMAN verbunden — und ist jeder Abruf
          nachvollziehbar? Lagebild zuerst, Nachweis danach.
        </p>
      </header>

      {view.canViewAudit ? (
        <ManagerTabs />
      ) : (
        <TopologyPanel headingId="topology-heading" />
      )}
    </section>
  );
}

/** Manager: zwei Tabs (Topologie zuerst, dann Audit) — beide Panels bleiben gemountet. */
function ManagerTabs() {
  const tabs = [
    { id: "topology", label: "Topologie" },
    { id: "audit", label: "Audit-Trail" },
  ] as const;
  type TabId = (typeof tabs)[number]["id"];
  const [active, setActive] = useState<TabId>("topology");
  const refs = useRef<Array<HTMLButtonElement | null>>([]);

  function onKeyDown(event: React.KeyboardEvent, index: number) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") {
      return;
    }
    event.preventDefault();
    const delta = event.key === "ArrowRight" ? 1 : -1;
    const next = (index + delta + tabs.length) % tabs.length;
    const target = tabs[next];
    if (target) {
      setActive(target.id);
      refs.current[next]?.focus();
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div role="tablist" aria-label="Plattform-Ansichten" className="flex gap-1 border-b border-line-subtle">
        {tabs.map((tab, index) => {
          const selected = active === tab.id;
          return (
            <button
              key={tab.id}
              ref={(node) => {
                refs.current[index] = node;
              }}
              role="tab"
              type="button"
              id={`tab-${tab.id}`}
              aria-selected={selected}
              aria-controls={`panel-${tab.id}`}
              tabIndex={selected ? 0 : -1}
              onClick={() => setActive(tab.id)}
              onKeyDown={(event) => onKeyDown(event, index)}
              className={cx(
                "touch-target -mb-px border-b-2 px-4 text-body",
                selected
                  ? "border-line-strong font-medium text-fg-primary"
                  : "border-transparent text-fg-secondary hover:text-fg-primary",
              )}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      <div role="tabpanel" id="panel-topology" aria-labelledby="tab-topology" hidden={active !== "topology"}>
        <TopologyPanel headingId="topology-panel-heading" />
      </div>
      <div role="tabpanel" id="panel-audit" aria-labelledby="tab-audit" hidden={active !== "audit"}>
        <AuditPanel />
      </div>
    </div>
  );
}

/** Topologie-Lagebild: HTTP-Snapshot + bewusster Refresh, optionale Substrat-Probe. */
function TopologyPanel({ headingId }: { headingId: string }) {
  const [probe, setProbe] = useState(true);
  const { state, refresh, refreshing } = useTopology(probe);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 id={headingId} className="text-h2 text-fg-primary">
          Systemtopologie
        </h2>
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-caption text-fg-secondary">
            <input
              type="checkbox"
              checked={probe}
              onChange={(event) => setProbe(event.target.checked)}
            />
            Substrat live prüfen (schreibt Prüf-Marker)
          </label>
          <button
            type="button"
            onClick={refresh}
            disabled={refreshing}
            className="touch-target rounded-md bg-surface-overlay px-4 text-body font-medium text-fg-primary hover:bg-surface-canvas disabled:opacity-60"
          >
            {refreshing ? "lädt …" : "Aktualisieren"}
          </button>
        </div>
      </div>

      <FiveState state={state} label="Topologie">
        {(model, freshness) => <TopologyContent model={model} freshness={freshness} />}
      </FiveState>
    </div>
  );
}

function NodeGroup({ title, nodes }: { title: string; nodes: TopologyModel["inputs"] }) {
  if (nodes.length === 0) {
    return null;
  }
  return (
    <div className="flex flex-col gap-2">
      <h3 className="text-caption font-semibold uppercase tracking-wide text-fg-muted">{title}</h3>
      <ul className="flex flex-col gap-2">
        {nodes.map((node) => (
          <TopologyNodeMark key={node.id} node={node} />
        ))}
      </ul>
    </div>
  );
}

function TopologyContent({
  model,
  freshness,
}: {
  model: TopologyModel;
  freshness: "live" | "cached";
}) {
  return (
    <div className="flex flex-col gap-4">
      <div className="rounded-lg border border-line-subtle bg-surface-raised p-4">
        <TopologyGraph model={model} />
      </div>
      <ProvenanceStamp freshness={freshness} stampedAt={model.generatedAtIso} />
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <NodeGroup title="Eingänge" nodes={model.inputs} />
        <NodeGroup title="Gedächtnis-Substrat" nodes={model.substrate} />
        <NodeGroup title="Schnittstelle (F7)" nodes={model.mcp} />
        <NodeGroup title="Geplant — nicht verbunden ([VISION])" nodes={model.vision} />
      </div>
    </div>
  );
}

/** Audit-Trail: unveränderlich-lesend, gefiltert, paginiert (nur Manager). */
function AuditPanel() {
  const [filter, setFilter] = useState<AuditFilter>(emptyAuditFilter());
  const { state } = useAudit(filter);
  const rows = state.kind === "live" || state.kind === "cached" ? state.data : [];
  const onLastPage = rows.length < filter.limit;

  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-h2 text-fg-primary">Audit-Trail</h2>
      <p className="text-caption text-fg-muted">
        Nachweis abgerufener Erkenntnisse und Human-in-the-Loop-Entscheidungen. Nur lesend — der Audit
        protokolliert, löst nichts aus. Akteure erscheinen ausschließlich pseudonym.
      </p>
      <AuditFilters initial={filter} onApply={setFilter} />
      <FiveState state={state} label="Audit-Trail">
        {(auditRows, freshness) => (
          <div className="flex flex-col gap-3">
            <ProvenanceStamp freshness={freshness} />
            <AuditTable rows={auditRows} />
          </div>
        )}
      </FiveState>
      <nav className="flex items-center gap-3" aria-label="Audit-Seiten">
        <button
          type="button"
          aria-label="vorherige Seite"
          disabled={filter.offset === 0}
          onClick={() =>
            setFilter((current) => ({
              ...current,
              offset: Math.max(0, current.offset - current.limit),
            }))
          }
          className="touch-target rounded-md px-4 text-body text-fg-secondary hover:bg-surface-overlay disabled:opacity-50"
        >
          Zurück
        </button>
        <span role="status" aria-live="polite" aria-atomic="true" className="text-caption text-fg-muted">
          {rows.length === 0
            ? "keine Einträge"
            : `Einträge ${filter.offset + 1}–${filter.offset + rows.length}`}
        </span>
        <button
          type="button"
          aria-label="nächste Seite"
          disabled={onLastPage}
          onClick={() =>
            setFilter((current) => ({ ...current, offset: current.offset + current.limit }))
          }
          className="touch-target rounded-md px-4 text-body text-fg-secondary hover:bg-surface-overlay disabled:opacity-50"
        >
          Weiter
        </button>
      </nav>
    </div>
  );
}
