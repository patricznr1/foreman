// ============================================================
//  FOREMAN Frontend — components/event-chains/pin-chain-action.tsx
//  Zweck: Pinnt eine gespeicherte Kette an die Maschinen-Zeitachse (B, Studie §4D)
//         — mit EINGEFRORENEM Stand-Stempel (dem Erstellzeitpunkt der Kette). Nur
//         für Rollen mit Pin-Recht (Techniker/Schichtleiter; der Aufrufer gated).
//         HITL: das Anpinnen ist eine Anzeige-/Merk-Aktion, keine Anlagen-Aktorik.
//  Architektur-Einordnung: Aktions-Atom (Schicht 2, client).
// ============================================================
"use client";

import { useEffect, useState } from "react";
import { isPinned, pinChain, unpinChain } from "@/lib/event-chains/pin";
import type { ChainCardModel } from "@/lib/event-chains/types";

export function PinChainAction({ card }: { card: ChainCardModel }) {
  const [pinned, setPinned] = useState(false);

  useEffect(() => {
    setPinned(isPinned(card.explanationId));
  }, [card.explanationId]);

  if (card.machineId === null) {
    return (
      <p className="text-caption text-fg-muted">
        Anpinnen nicht möglich — der Kette ist keine Maschine zugeordnet.
      </p>
    );
  }
  const machineId = card.machineId;

  function toggle() {
    if (pinned) {
      unpinChain(card.explanationId);
      setPinned(false);
      return;
    }
    pinChain({
      explanationId: card.explanationId,
      machineId,
      anchorAlarmId: card.anchorAlarmId,
      confidence: card.confidence,
      isHypothesis: card.isHypothesis,
      eventCount: card.nodes.length,
      stampedAt: card.stampedAt,
      pinnedAt: new Date().toISOString(),
    });
    setPinned(true);
  }

  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={pinned}
      className="inline-flex min-h-[var(--touch-min)] items-center justify-center rounded-lg border border-line-strong bg-surface-raised px-4 text-body text-fg-primary transition-colors duration-[var(--motion-base)] motion-reduce:transition-none hover:bg-surface-overlay focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
    >
      {pinned ? "Von der Maschine lösen" : "An die Maschine anpinnen"}
    </button>
  );
}
