// ============================================================
//  FOREMAN Frontend — components/event-chains/saved-chains-browser.tsx
//  Zweck: Gespeicherte Ereignisketten einer Maschine durchsehen — Liste links,
//         geöffnete Kette rechts.
//  Warum als eigener Baustein (02.09.2026): Dieses Paar wird an ZWEI Stellen
//         gebraucht — in der Sektion D und seit heute eingebettet in der
//         Maschinensicht, wo der Knopf „Ereigniskette" die Ketten an Ort und
//         Stelle zeigt statt wegzuführen. Es dort nachzubauen hiesse, zwei
//         Fassungen derselben Darstellung zu führen: Sie laufen auseinander,
//         sobald eine angefasst wird, und beide sehen richtig aus.
//  GESTEUERT und nicht selbstverwaltend: Die Auswahl liegt beim Aufrufer. In
//         Sektion D setzt sie auch der Rekonstruktions-Auslöser (`onOpenSibling`),
//         der ausserhalb dieses Bausteins steht — hielte der Baustein sie selbst,
//         käme sein Zustand mit dem des Aufrufers auseinander.
//  Architektur-Einordnung: Sicht-Baustein (Schicht 3, client). Read-only.
// ============================================================
"use client";

import { ResultWithProvenance } from "@/components/ondemand";
import { useChainDetail } from "@/lib/event-chains/use-saved-chains";
import { ASSEMBLE_FAILURE_TEXT, assembleChainCard } from "@/lib/event-chains/view-model";
import { FiveState } from "@/lib/ui/five-states";
import { SavedChainsList } from "./saved-chains-list";
import { TimelineNarrative } from "./timeline-narrative";

export interface SavedChainsBrowserProps {
  /** Maschinen-Filter; `null` = über alle sichtbaren Maschinen. */
  machineId: number | null;
  /** Die geöffnete Kette — beim Aufrufer gehalten. */
  selectedId: number | null;
  onSelect: (explanationId: number) => void;
  /** Anpinnen erlaubt (Techniker/Schichtleiter). */
  canPin: boolean;
  /** Überschrift der Liste — in der Maschinensicht sitzt die schon aussen. */
  showHeading?: boolean;
}

export function SavedChainsBrowser({
  machineId,
  selectedId,
  onSelect,
  canPin,
  showHeading = true,
}: SavedChainsBrowserProps) {
  const detail = useChainDetail(selectedId);

  return (
    <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,20rem)_1fr]">
      <div className="flex flex-col gap-2">
        {showHeading ? <h2 className="text-h2 text-fg-primary">Gespeicherte Ketten</h2> : null}
        <SavedChainsList machineId={machineId} selectedId={selectedId} onOpen={onSelect} />
      </div>
      <div className="min-w-0">
        <FiveState
          state={detail}
          label="Kette"
          empty={
            <div
              role="status"
              className="rounded-lg border border-line-subtle bg-surface-raised p-4 text-body text-fg-muted"
            >
              Wähle links eine gespeicherte Kette, um sie zu öffnen.
            </div>
          }
        >
          {(data, freshness) => {
            const result = assembleChainCard(data);
            if (!result.ok) {
              return (
                <div
                  role="alert"
                  className="rounded-lg border border-line-subtle bg-surface-raised p-4 text-body text-note-caveat"
                >
                  {ASSEMBLE_FAILURE_TEXT[result.reason]}
                </div>
              );
            }
            const { card } = result;
            const basis = card.recallUsed
              ? "Datenbasis: belegte Ereignisse + ähnliche Vergangenheitsfälle"
              : "Datenbasis: belegte Ereignisse";
            return (
              <ResultWithProvenance
                freshness={freshness}
                stampedAt={card.stampedAt}
                aiGenerated
                caveat={card.isHypothesis}
                basis={basis}
              >
                <TimelineNarrative card={card} canPin={canPin} onOpenSibling={onSelect} />
              </ResultWithProvenance>
            );
          }}
        </FiveState>
      </div>
    </div>
  );
}
