// ============================================================
//  FOREMAN Frontend — components/machine/machine-card.tsx
//  Zweck: Die EINE kanonische lebende Maschinenkarte (Synoptik-Entwurf). Trägt den
//         Steckbrief (Klasse/Standort/Kennung/Hersteller/Komponenten) + Maschinen-
//         Status-Badge (FCSM OK/M/S/C/F) im Kopf und pro Datenpunkt Name · WERT ·
//         Einheit + Status-Indikator im Körper. EINE Komponente für beide Einsätze:
//         `compact` ersetzt die Maschinenlisten-Reiter unter „Linie & Maschinen"
//         (Grid, Sprung in die Detailsicht), `full` ersetzt die Stammdaten-Box der
//         Detailansicht (machine-specs). Live über das WS-Thema machine:{id} (SSR-
//         Erstbild + Push); Stale ehrlich (bei Stream-Stopp „Stand vor X").
//  Architektur-Einordnung: Komponente (Schicht 1). Transport-agnostisch testbar
//         (FakeTransport); Visualisierung kennt den Transport nie (useTopicState).
// ============================================================
"use client";

import Link from "next/link";

import { StatusIndicator } from "@/components/atoms/status-indicator";
import type { DataPointCardOut, DataPointStatus, MachineCardOut } from "@/lib/api/contracts";
import { cardFreshness, dataPointStatusView, formatDataPointValue } from "@/lib/machine/card";
import { useRealtimeStore } from "@/lib/realtime/realtime-context";
import { useTopicState } from "@/lib/state/use-topic";
import { cx } from "@/lib/ui/cx";
import { MACHINE_STATUS_LABEL, MACHINE_STATUS_TO_FCSM } from "@/lib/ui/wording";

export interface MachineCardProps {
  /** SSR-Erstbild der Karte (Grid: /api/v1/cards, Detail: /machines/{id}/card). */
  initial: MachineCardOut;
  /** `compact` fürs Grid (Reiter-Ersatz), `full` für die Detailansicht. */
  density?: "compact" | "full";
  /** Injizierbares „jetzt" für die Stale-Ableitung (Tests). */
  nowMs?: number;
}

// Literale Token-Klassen je Datenpunkt-Status (Tailwind-Purge-sicher, wie
// StatusIndicator.FILL — keine dynamisch zusammengesetzten Klassennamen). Verdikt =
// FCSM-Farbe (laut), Beobachtung = Vorbehalts-Token (leiser, kein Rot), unbekannt =
// neutral (nie grün geraten).
const DOT_CLASS: Record<DataPointStatus, string> = {
  drift_alarm: "bg-state-outofspec",
  alarm: "bg-state-check",
  out_of_band: "bg-note-caveat",
  out_of_spec: "bg-note-caveat",
  ok: "bg-state-ok",
  unknown: "bg-fg-muted",
};

function DataPointRow({ dataPoint }: { dataPoint: DataPointCardOut }) {
  const view = dataPointStatusView(dataPoint.status);
  // Beobachtung/Verdikt tragen ihr Label sichtbar (mehrkanalig); Normal/Unbekannt
  // treten zurück (ISA-101-Ruhe) — aria-Label trägt den Status immer.
  const showLabel = view.tone === "alarm" || view.tone === "observation";
  return (
    <li className="flex items-center justify-between gap-3 py-1.5">
      <span className="text-caption text-fg-secondary">{dataPoint.name}</span>
      <span className="flex items-center gap-2">
        <span className="text-body tabular-nums text-fg-primary">
          {formatDataPointValue(dataPoint.last_value)}
        </span>
        {dataPoint.unit !== null ? (
          <span className="text-caption text-fg-secondary">{dataPoint.unit}</span>
        ) : null}
        <span role="img" aria-label={view.label} className="inline-flex items-center gap-1.5">
          <span
            aria-hidden="true"
            className={cx("h-2.5 w-2.5 shrink-0 rounded-full", DOT_CLASS[dataPoint.status])}
          />
          {showLabel ? <span className="text-caption text-fg-muted">{view.label}</span> : null}
        </span>
      </span>
    </li>
  );
}

