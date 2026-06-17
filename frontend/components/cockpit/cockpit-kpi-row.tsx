// ============================================================
//  FOREMAN Frontend — components/cockpit/cockpit-kpi-row.tsx
//  Zweck: Die KPI-Zeile des Cockpits (§4A) aus den /overview-Aggregaten — je
//         Kennzahl eine KpiTile (nie nackt: Wert + Zustand + Trend + Spark,
//         Prinzip 6). Severity-Farbe ist hier erlaubt (KPI-Zeile, §4A). Die
//         Verlaufs-Sparks sind die Live-Spur dieser Sitzung (history.*). Antippbare
//         Kennzahlen führen ins Drill-down: offene kritische Alarme + Abweichungen
//         → Alarme (C).
//  Architektur-Einordnung: Darstellung (Schicht 3). Liest nur abgeleiteten State.
// ============================================================
"use client";

import Link from "next/link";

import { KpiTile } from "@/components/atoms/kpi-tile";
import { trendOf } from "@/lib/cockpit/history";
import { type CockpitKpis, availabilityFcsm, criticalFcsm, driftFcsm } from "@/lib/cockpit/kpis";
import { alarmsHref } from "@/lib/cockpit/url";

/** Live-Verlaufsspuren der drei Kennzahlen (Spark + Trendrichtung). */
export interface KpiHistory {
  availability: number[];
  criticalOpen: number[];
  driftCount: number[];
}

export interface CockpitKpiRowProps {
  kpis: CockpitKpis;
  history: KpiHistory;
}

export function CockpitKpiRow({ kpis, history }: CockpitKpiRowProps) {
  return (
    <div role="group" aria-label="Flotten-Kennzahlen" className="grid grid-cols-1 gap-4 sm:grid-cols-3">
      <KpiTile
        label="Flottenverfügbarkeit"
        value={kpis.availabilityPct}
        unit="%"
        status={availabilityFcsm(kpis.availabilityPct)}
        trend={trendOf(history.availability)}
        spark={history.availability}
      />
      <Link
        href={alarmsHref()}
        aria-label="Offene kritische Alarme ansehen"
        className="rounded-lg focus-visible:outline-none"
      >
        <KpiTile
          label="Offene kritische Alarme"
          value={kpis.criticalOpen}
          status={criticalFcsm(kpis.criticalOpen)}
          trend={trendOf(history.criticalOpen)}
          spark={history.criticalOpen}
        />
      </Link>
      <Link
        href={alarmsHref()}
        aria-label="Maschinen in Abweichung ansehen"
        className="rounded-lg focus-visible:outline-none"
      >
        <KpiTile
          label="Maschinen in Abweichung"
          value={kpis.driftCount}
          status={driftFcsm(kpis.driftCount)}
          trend={trendOf(history.driftCount)}
          spark={history.driftCount}
        />
      </Link>
    </div>
  );
}
