// ============================================================
//  FOREMAN Frontend — lib/ui/five-states.tsx
//  Zweck: Die FÜNF-ZUSTÄNDE-HÜLLE (Prinzip 2 / §5.5) als geerbtes Muster: jede
//         datentragende Sicht stellt live / gecacht / lädt / leer / Fehler
//         identisch dar. children(data, freshness) bekommt den Frische-Hinweis
//         (für den Stand-Stempel bei "gecacht" — Degradation friert ein, kein
//         weißer Screen). Ruhige, barrierearme Default-Platzhalter (Live-Region).
//  Architektur-Einordnung: Darstellungs-Muster (Schicht 1/2). Atom-frei.
// ============================================================
import type { ReactNode } from "react";
import type { DataState } from "@/lib/state/view-state";

/** Technische Fehlergründe → Hallensprache (kein internes Vokabular). */
export function friendlyError(message: string): string {
  switch (message) {
    case "forbidden":
      return "Kein Zugriff auf diese Sicht";
    case "unauthorized":
      return "Sitzung abgelaufen — bitte neu anmelden";
    default:
      return "Daten derzeit nicht verfügbar";
  }
}

export interface FiveStateProps<T> {
  state: DataState<T>;
  /** Kurzbezeichnung der Sicht (für Platzhalter-Texte). */
  label?: string;
  children: (data: T, freshness: "live" | "cached") => ReactNode;
  loading?: ReactNode;
  empty?: ReactNode;
  error?: (message: string) => ReactNode;
}

function Placeholder({
  tone,
  role,
  busy,
  children,
}: {
  tone: "muted" | "caveat";
  role: "status" | "alert";
  busy?: boolean;
  children: ReactNode;
}) {
  const color = tone === "caveat" ? "text-note-caveat" : "text-fg-muted";
  return (
    <div
      role={role}
      aria-busy={busy ? true : undefined}
      className={`flex min-h-24 items-center justify-center rounded-lg border border-line-subtle bg-surface-raised p-4 text-body ${color}`}
    >
      {children}
    </div>
  );
}

export function FiveState<T>({ state, label, children, loading, empty, error }: FiveStateProps<T>) {
  switch (state.kind) {
    case "loading":
      return (
        <>{loading ?? <Placeholder tone="muted" role="status" busy>{label ? `${label} lädt …` : "Lädt …"}</Placeholder>}</>
      );
    case "error":
      return (
        <>
          {error ? (
            error(state.message)
          ) : (
            <Placeholder tone="caveat" role="alert">
              {friendlyError(state.message)}
            </Placeholder>
          )}
        </>
      );
    case "empty":
      return (
        <>{empty ?? <Placeholder tone="muted" role="status">{label ? `${label}: keine Daten` : "Keine Daten"}</Placeholder>}</>
      );
    case "live":
      return <>{children(state.data, "live")}</>;
    case "cached":
      return <>{children(state.data, "cached")}</>;
  }
}
