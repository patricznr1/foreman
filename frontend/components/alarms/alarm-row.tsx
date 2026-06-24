// ============================================================
//  FOREMAN Frontend — components/alarms/alarm-row.tsx
//  Zweck: Prioritätscodierte Alarmzeile (Studie §4C/§5.5). Severity DREIKANALIG:
//         Farbe (Kante/Punkt/Chip) + Position (Sortier-Sektion) + Label (Chip-Text)
//         — Prinzip 3/8. Zweiter, gelernter Kanal: FCSM-StatusIndicator. 1-Hz-Puls
//         NUR unquittiert-kritisch. Handschuh-Höhe; rechts das große Quittier-Ziel.
//         Querlinks → B/D/E (+ Drift→A graceful). Neuer Alarm blendet einmalig ein.
//  Architektur-Einordnung: Sicht-Komponente (Schicht 3, client). Rein präsentational
//         über dem View-Modell — rechnet nichts mehr aus.
// ============================================================
"use client";

import Link from "next/link";
import { StatusIndicator } from "@/components/atoms/status-indicator";
import { LIFECYCLE_LABEL } from "@/lib/alarms/lifecycle";
import type { AlarmViewModel } from "@/lib/alarms/types";
import { cx } from "@/lib/ui/cx";
import { AcknowledgeAction } from "./acknowledge-action";
import { PRIORITY_BORDER, PRIORITY_CHIP, PRIORITY_DOT, railWidth } from "./alarm-styles";

export interface AlarmRowProps {
  vm: AlarmViewModel;
  canAcknowledge: boolean;
  online: boolean;
  onAcknowledged: () => void;
  onShelve: (alarmId: number) => void;
  onUnshelve: (alarmId: number) => void;
  /** Mitglied eines aufgeklappten Flood-Bündels (eingerückt darstellen). */
  nested?: boolean;
  /** Volltext statt einzeiligem Kurztext (Maschinensicht B, nicht virtualisiert). */
  fullMessage?: boolean;
}

function formatTime(value: string | number): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return date.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
}

