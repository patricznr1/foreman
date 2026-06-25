// ============================================================
//  FOREMAN Frontend — components/shell/global-status-bar.tsx
//  Zweck: Globale Status-/Alarmleiste (§3.3) — der EINZIGE Ort, an dem Live-
//         Dringlichkeit den Nutzer aktiv holen darf. Trägt das aggregierte FCSM-/
//         Alarmbild des Geltungsbereichs (live, mit Stand-Stempel), den Scope-
//         Breadcrumb, die Befehlsleiste und den Theme-Umschalter. Über alle
//         Sektionen identisch (Prinzip 2).
//  Architektur-Einordnung: Persistentes Rahmenelement (Schicht 2, client).
// ============================================================
"use client";

import Link from "next/link";
import { ProvenanceStamp } from "@/components/atoms/provenance-stamp";
import { StatusIndicator } from "@/components/atoms/status-indicator";
import { countByPriorityFromOverview } from "@/lib/alarms/counts";
import type { FleetOverviewOut, MachineStatus } from "@/lib/api/contracts";
import { canAccessSection } from "@/lib/auth/roles";
import { useSession } from "@/lib/auth/use-session";
import { useRealtimeStore } from "@/lib/realtime/realtime-context";
import { useTopicState } from "@/lib/state/use-topic";
import { streamBadgeFreshness } from "@/lib/ui/stream-freshness";
import { MACHINE_STATUS_LABEL, MACHINE_STATUS_TO_FCSM } from "@/lib/ui/wording";
import { CommandPalette } from "./command-palette";
import { type ScopeCrumb, ScopeBreadcrumb } from "./scope-breadcrumb";
import { ThemeToggle } from "./theme-toggle";

const DEFAULT_SCOPE: ScopeCrumb[] = [{ label: "Flotte", href: "/overview" }];

/**
 * Dringlichster Flottenzustand. Reihenfolge nach Studie 4C: offene Alarme sind
 * dringlicher als die (weicheren) Drift-Warnungen. Rückgabe ist der komponierte
 * MachineStatus — Farbe UND Label leiten sich daraus konsistent ab (kein
 * irreführendes FCSM-Wording, Review-Fix).
 */
function worstMachineStatus(overview: FleetOverviewOut): MachineStatus {
  if ((overview.by_status.open_warning ?? 0) > 0) {
    return "open_warning";
  }
  if ((overview.by_status.drift_active ?? 0) > 0) {
    return "drift_active";
  }
  return "healthy";
}

/** Live-Aggregat — nur für Rollen mit Cockpit-Zugriff (sonst kein overview-Abo). */
function FleetLiveBadge() {
  const store = useRealtimeStore();
  const state = useTopicState<FleetOverviewOut>(store, "overview");

  if (state.kind === "live" || state.kind === "cached") {
    const overview = state.data;
    const worst = worstMachineStatus(overview);
    // Eskalations-Verschärfung (Studie §4C): offene kritische Alarme verschärfen
    // ihre Präsenz in die globale Leiste (assertiv, mit Sprung zur Alarm-Sicht).
    const criticalCount = countByPriorityFromOverview(overview).critical;
    // „Live" NUR, wenn die Verbindung steht UND der Eingangs-Stream wirklich tickt —
    // sonst „Verlauf" (Historie) statt eines Live-Etiketts über statischen Daten.
    // DIESELBE Wahrheit wie die Topologie-Kachel „Simulation (intern)".
    const freshness = streamBadgeFreshness(state.kind === "live", overview.stream.active);
    return (
      <div className="flex items-center gap-3" aria-live="polite">
        {criticalCount > 0 ? (
          <span aria-live="assertive">
            <Link
              href="/alarms"
              className="inline-flex items-center gap-1 rounded bg-alarm-critical px-2 py-0.5 text-caption font-semibold text-fg-on-accent"
            >
              {criticalCount} kritisch · ansehen
            </Link>
          </span>
        ) : null}
        <StatusIndicator
          status={MACHINE_STATUS_TO_FCSM[worst]}
          label={MACHINE_STATUS_LABEL[worst]}
          size="s"
        />
        <span className="text-caption tabular-nums text-fg-secondary">
          {overview.open_alarm_total} offene Alarme
        </span>
        <ProvenanceStamp freshness={freshness} stampedAt={overview.stream.last_reading_at} />
      </div>
    );
  }
  if (state.kind === "error") {
    return <span className="text-caption text-note-caveat">Lagebild nicht verfügbar</span>;
  }
  return <span className="text-caption text-fg-muted">Lagebild lädt …</span>;
}

export function GlobalStatusBar({ scope = DEFAULT_SCOPE }: { scope?: ScopeCrumb[] }) {
  const user = useSession();
  const showFleet = canAccessSection(user.role, "A");

  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line-subtle bg-surface-raised px-4 py-2">
      <div className="flex items-center gap-4">
        <span className="text-body-l font-semibold text-fg-primary">FOREMAN</span>
        <ScopeBreadcrumb items={scope} />
      </div>
      <div className="flex items-center gap-4">
        {showFleet ? <FleetLiveBadge /> : null}
        <CommandPalette />
        <ThemeToggle />
      </div>
    </header>
  );
}
