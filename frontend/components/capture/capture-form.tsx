// ============================================================
//  FOREMAN Frontend — components/capture/capture-form.tsx
//  Zweck: Das reibungsarme Erfassungs-Formular (Studie §4J, Leitfrage „in unter
//         15 Sekunden korrekt zugeordnet ins System"). Einspaltig: Freitext groß
//         ZUERST, dann vorausgefüllte Zuordnungs-Chips (Maschine/Schicht), dann
//         Kategorie-Buttons, unten der große Speichern-Button (≥ 64 px). Offline →
//         lokal puffern mit sichtbarem Sync-Status (Degradation = Offline-Queue).
//         HITL: eine Notiz erfassen ist eine Daten-Eingabe — keine Aktorik.
//         Pseudonymisierung/Maskierung passieren serverseitig (transparent gemacht);
//         der lokale Puffer wird nach erfolgreichem Senden gelöscht.
//  Architektur-Einordnung: Sektions-Komponente (Schicht 3, client).
// ============================================================
"use client";

import { useEffect, useId, useState } from "react";
import type { CurrentUser } from "@/lib/api/contracts";
import type { CaptureRoleView } from "@/lib/capture/roles";
import { SHIFTS } from "@/lib/capture/shifts";
import { isSubmittable } from "@/lib/capture/submit";
import { deriveSyncState } from "@/lib/capture/sync";
import type { Classification } from "@/lib/capture/types";
import { useCreateNote } from "@/lib/capture/use-create-note";
import type { MachinesState } from "@/lib/capture/use-machines";
import { useOutbox } from "@/lib/capture/use-outbox";
import { useOnline } from "@/lib/ondemand/use-online";
import { cx } from "@/lib/ui/cx";
import { CategoryButtons } from "./category-buttons";
import { ContextSuggestions } from "./context-suggestions";
import { MachineSelect } from "./machine-select";
import { SyncStatus } from "./sync-status";
import { VoiceCapturePlaceholder } from "./voice-capture-placeholder";

export interface CaptureFormProps {
  user: CurrentUser;
  roleView: CaptureRoleView;
  machinesState: MachinesState;
  initialMachineId: number | null;
}

type Confirmation = { kind: "sent" | "queued" } | null;

function errorText(reason: "validation" | "unauthorized" | "forbidden"): string {
  switch (reason) {
    case "validation":
      return "Bitte eine Beobachtung eingeben.";
    case "unauthorized":
      return "Anmeldung abgelaufen — bitte neu anmelden.";
    case "forbidden":
      return "Erfassen für diese Maschine nicht erlaubt.";
  }
}