function SteifbriefDetails({ card }: { card: MachineCardOut }) {
  const rows: ReadonlyArray<readonly [string, string | null]> = [
    ["Hersteller", card.manufacturer],
    ["Standort", card.location],
    ["Linie", card.line_id !== null ? `Linie ${card.line_id}` : null],
    ["Kennung", card.external_id],
    [
      "Komponenten",
      card.components.length > 0 ? card.components.map((c) => c.label).join(", ") : null,
    ],
  ];
  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2">
      {rows.map(([label, value]) =>
        value !== null ? (
          <div key={label} className="flex justify-between gap-3 border-b border-line-subtle py-1">
            <dt className="text-caption text-fg-muted">{label}</dt>
            <dd className="text-caption text-fg-secondary">{value}</dd>
          </div>
        ) : null,
      )}
    </dl>
  );
}

export function MachineCard({ initial, density = "compact", nowMs }: MachineCardProps) {
  const store = useRealtimeStore();
  const state = useTopicState<MachineCardOut>(store, `machine:${initial.id}`);
  // Erstbild aus dem SSR-Pull; sobald der Live-Snapshot/Push da ist (live/gecacht),
  // führt er — Degradation friert auf dem letzten Stand ein, leert nicht.
  const card = state.kind === "live" || state.kind === "cached" ? state.data : initial;
  const wsLive = state.kind === "live";

  const now = nowMs ?? Date.now();
  const lastReadingAtMs =
    card.stream.last_reading_at !== null ? Date.parse(card.stream.last_reading_at) : null;
  // „Live" nur, wenn der Eingangs-Stream tickt UND die WS-Verbindung steht; sonst
  // der ehrliche Stand des letzten Werts (kein Live-Etikett über statischer Historie).
  const fresh = cardFreshness(card.stream.active && wsLive, lastReadingAtMs, now);

  const identity = [card.machine_class, card.location].filter(Boolean).join(" · ");

  const inner = (
    <div
      className={cx(
        "flex h-full flex-col gap-3 rounded-lg border border-line-subtle bg-surface-raised p-4",
        density === "compact" && "hover:border-line-strong hover:bg-surface-overlay",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex flex-col gap-0.5">
          <span className="text-body font-medium text-fg-primary">{card.label}</span>
          {identity ? <span className="text-caption text-fg-muted">{identity}</span> : null}
        </div>
        <StatusIndicator
          status={MACHINE_STATUS_TO_FCSM[card.status]}
          label={MACHINE_STATUS_LABEL[card.status]}
          size="s"
        />
      </div>

      {density === "full" ? <SteifbriefDetails card={card} /> : null}

      <ul className="flex flex-col divide-y divide-line-subtle">
        {card.data_points.map((dataPoint) => (
          <DataPointRow key={dataPoint.id} dataPoint={dataPoint} />
        ))}
        {card.data_points.length === 0 ? (
          <li className="py-1.5 text-caption text-fg-muted">Keine Datenpunkte hinterlegt.</li>
        ) : null}
      </ul>

      <p className="mt-auto text-caption text-fg-muted">
        {fresh.live ? (
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden="true" className="h-2 w-2 rounded-full bg-state-ok" />
            Live
          </span>
        ) : (
          (fresh.standText ?? "Kein Stand")
        )}
      </p>
    </div>
  );

  if (density === "compact") {
    return (
      <Link
        href={`/machines/${card.id}`}
        aria-label={`Maschine ${card.label}`}
        className="touch-target block rounded-lg"
      >
        {inner}
      </Link>
    );
  }
  return <section aria-label={`Maschinenkarte ${card.label}`}>{inner}</section>;
}
