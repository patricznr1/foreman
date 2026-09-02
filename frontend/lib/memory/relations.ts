// ============================================================
//  FOREMAN Frontend — lib/memory/relations.ts
//  Zweck: Die VERKNÜPFUNG zwischen Treffern (Studie §4H Verknüpfungslogik) —
//         kompakt, kein Graph. Es werden NUR Beziehungen abgeleitet, die aus
//         realen Feldern faktisch folgen: gleiche Maschine, gleiche Schicht,
//         zeitliche Nähe (Treffer dicht beieinander auf der Zeitachse) und seit dem
//         02.09.2026 GLEICHES BAUTEIL. Letztere ist die tragende Verknüpfung des
//         Gedächtnisses: Sie verbindet Maschinen verschiedener Bauart über ein
//         geteiltes Bauteil — ein Zusammenhang, den keine der drei anderen
//         Beziehungen findet. Möglich wurde sie, weil die Spiegelung seit dem
//         28.08.2026 `bauteilart`/`bauteil` mitschickt.
//         Die WURZELURSACHEN-basierte Verknüpfung bleibt reserviert (es gibt kein
//         Auflösungsfeld) — sie wird NICHT erfunden. Jede Begründung ist faktisch,
//         kein erfundener Ähnlichkeitssatz.
//  Architektur-Einordnung: View-State (Schicht 2). Reine Funktion.
// ============================================================
import type { MemoryHit, MemoryRelation, RelationType } from "./types";

/** Treffer gelten als zeitlich nah, wenn ihr Abstand höchstens so groß ist. */
const TEMPORAL_WINDOW_MS = 14 * 24 * 60 * 60 * 1000;

/** Normalisierter Schicht-Schlüssel (getrimmt) oder null, wenn leer. */
function shiftKey(hit: MemoryHit): string | null {
  const trimmed = hit.shift?.trim();
  return trimmed ? trimmed : null;
}

/** Gruppiert Treffer nach einem Schlüssel; null-Schlüssel werden übersprungen. */
function groupBy(
  hits: MemoryHit[],
  keyOf: (hit: MemoryHit) => string | null,
): Map<string, MemoryHit[]> {
  const groups = new Map<string, MemoryHit[]>();
  for (const hit of hits) {
    const key = keyOf(hit);
    if (key === null) {
      continue;
    }
    const group = groups.get(key) ?? [];
    group.push(hit);
    groups.set(key, group);
  }
  return groups;
}

/**
 * Gruppen zeitlicher Nähe: Treffer nach Zeit sortieren und in Läufe schneiden,
 * sobald der Abstand zum Vorgänger das Fenster übersteigt. So entsteht "diese
 * Hinweise fielen dicht beieinander" ohne willkürliche Kalendergrenze.
 */
function temporalGroups(hits: MemoryHit[]): MemoryHit[][] {
  const dated = hits
    .map((hit) => ({ hit, ts: Date.parse(hit.createdAt) }))
    .filter((entry) => !Number.isNaN(entry.ts))
    .sort((a, b) => a.ts - b.ts);

  const groups: MemoryHit[][] = [];
  let run: { hit: MemoryHit; ts: number }[] = [];
  for (const entry of dated) {
    const prev = run[run.length - 1];
    if (prev === undefined || entry.ts - prev.ts <= TEMPORAL_WINDOW_MS) {
      run.push(entry);
    } else {
      groups.push(run.map((e) => e.hit));
      run = [entry];
    }
  }
  if (run.length > 0) {
    groups.push(run.map((e) => e.hit));
  }
  return groups;
}

const ids = (hits: MemoryHit[]): number[] => hits.map((hit) => hit.id);

/**
 * Leitet die faktischen Beziehungen zwischen den Treffern ab. Ein Treffer kann in
 * mehreren Beziehungen stehen (z. B. gleiche Maschine UND zeitliche Nähe) — das
 * ist gewollt: die Verknüpfungs-Ansicht zeigt sie nebeneinander, nicht als Graph.
 */
export function deriveRelations(hits: MemoryHit[]): MemoryRelation[] {
  const relations: MemoryRelation[] = [];

  for (const group of groupBy(hits, (h) => (h.machineId !== null ? `m:${h.machineId}` : null)).values()) {
    const first = group[0];
    if (group.length >= 2 && first !== undefined) {
      relations.push({
        type: "same_machine",
        hitIds: ids(group),
        reason: `${group.length} Hinweise an Maschine ${first.machineId}`,
      });
    }
  }

  for (const group of groupBy(hits, (h) => (shiftKey(h) === null ? null : `s:${shiftKey(h)}`)).values()) {
    const first = group[0];
    const shift = first ? shiftKey(first) : null;
    if (group.length >= 2 && shift !== null) {
      relations.push({
        type: "same_shift",
        hitIds: ids(group),
        reason: `${group.length} Hinweise aus Schicht ${shift}`,
      });
    }
  }

  // GLEICHES BAUTEIL an VERSCHIEDENEN Maschinen. Die zweite Bedingung ist tragend:
  // Liegen alle Treffer an derselben Maschine, sagt diese Beziehung nichts, was
  // `same_machine` nicht schon sagt — sie stuende nur doppelt da und liesse die
  // Verknuepfungs-Ansicht reicher aussehen, als sie ist. Der Erkenntniswert liegt
  // GERADE im Sprung ueber die Maschinengrenze.
  for (const group of groupBy(hits, (h) =>
    h.componentType?.trim() ? `c:${h.componentType.trim()}` : null,
  ).values()) {
    const first = group[0];
    const maschinen = new Set(group.map((h) => h.machineId).filter((id) => id !== null));
    if (group.length >= 2 && first !== undefined && maschinen.size >= 2) {
      const bezeichnung = first.componentLabel?.trim() || first.componentType?.trim();
      relations.push({
        type: "same_component",
        hitIds: ids(group),
        reason: `${group.length} Hinweise am selben Bauteil (${bezeichnung}) an ${maschinen.size} Maschinen`,
      });
    }
  }

  for (const group of temporalGroups(hits)) {
    if (group.length >= 2) {
      relations.push({
        type: "temporal",
        hitIds: ids(group),
        reason: `${group.length} Hinweise in zeitlicher Nähe`,
      });
    }
  }

  return relations;
}

/** UI-Label je Beziehungstyp (Hallensprache, farbunabhängig durch Wort + Anordnung). */
export const RELATION_LABEL: Record<RelationType, string> = {
  same_component: "Gleiches Bauteil",
  same_machine: "Gleiche Maschine",
  same_shift: "Gleiche Schicht",
  temporal: "Zeitliche Nähe",
};
