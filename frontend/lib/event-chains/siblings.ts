// ============================================================
//  FOREMAN Frontend — lib/event-chains/siblings.ts
//  Zweck: Formt die ehrlichen Backend-Schwester-Referenzen fürs UI (§21-D). Eine
//         Referenz ist NUR dann ein klickbarer Querverweis (`navigable`), wenn eine
//         reale Ziel-Erklärung existiert. Es wird NICHTS erfunden; leere Eingabe →
//         leere Ausgabe (der Schwesterketten-Block erscheint dann gar nicht).
//  Architektur-Einordnung: reine Abbildung (Schicht 2).
// ============================================================
import type { SiblingReference } from "@/lib/api/contracts";
import type { SiblingModel } from "./types";

export function toSiblingModels(siblings: SiblingReference[]): SiblingModel[] {
  return siblings.map((sibling) => ({
    recallRef: sibling.recall_ref,
    machineId: sibling.machine_id,
    machineClass: sibling.machine_class,
    explanationId: sibling.explanation_id,
    basis: sibling.similarity_basis,
    excerpt: sibling.excerpt,
    navigable: sibling.explanation_id !== null,
  }));
}

/** Klartext-Label einer Schwester-Referenz — ehrlich nach Verfügbarkeit. */
export function siblingLabel(sibling: SiblingModel): string {
  if (sibling.machineId !== null && sibling.machineClass !== null) {
    return `Schwestermaschine ${sibling.machineId} (${sibling.machineClass})`;
  }
  if (sibling.machineId !== null) {
    return `Schwestermaschine ${sibling.machineId}`;
  }
  if (sibling.machineClass !== null) {
    return `Schwestermaschine der Klasse ${sibling.machineClass}`;
  }
  return "Ähnlicher Vergangenheitsfall";
}
