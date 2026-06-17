// ============================================================
//  FOREMAN Frontend — components/memory/relation-view.tsx
//  Zweck: Die Verknüpfungs-Ansicht (Studie §4H): wie die Treffer zusammenhängen —
//         als kompakte Beziehungsdarstellung, NICHT als wilder Graph (die tiefere
//         Graph-Visualisierung ist [VISION]). Beziehungstypen farbunabhängig durch
//         Label + Anordnung. Reservierte Typen (Maschinenklasse/Wurzelursache) sind
//         ehrlich als Zielbild markiert — nicht erfunden.
//  Architektur-Einordnung: Sektions-Molekül (Schicht 2). Rein präsentational.
// ============================================================
import { RELATION_LABEL } from "@/lib/memory/relations";
import type { MemoryRelation } from "@/lib/memory/types";

export interface RelationViewProps {
  relations: MemoryRelation[];
}

export function RelationView({ relations }: RelationViewProps) {
  return (
    <aside
      aria-label="Wie die Fälle zusammenhängen"
      className="flex flex-col gap-3 rounded-lg border border-line-subtle bg-surface-raised p-4"
    >
      <h3 className="text-body font-medium text-fg-primary">Wie die Fälle zusammenhängen</h3>
      {relations.length === 0 ? (
        <p className="text-caption text-fg-muted">
          Keine gemeinsamen Bezüge zwischen den Treffern erkannt.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {relations.map((relation, index) => (
            <li key={`${relation.type}-${index}`} className="flex flex-col gap-0.5">
              <span className="text-caption font-semibold uppercase tracking-wide text-fg-muted">
                {RELATION_LABEL[relation.type]}
              </span>
              <span className="text-body text-fg-secondary">{relation.reason}</span>
            </li>
          ))}
        </ul>
      )}
      <p className="border-t border-line-subtle pt-2 text-caption text-fg-muted">
        Verknüpfung über Maschinenklasse (Schwestermaschinen) und gemeinsame Ursache folgt.
      </p>
    </aside>
  );
}
