// ============================================================
//  FOREMAN Frontend — components/prediction/decision-action.tsx
//  Zweck: Die menschliche HITL-Entscheidung (Studie §4E, drei Haltungen):
//         Quittieren ODER Verwerfen — zweistufig, mit Begründung (auditierbar).
//         HARTE GRENZE: keine Anlagen-Aktorik — der Hinweis macht das sichtbar.
//         Begründung ist Pflicht beim Verwerfen und bei erhöhtem Risiko (Submit
//         gesperrt, bis sie da ist). Handschuhsichere Ziele; Fokus kehrt zurück.
//  Architektur-Einordnung: HITL-Aktion (Schicht 2). Rein präsentational + lokal.
// ============================================================
"use client";

import { useEffect, useId, useRef, useState } from "react";
import type { RiskDecision } from "@/lib/api/contracts";
import { type DecisionDisposition, requiresDecisionReason } from "@/lib/prediction/decision";
import { cx } from "@/lib/ui/cx";

export interface DecisionActionProps {
  decision: RiskDecision;
  onDecide: (disposition: DecisionDisposition, reason: string | null) => void;
  pending?: boolean;
}

const DISPOSITION_LABEL: Record<DecisionDisposition, string> = {
  acknowledged: "Quittieren",
  dismissed: "Verwerfen",
};

export function DecisionAction({ decision, onDecide, pending = false }: DecisionActionProps) {
  const [open, setOpen] = useState<DecisionDisposition | null>(null);
  const [reason, setReason] = useState("");
  const reasonId = useId();
  const triggerRef = useRef<HTMLButtonElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const reasonRequired = open !== null ? requiresDecisionReason(open, decision) : false;
  const canSubmit = open !== null && !pending && (!reasonRequired || reason.trim().length > 0);

  // Fokus in das Begründungsfeld, sobald der Bestätigungs-Schritt aufgeht.
  useEffect(() => {
    if (open !== null) {
      textareaRef.current?.focus();
    }
  }, [open]);

  function start(disposition: DecisionDisposition, event: React.MouseEvent<HTMLButtonElement>) {
    triggerRef.current = event.currentTarget;
    setReason("");
    setOpen(disposition);
  }

  function cancel() {
    setOpen(null);
    setReason("");
    triggerRef.current?.focus();
  }

  function confirm() {
    if (open === null || !canSubmit) {
      return;
    }
    const trimmed = reason.trim();
    onDecide(open, trimmed.length > 0 ? trimmed : null);
    setOpen(null);
    setReason("");
    triggerRef.current?.focus();
  }

  if (open === null) {
    return (
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap gap-3">
          {(["acknowledged", "dismissed"] as const).map((disposition) => (
            <button
              key={disposition}
              type="button"
              onClick={(event) => start(disposition, event)}
              className={cx(
                "inline-flex min-h-[var(--touch-safety)] items-center justify-center rounded-lg px-5 text-body font-medium",
                "border border-line-strong bg-surface-overlay text-fg-primary",
                "transition-colors duration-[var(--motion-base)] motion-reduce:transition-none hover:bg-surface-raised",
                "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring",
              )}
            >
              {DISPOSITION_LABEL[disposition]}
            </button>
          ))}
        </div>
        <p className="text-caption text-fg-muted">
          Ihre Entscheidung wird protokolliert — die Anlage wird dadurch nicht geschaltet.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-line-subtle bg-surface-raised p-3">
      <label htmlFor={reasonId} className="text-caption font-medium text-fg-secondary">
        {DISPOSITION_LABEL[open]} — Begründung
        {reasonRequired ? <span className="text-note-caveat"> (Pflicht)</span> : " (optional)"}
      </label>
      <textarea
        id={reasonId}
        ref={textareaRef}
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        rows={2}
        className={cx(
          "w-full rounded-md border border-line-strong bg-surface-canvas p-2 text-body text-fg-primary",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring",
        )}
      />
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={confirm}
          disabled={!canSubmit}
          aria-disabled={!canSubmit}
          className={cx(
            "inline-flex min-h-[var(--touch-safety)] items-center justify-center rounded-lg px-5 text-body font-medium",
            "border border-line-strong bg-surface-overlay text-fg-primary hover:bg-surface-raised",
            "transition-colors duration-[var(--motion-base)] motion-reduce:transition-none",
            "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring",
            "disabled:cursor-not-allowed disabled:opacity-60 disabled:hover:bg-surface-overlay",
          )}
        >
          Bestätigen
        </button>
        <button
          type="button"
          onClick={cancel}
          className={cx(
            "inline-flex min-h-[var(--touch-safety)] items-center justify-center rounded-lg px-5 text-body",
            "border border-line-subtle bg-transparent text-fg-secondary hover:bg-surface-raised",
            "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring",
          )}
        >
          Abbrechen
        </button>
      </div>
    </div>
  );
}
