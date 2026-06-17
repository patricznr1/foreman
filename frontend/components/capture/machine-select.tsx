// ============================================================
//  FOREMAN Frontend — components/capture/machine-select.tsx
//  Zweck: Zuordnungs-Chips für die Maschine (Studie §4J: Chips statt Dropdown-
//         Suche, ein Tap zum Ändern). Trägt die fünf Pflichtzustände an DIESER
//         Auswahl: lädt / bereit / leer (keine zugewiesene Maschine) / Fehler. Bei
//         leer ODER Fehler bleibt die Erfassung möglich — machine_id ist optional
//         (eine allgemeine Notiz ohne Maschinenbezug ist erlaubt). Auswahl ist
//         NEUTRAL gefärbt (keine Statussemantik). Scope ist UX-Führung, keine
//         AuthZ-Grenze (der Server nimmt jede machine_id, §20).
//  Architektur-Einordnung: Sicht-Komponente (Schicht 3, client).
// ============================================================
"use client";

import { machineLabel } from "@/lib/capture/scope";
import type { MachinesState } from "@/lib/capture/use-machines";
import { cx } from "@/lib/ui/cx";

export interface MachineSelectProps {
  state: MachinesState;
  value: number | null;
  onChange: (machineId: number | null) => void;
}

function Chip({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={cx(
        "touch-target inline-flex items-center rounded-lg px-4 text-body",
        active
          ? "border border-line-strong bg-surface-overlay font-semibold text-fg-primary"
          : "border border-line-subtle bg-surface-raised text-fg-secondary",
      )}
    >
      {label}
    </button>
  );
}

export function MachineSelect({ state, value, onChange }: MachineSelectProps) {
  if (state.kind === "loading") {
    return (
      <p role="status" className="text-caption text-fg-muted">
        Maschinen werden geladen …
      </p>
    );
  }

  if (state.kind === "error") {
    return (
      <p className="text-caption text-fg-muted">
        Maschinenliste gerade nicht abrufbar — du kannst trotzdem erfassen (ohne Maschinenbezug).
      </p>
    );
  }

  if (state.kind === "empty") {
    return (
      <p className="text-caption text-fg-muted">
        Keine zugewiesene Maschine — Notiz wird ohne Maschinenbezug erfasst.
      </p>
    );
  }

  return (
    <div
      role="group"
      aria-label="Maschine zuordnen"
      className="flex max-h-44 flex-wrap gap-2 overflow-y-auto"
    >
      <Chip active={value === null} label="Allgemein" onClick={() => onChange(null)} />
      {state.machines.map((machine) => (
        <Chip
          key={machine.id}
          active={value === machine.id}
          label={machineLabel(machine)}
          onClick={() => onChange(machine.id)}
        />
      ))}
    </div>
  );
}