export function AlarmRow({
  vm,
  canAcknowledge,
  online,
  onAcknowledged,
  onShelve,
  onUnshelve,
  nested = false,
  fullMessage = false,
}: AlarmRowProps) {
  // Querlinks (Kontextnavigation §4C/§3.3): Deep-Links auf bestehende Routen.
  // Maschine → Detailseite (Sektion B), die den Alarm im Kontext zeigt (Trend,
  // Komponenten, offene Alarme der Maschine).
  const machineHref = `/machines/${vm.machineId}`;
  // Sektion D ist gebaut: der Alarm IST der Anker der Rekonstruktion (real, §21-D).
  const chainHref = `/insights/chains?anchor=${vm.id}`;
  const predictHref = `/insights?section=E&machine=${vm.machineId}`;
  const driftHref = `/overview?drift=${vm.machineId}`;
  // Erfassung (J) mit dieser Maschine vorausgewählt — eine Beobachtung zum Alarm
  // festhalten (Daten-Eingabe, keine Aktorik); J liest ?machine= real aus.
  const captureHref = `/capture?machine=${vm.machineId}`;

  const ariaLabel = `${vm.priorityLabel}, ${vm.machineLabel}, ${vm.message}, ${LIFECYCLE_LABEL[vm.lifecycle]}`;

  return (
    <article
      aria-label={ariaLabel}
      className={cx(
        "relative flex h-full gap-3 bg-surface-raised pr-2 pl-3",
        fullMessage ? "items-start py-2" : "items-center",
        railWidth(vm.priority),
        PRIORITY_BORDER[vm.priority],
        nested && "ml-6 border-l-2",
        vm.isNew && "state-flip",
        vm.lifecycle === "cleared" && "opacity-60",
      )}
    >
      {/* Klickbare Zeile (Studie §4C "Zeile öffnen"): die ganze Zeile öffnet die
          Maschine (B), wo der Alarm im Kontext + Volltext lebt. Stretched-Link
          (after:inset-0) statt <article>-in-<Link> → keine <a>-in-<a>-Verschachtelung;
          die Rand-Querlinks/Buttons liegen mit z-10 darüber und bleiben bedienbar.
          In B selbst (fullMessage) entfällt der Link — er führte zirkulär zur
          eigenen Maschine. */}
      {!fullMessage ? (
        <Link
          href={machineHref}
          aria-label={`${vm.machineLabel} öffnen`}
          className="absolute inset-0 z-[1] rounded focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus-ring"
        />
      ) : null}

      {/* Kanal 1 (Farbe): Prioritäts-Punkt; Puls nur unquittiert-kritisch. */}
      <span
        aria-hidden="true"
        className={cx("h-3 w-3 shrink-0 rounded-full", PRIORITY_DOT[vm.priority], vm.pulse && "attention-pulse")}
      />

      {/* Zweiter, gelernter Kanal: NE-107-Zustandsklasse. */}
      <StatusIndicator status={vm.fcsm} size="s" showLabel={false} />

      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate text-body font-medium text-fg-primary">{vm.machineLabel}</span>
          {vm.isDrift ? (
            <span className="shrink-0 rounded border border-dashed border-line-strong px-1.5 text-caption text-fg-secondary">
              Abweichung
            </span>
          ) : null}
          {/* Kanal 3 (Label): Prioritäts-Chip; kritisch gefüllt, sonst umrandet. */}
          <span
            className={cx(
              "shrink-0 rounded px-1.5 text-caption font-semibold",
              PRIORITY_CHIP[vm.priority],
            )}
          >
            {vm.priorityLabel}
          </span>
          {/* Zurückgestellt: mehrkanalig (Symbol + Text), sichtbar auf ALLEN Größen. */}
          {vm.lifecycle === "shelved" ? (
            <span className="inline-flex shrink-0 items-center gap-1 rounded border border-line-strong px-1.5 text-caption text-fg-secondary">
              <span aria-hidden="true">⏸</span>
              Zurückgestellt
              {vm.shelvedUntil !== null ? ` bis ${formatTime(vm.shelvedUntil)}` : ""}
            </span>
          ) : null}
        </div>
        <div
          className={cx(
            "text-caption text-fg-secondary",
            fullMessage ? "whitespace-pre-wrap break-words" : "truncate",
          )}
          // In der virtualisierten C-Liste bleibt der Text einzeilig (feste
          // Slot-Höhe) — der Volltext ist als title-Tooltip + in der Maschinensicht
          // (B, fullMessage) zugänglich.
          title={fullMessage ? undefined : vm.message}
        >
          {vm.message}
        </div>
      </div>

      <div className="hidden flex-col items-end text-caption text-fg-muted sm:flex">
        <time dateTime={vm.raisedAt} className="tabular-nums">
          {formatTime(vm.raisedAt)}
        </time>
        <span>{LIFECYCLE_LABEL[vm.lifecycle]}</span>
      </div>

      <span className="hidden max-w-40 truncate text-caption text-fg-muted md:inline">
        {vm.expectedAction}
      </span>

      {/* Querlinks liegen mit z-10 ÜBER dem Stretched-Link → eigenständig bedienbar.
          Der frühere "Maschine"-Link entfällt: die ganze Zeile öffnet sie bereits. */}
      <nav aria-label="Querlinks" className="relative z-10 hidden items-center gap-1 sm:flex">
        <Link
          href={chainHref}
          className="rounded px-2 py-1 text-caption text-fg-secondary underline underline-offset-2 hover:text-fg-primary"
        >
          Kette
        </Link>
        <Link
          href={predictHref}
          className="rounded px-2 py-1 text-caption text-fg-secondary underline underline-offset-2 hover:text-fg-primary"
        >
          Ausfall?
        </Link>
        <Link
          href={captureHref}
          className="rounded px-2 py-1 text-caption text-fg-secondary underline underline-offset-2 hover:text-fg-primary"
        >
          Notiz
        </Link>
        {vm.isDrift ? (
          <Link
            href={driftHref}
            className="rounded px-2 py-1 text-caption text-fg-secondary underline underline-offset-2 hover:text-fg-primary"
          >
            Heatmap
          </Link>
        ) : null}
      </nav>

      {vm.lifecycle === "shelved" ? (
        canAcknowledge ? (
          // Rücknahme der Zurückstellung — auf ALLEN Größen erreichbar (Touch), ≥56px.
          <button
            type="button"
            onClick={() => onUnshelve(vm.id)}
            aria-label={`Zurückstellung für ${vm.machineLabel} aufheben`}
            className="relative z-10 touch-target inline-flex items-center rounded-md border border-line-strong px-3 text-caption text-fg-primary"
          >
            Einblenden
          </button>
        ) : null
      ) : (
        <>
          {canAcknowledge && vm.lifecycle === "active" ? (
            <button
              type="button"
              onClick={() => onShelve(vm.id)}
              aria-label={`Alarm an ${vm.machineLabel} zurückstellen`}
              className="relative z-10 hidden touch-target items-center rounded-md px-2 text-caption text-fg-secondary sm:inline-flex"
              title="Sichtbar zurückstellen (zeitlich begrenzt)"
            >
              Zurückstellen
            </button>
          ) : null}

          <AcknowledgeAction
            vm={vm}
            canAcknowledge={canAcknowledge}
            online={online}
            onAcknowledged={onAcknowledged}
            className="relative z-10"
          />
        </>
      )}
    </article>
  );
}
