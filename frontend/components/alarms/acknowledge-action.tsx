// ============================================================
//  FOREMAN Frontend — components/alarms/acknowledge-action.tsx
//  Zweck: Die zweistufige HITL-Quittierung (Studie §4C). Tap → kurze Bestätigung;
//         bei KRITISCH mit Pflicht-Kontext (Begründung). Sicherheitsrelevantes Ziel
//         ≥ 64 px (touch-target-safety). Das Bestätigungs-Panel ist ein OVERLAY
//         (absolut positioniert) — die Zeilenhöhe bleibt konstant, damit die
//         Virtualisierung exakt bleibt. Deaktivierung immer MIT Grund (offline /
//         keine Route / keine Berechtigung). Quittieren = Alarm-Status-Aktion,
//         NIE eine Anlagen-Schaltung (die Invariante prüft der Hook vor dem Senden).
//  Architektur-Einordnung: Sicht-Komponente (Schicht 3, client).
// ============================================================
"use client";

import { useEffect, useId, useRef, useState } from "react";
import {
  ACK_DISABLED_TEXT,
  ackDisabledReason,
  acknowledgeEndpoint,
  buildAcknowledgeRecord,
  requiresAckContext,
} from "@/lib/alarms/acknowledge";
import type { AlarmViewModel } from "@/lib/alarms/types";
import { useAcknowledge } from "@/lib/alarms/use-acknowledge";
import { cx } from "@/lib/ui/cx";

export interface AcknowledgeActionProps {
  vm: AlarmViewModel;
  canAcknowledge: boolean;
  online: boolean;
  /** Nach erfolgreicher Quittierung (löst die Nachladung der Liste aus). */
  onAcknowledged: () => void;
  /** Zusätzliche Klassen am Wurzelelement (z. B. Stacking über dem Zeilen-Link). */
  className?: string;
}

export function AcknowledgeAction({
  vm,
  canAcknowledge,
  online,
  onAcknowledged,
  className,
}: AcknowledgeActionProps) {
  const { acknowledge, pending } = useAcknowledge();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [errorText, setErrorText] = useState<string | null>(null);
  const fieldId = useId();
  const firstFieldRef = useRef<HTMLTextAreaElement | HTMLButtonElement | null>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (open) {
      firstFieldRef.current?.focus();
    }
  }, [open]);

  // Schließen gibt den Fokus an den Auslöser zurück (Tastatur/Screenreader behalten
  // den Bedienkontext der HITL-Geste — WCAG 2.4.3).
  function close() {
    setOpen(false);
    setReason("");
    setErrorText(null);
    triggerRef.current?.focus();
  }

  function failureText(reason: "no-route" | "blocked" | "forbidden" | "unauthorized" | "error") {
    switch (reason) {
      case "forbidden":
        return "Quittieren für diesen Alarm nicht erlaubt";
      case "unauthorized":
        return "Anmeldung abgelaufen — bitte neu anmelden";
      case "no-route":
        return "Quittier-Route nicht verfügbar";
      case "blocked":
        return "Aktion nicht zulässig";
      case "error":
        return "Quittieren fehlgeschlagen — erneut versuchen";
    }
  }

  // Bereits quittiert/geklärt → Status statt Aktion (Puls ist aus, Häkchen + „von …").
  if (vm.lifecycle === "acknowledged" || vm.lifecycle === "cleared") {
    return (
      <span className={cx("inline-flex items-center gap-2 text-caption text-fg-secondary", className)}>
        <span aria-hidden="true" className="text-state-ok">
          ✓
        </span>
        <span>{vm.acknowledgedLabel ?? (vm.lifecycle === "cleared" ? "geklärt" : "quittiert")}</span>
      </span>
    );
  }

  const endpoint = acknowledgeEndpoint(vm);
  const disabled = ackDisabledReason({ online, canAcknowledge, endpoint });

  // Keine Berechtigung → gar keine Aktion zeigen (Werker/Manager).
  if (disabled === "no-permission") {
    return null;
  }

  if (disabled !== null) {
    return (
      <span
        className={cx("inline-flex max-w-44 items-center text-caption text-fg-muted", className)}
        title={ACK_DISABLED_TEXT[disabled]}
      >
        {ACK_DISABLED_TEXT[disabled]}
      </span>
    );
  }

  const needsContext = requiresAckContext(vm.priority);
  const submitDisabled = pending === vm.id || (needsContext && reason.trim().length === 0);

  async function confirm() {
    setErrorText(null);
    // Auditierbarer Datensatz (wer/wann/warum): erzwingt die Pflicht-Begründung bei
    // kritisch und reicht sie an den Quittier-Request weiter (Audit-Bezug Sektion I).
    const record = buildAcknowledgeRecord(vm, reason, new Date().toISOString());
    const result = await acknowledge(vm, record.reason);
    if (result.ok) {
      setOpen(false);
      setReason("");
      onAcknowledged();
    } else {
      setErrorText(failureText(result.reason));
    }
  }

  return (
    <div className={cx("relative", className)}>
      <button
        ref={triggerRef}
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-label={`Alarm an ${vm.machineLabel} quittieren`}
        className={cx(
          "touch-target-safety inline-flex items-center justify-center rounded-md px-4 text-body font-semibold",
          "bg-alarm-critical text-fg-on-accent",
          vm.priority !== "critical" && "bg-surface-overlay text-fg-primary border border-line-strong",
        )}
      >
        Quittieren
      </button>

      {open ? (
        <div
          role="dialog"
          aria-label={`Alarm an ${vm.machineLabel} quittieren`}
          className="absolute right-0 z-20 mt-2 w-72 rounded-lg border border-line-strong bg-surface-overlay p-3 shadow-lg"
          onKeyDown={(event) => {
            if (event.key === "Escape") {
              close();
            }
          }}
        >
          <p className="mb-2 text-caption text-fg-secondary">
            {vm.priority === "critical"
              ? "Kritischen Alarm quittieren — Begründung erforderlich (auditierbar)."
              : "Alarm quittieren? Diese Bestätigung ist auditierbar."}
          </p>
          {needsContext ? (
            <textarea
              ref={firstFieldRef as React.RefObject<HTMLTextAreaElement>}
              id={fieldId}
              aria-label="Begründung für die Quittierung"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
              rows={2}
              placeholder="Was wurde geprüft? (Pflicht)"
              className="mb-2 w-full rounded-md border border-line-subtle bg-surface-raised p-2 text-body text-fg-primary"
            />
          ) : null}
          {errorText ? (
            <p role="alert" className="mb-2 text-caption text-note-caveat">
              {errorText}
            </p>
          ) : null}
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              ref={!needsContext ? (firstFieldRef as React.RefObject<HTMLButtonElement>) : undefined}
              onClick={close}
              className="touch-target inline-flex items-center rounded-md px-3 text-body text-fg-secondary"
            >
              Abbrechen
            </button>
            <button
              type="button"
              onClick={() => void confirm()}
              disabled={submitDisabled}
              className={cx(
                "touch-target inline-flex items-center rounded-md px-4 text-body font-semibold",
                "bg-state-ok text-fg-on-accent",
                submitDisabled && "opacity-50",
              )}
            >
              {pending === vm.id ? "…" : "Bestätigen"}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
