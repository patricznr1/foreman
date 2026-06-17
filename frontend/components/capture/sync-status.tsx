// ============================================================
//  FOREMAN Frontend — components/capture/sync-status.tsx
//  Zweck: Der sichtbare Sync-Status der Erfassung (Studie §4J). „wartet auf Netz"
//         ist NORMAL — ruhiges Symbol, KEIN Alarm-Rot (gedämpft / state-ok). Höfliche
//         Live-Region (role=status, aria-live=polite), damit Screenreader den
//         Übergang „gesendet"/„gepuffert" mitbekommen, ohne zu drängeln.
//  Architektur-Einordnung: Sicht-Komponente (Schicht 3). Rein präsentational.
// ============================================================
import { syncStatusText } from "@/lib/capture/sync";
import type { SyncState } from "@/lib/capture/types";
import { cx } from "@/lib/ui/cx";

export function SyncStatus({ state }: { state: SyncState }) {
  const text = syncStatusText(state);
  if (!text) {
    return null;
  }
  const synced = state.kind === "synced";
  return (
    <p
      role="status"
      aria-live="polite"
      className={cx(
        "inline-flex items-center gap-2 text-caption",
        synced ? "text-fg-secondary" : "text-fg-muted",
      )}
      data-sync={state.kind}
    >
      <span aria-hidden="true" className={synced ? "text-state-ok" : "text-fg-muted"}>
        {state.kind === "sending" ? "…" : synced ? "✓" : "⧖"}
      </span>
      <span>{text}</span>
    </p>
  );
}
