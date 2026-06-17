// ============================================================
//  FOREMAN Frontend — components/machine/machine-list.tsx
//  Zweck: Maschinen-Übersicht der Route /machines (Landing für Werker/Techniker) —
//         Einstieg in die Detail-Sicht je Maschine. Reine Navigation. Der scope-
//         korrekte Satz wird server-seitig gefiltert (Sichtbarkeit ≤ Backend).
//  Architektur-Einordnung: Sicht-Baustein (Schicht 3).
// ============================================================
import Link from "next/link";

import type { MachineRead } from "@/lib/api/contracts";

export interface MachineListProps {
  machines: MachineRead[];
}

export function MachineList({ machines }: MachineListProps) {
  return (
    <section aria-label="Maschinen" className="flex flex-col gap-4">
      <h1 className="text-h1 text-fg-primary">Linie &amp; Maschinen</h1>
      {machines.length > 0 ? (
        <ul className="divide-y divide-line-subtle rounded-lg border border-line-subtle bg-surface-raised">
          {machines.map((machine) => (
            <li key={machine.id}>
              <Link
                href={`/machines/${machine.id}`}
                className="touch-target flex items-center justify-between gap-3 px-4 py-3 hover:bg-surface-overlay"
              >
                <span className="text-body text-fg-primary">{machine.label}</span>
                <span className="text-caption text-fg-muted">
                  {[machine.machine_class, machine.location].filter(Boolean).join(" · ")}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-body text-fg-muted">Keine Maschinen in deinem Zugriff.</p>
      )}
    </section>
  );
}
