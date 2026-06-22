// ============================================================
//  FOREMAN Frontend — components/machine/pinned-chains.tsx
//  Zweck: ADDITIVE Erweiterung der Maschinen-Detail-Sicht (Sektion B): zeigt die an
//         diese Maschine ANGEPINNTEN Ereignisketten (Studie §4D) — jede mit ihrem
//         EINGEFRORENEN Stand-Stempel (dem Erstellzeitpunkt der Kette). Sprung in die
//         Ketten-Sicht (D, Deep-Link). Sind keine Ketten angepinnt, erscheint der
//         Block GAR NICHT (graceful). Reine Anzeige/Navigation, keine Aktorik.
//  Architektur-Einordnung: Sicht-Baustein (Schicht 3, client).
// ============================================================
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { CONFIDENCE_LABEL } from "@/lib/event-chains/confidence";
import { type PinnedChain, readPinnedChains } from "@/lib/event-chains/pin";
import { chainsHref } from "@/lib/event-chains/url";

function formatStamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return date.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function PinnedChains({ machineId }: { machineId: number }) {
  const [pins, setPins] = useState<PinnedChain[]>([]);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setPins(readPinnedChains(machineId));
    setReady(true);
  }, [machineId]);

  // Nichts angepinnt → kein Block (graceful, additiv: ändert die übrige B-Sicht nicht).
  if (!ready || pins.length === 0) {
    return null;
  }

  return (
    <section
      aria-label="Angepinnte Ereignisketten"
      className="flex flex-col gap-2 rounded-lg border border-line-subtle bg-surface-raised p-4"
    >
      <h2 className="text-h2 text-fg-primary">Angepinnte Ketten</h2>
      <ul className="flex flex-col gap-2">
        {pins.map((pin) => (
          <li key={pin.explanationId}>
            <Link
              href={chainsHref({ machine: machineId, explanation: pin.explanationId })}
              className="flex flex-col gap-1 rounded-md border border-line-subtle bg-surface-canvas p-3 transition-colors duration-[var(--motion-base)] motion-reduce:transition-none hover:border-line-strong focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
            >
              <span className="flex flex-wrap items-baseline gap-x-2">
                <span className="text-body text-fg-primary">
                  Kette um Alarm #{pin.anchorAlarmId} · {pin.eventCount} Ereignisse
                </span>
                {pin.isHypothesis ? (
                  <span className="text-caption text-note-caveat">Hypothese</span>
                ) : null}
              </span>
              <span className="flex flex-wrap items-baseline gap-x-2 text-caption text-fg-muted">
                <span>{CONFIDENCE_LABEL[pin.confidence]}</span>
                <span className="tabular-nums">Stand {formatStamp(pin.stampedAt)}</span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
