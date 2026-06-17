// ============================================================
//  FOREMAN Frontend — lib/memory/cluster.ts
//  Zweck: Verdichtung der Trefferliste (Studie §4H: "die Verknüpfung ist der Wert,
//         nicht die rohe Trefferliste"). Gruppiert NUR über das, was das Gedächtnis
//         real hergibt: dieselbe Maschine. Der Auflösungs-Bezug ("alle gelöst durch
//         …") ist graceful null — das Backend führt kein Auflösungsfeld, also wird
//         er NICHT erfunden, sondern im UI als folgt markiert.
//  Architektur-Einordnung: View-State (Schicht 2). Reine Funktion.
// ============================================================
import type { MemoryCluster, MemoryHit } from "./types";

/** Kleinster (bester) Rang einer Trefferguppe — für die Sortierung der Cluster. */
function bestRank(hits: MemoryHit[]): number {
  return hits.reduce((min, hit) => Math.min(min, hit.rank), Number.POSITIVE_INFINITY);
}

/**
 * Gruppiert Treffer nach Maschine; nur Gruppen mit >= 2 Treffern gelten als
 * Verdichtung (ein Einzeltreffer ist kein Muster). Sortierung: größere Gruppe
 * zuerst, bei Gleichstand die präsentere (kleinster Rang). Reihenfolge innerhalb
 * der Gruppe bleibt die Relevanz-Reihenfolge (Rang).
 */
export function clusterByMachine(hits: MemoryHit[]): MemoryCluster[] {
  const byMachine = new Map<number, MemoryHit[]>();
  for (const hit of hits) {
    if (hit.machineId === null) {
      continue;
    }
    const group = byMachine.get(hit.machineId) ?? [];
    group.push(hit);
    byMachine.set(hit.machineId, group);
  }
  const clusters: MemoryCluster[] = [];
  for (const [machineId, group] of byMachine) {
    if (group.length < 2) {
      continue;
    }
    clusters.push({ machineId, hits: group, sharedResolution: null });
  }
  clusters.sort(
    (a, b) => b.hits.length - a.hits.length || bestRank(a.hits) - bestRank(b.hits),
  );
  return clusters;
}
