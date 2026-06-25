// ============================================================
//  FOREMAN Frontend — components/machine/machine-card-grid.tsx
//  Zweck: Das Karten-Grid unter „Linie & Maschinen" — ersetzt die bisherige
//         Maschinenlisten-Darstellung (Reiter) durch lebende Karten (MachineCard,
//         compact), gruppiert nach Synoptik-Stufe (Fördern/Pressen/Handling/
//         Bestücken/Endkontrolle) in kanonischer Linien-Reihenfolge. Leerer Zugriff
//         wird ehrlich benannt.
//  Architektur-Einordnung: Komponente (Schicht 1). Reine Komposition über
//         lib/machine/grouping + MachineCard; jede Karte ist ihr eigener Live-Boundary.
// ============================================================
import type { MachineCardOut } from "@/lib/api/contracts";
import { groupByStage } from "@/lib/machine/grouping";

import { MachineCard } from "./machine-card";

export interface MachineCardGridProps {
  cards: MachineCardOut[];
}

export function MachineCardGrid({ cards }: MachineCardGridProps) {
  if (cards.length === 0) {
    return <p className="text-body text-fg-muted">Keine Maschinen in deinem Zugriff.</p>;
  }
  const groups = groupByStage(cards);
  return (
    <div className="flex flex-col gap-8">
      {groups.map((group) => (
        <section
          key={group.machineClass ?? "__none__"}
          aria-label={group.stage}
          className="flex flex-col gap-3"
        >
          <h2 className="text-caption font-semibold uppercase tracking-wide text-fg-muted">
            {group.stage}
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {group.cards.map((card) => (
              <MachineCard key={card.id} initial={card} density="compact" />
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}
