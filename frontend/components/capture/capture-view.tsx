// ============================================================
//  FOREMAN Frontend — components/capture/capture-view.tsx
//  Zweck: Einstieg der Erfassung (Sektion J, Studie §4J). Rollen-Split OHNE
//         bedingte Hooks (alle Hooks oben, Verzweigung auf Komponenten-Ebene):
//         erfassende Rollen (Werker/Schichtleiter/Techniker) bekommen das Formular,
//         der Manager eine reduzierte Lese-/Hinweis-Ansicht (liest, erfasst nicht).
//         `initialMachineId` kommt als Kontext-Vorauswahl aus ?machine= (aus B/Alarm
//         oder dem QuickCaptureFab). Sichtbarkeit ≤ Server-Guard (requireSection J).
//  Architektur-Einordnung: Sektions-Orchestrierung (Schicht 2, client).
// ============================================================
"use client";

import Link from "next/link";
import type { CurrentUser } from "@/lib/api/contracts";
import { captureRoleView } from "@/lib/capture/roles";
import { useSelectableMachines } from "@/lib/capture/use-machines";
import { CaptureForm } from "./capture-form";

export interface CaptureViewProps {
  user: CurrentUser;
  initialMachineId: number | null;
}

export function CaptureView({ user, initialMachineId }: CaptureViewProps) {
  const roleView = captureRoleView(user.role);
  // Immer aufgerufen (keine bedingten Hooks); für Nur-Lese-Rollen lädt er nicht.
  const machinesState = useSelectableMachines(user, roleView.canCapture);

  return (
    <section className="flex flex-col gap-5" aria-label="Eingabe und Erfassung">
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-fg-primary">Erfassung</h1>
        <p className="max-w-prose text-body text-fg-secondary">
          Was du gerade siehst — schnell und richtig zugeordnet ins System.
        </p>
      </div>

      {roleView.canCapture ? (
        <CaptureForm
          user={user}
          roleView={roleView}
          machinesState={machinesState}
          initialMachineId={initialMachineId}
        />
      ) : (
        <div className="flex flex-col gap-3 rounded-lg border border-line-subtle bg-surface-raised p-4">
          <p className="text-body text-fg-primary">
            Beobachtungen erfassen Werker, Techniker und Schichtleiter direkt an der Maschine.
          </p>
          <p className="text-body text-fg-secondary">
            Zum Nachlesen früherer Notizen geht es ins Gedächtnis der Halle.
          </p>
          <Link
            href="/memory"
            className="touch-target inline-flex w-fit items-center rounded-lg border border-line-strong bg-surface-overlay px-4 text-body font-semibold text-fg-primary"
          >
            Zur Suche im Gedächtnis
          </Link>
        </div>
      )}
    </section>
  );
}