export function CaptureForm({ user, roleView, machinesState, initialMachineId }: CaptureFormProps) {
  const online = useOnline();
  const { submit, sending } = useCreateNote(String(user.id), online);
  const { pending, flushing, hadError, refresh } = useOutbox(online);

  const [text, setText] = useState("");
  const [machineId, setMachineId] = useState<number | null>(initialMachineId);
  const [shift, setShift] = useState<string | null>(null);
  const [classification, setClassification] = useState<Classification | null>(null);
  const [confirmation, setConfirmation] = useState<Confirmation>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [lastSyncedAt, setLastSyncedAt] = useState<string | null>(null);

  // Härtung: eine vorausgewählte Maschine (aus ?machine=), die NICHT im Scope des
  // Nutzers liegt, wird verworfen, sobald die Liste da ist — keine Vorauswahl statt
  // einer fremden Zuordnung (Sichtbarkeit ≤ Scope; der Nutzer wählt dann selbst).
  useEffect(() => {
    if (machineId !== null && machinesState.kind === "ready") {
      const inScope = machinesState.machines.some((machine) => machine.id === machineId);
      if (!inScope) {
        setMachineId(null);
      }
    }
  }, [machineId, machinesState]);

  const textFieldId = useId();
  const draft = { text, machineId, shift, classification };
  const canSubmit = isSubmittable(draft) && !sending;
  const syncState = deriveSyncState({ sending, flushing, pending, hadError, lastSyncedAt });

  async function onSubmit() {
    if (!isSubmittable(draft)) {
      setFormError("Bitte eine Beobachtung eingeben.");
      return;
    }
    setFormError(null);
    const result = await submit(draft);
    if (result.kind === "sent") {
      setLastSyncedAt(result.note.created_at);
      setConfirmation({ kind: "sent" });
      setText(""); // Folgenotiz: Zuordnung (Maschine/Schicht/Kategorie) bleibt erhalten.
    } else if (result.kind === "queued") {
      setConfirmation({ kind: "queued" });
      setText("");
      refresh();
    } else {
      setFormError(errorText(result.reason));
    }
  }

  return (
    <div className="flex flex-col gap-5">
      {/* 1) Freitext zuerst — das Wichtigste, großes Feld. */}
      <div className="flex flex-col gap-2">
        <label htmlFor={textFieldId} className="text-body-l font-semibold text-fg-primary">
          Was hast du beobachtet?
        </label>
        <textarea
          id={textFieldId}
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            if (confirmation) setConfirmation(null);
            if (formError) setFormError(null);
          }}
          rows={4}
          placeholder="z. B. Lager läuft heiß, Geräusch an der Spindel seit Schichtbeginn"
          className="w-full rounded-lg border border-line-strong bg-surface-raised p-3 text-body-l text-fg-primary"
        />
        <p className="text-caption text-fg-muted">
          Namen werden vor dem Speichern automatisch geschützt — schreib einfach, wie du sprichst.
        </p>
        <VoiceCapturePlaceholder prominent={roleView.voiceFirst} />
      </div>

      {/* 2) Zuordnung per Chips — vorausgefüllt aus dem Kontext, ein Tap zum Ändern. */}
      <div className="flex flex-col gap-2">
        <span className="text-body font-semibold text-fg-primary">Maschine</span>
        <MachineSelect state={machinesState} value={machineId} onChange={setMachineId} />
      </div>

      <div className="flex flex-col gap-2">
        <span className="text-body font-semibold text-fg-primary">Schicht</span>
        <div role="group" aria-label="Schicht zuordnen" className="flex flex-wrap gap-2">
          {SHIFTS.map((option) => {
            const active = shift === option.value;
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => setShift(active ? null : option.value)}
                aria-pressed={active}
                className={cx(
                  "touch-target inline-flex items-center rounded-lg px-4 text-body",
                  active
                    ? "border border-line-strong bg-surface-overlay font-semibold text-fg-primary"
                    : "border border-line-subtle bg-surface-raised text-fg-secondary",
                )}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* 3) Kategorie — große, mehrkanalige Buttons (vom Werker manuell gewählt). */}
      <div className="flex flex-col gap-2">
        <span className="text-body font-semibold text-fg-primary">Einordnung (optional)</span>
        <CategoryButtons value={classification} onChange={setClassification} />
      </div>

      {/* 4) Absenden — großes, eindeutiges Ziel (≥ 64 px). */}
      <div className="flex flex-col gap-2">
        <button
          type="button"
          onClick={() => void onSubmit()}
          disabled={!canSubmit}
          className={cx(
            "touch-target-safety inline-flex w-full items-center justify-center rounded-lg px-6",
            "bg-state-ok text-fg-on-accent text-body-l font-semibold",
            !canSubmit && "opacity-50",
          )}
        >
          {sending ? "wird gesendet …" : "Notiz speichern"}
        </button>
        {!isSubmittable(draft) ? (
          <p className="text-caption text-fg-muted">Beobachtung eingeben, dann speichern.</p>
        ) : null}
        {formError ? (
          <p role="alert" className="text-caption text-note-caveat">
            {formError}
          </p>
        ) : null}
        <SyncStatus state={syncState} />
        {confirmation ? (
          <div role="status" className="rounded-lg border border-line-subtle bg-surface-raised p-3">
            <p className="text-body text-fg-primary">
              {confirmation.kind === "sent"
                ? "Notiz erfasst."
                : "Notiz lokal gespeichert — wird gesendet, sobald wieder Netz da ist."}
            </p>
            <p className="text-caption text-fg-secondary">
              Sie erscheint in der Maschinen-Historie und ist später über die Suche auffindbar.
            </p>
          </div>
        ) : null}
      </div>

      {/* 5) Dezente Brücke zu H — frühere Fälle an dieser Maschine (kein Pop-up-Zwang). */}
      <ContextSuggestions
        key={machineId ?? "none"}
        text={text}
        machineId={machineId}
        enabled={roleView.showSuggestions && online}
      />
    </div>
  );
}
