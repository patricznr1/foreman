// ============================================================
//  FOREMAN Frontend — components/prediction/influence-factor-list.tsx
//  Zweck: Block 2 (Einflussfaktoren, Studie §4E). Je Treiber: Richtung (Pfeil +
//         Wort) und relatives Gewicht (Balkenlänge + Wort) — FARBUNABHÄNGIG
//         lesbar. Werker-Label paraphrasiert (kein Verfahrensname). Werker sehen
//         knapp (Top 2), Techniker/Schichtleiter das volle Diagnose-Detail.
//  Architektur-Einordnung: Block-Komponente (Schicht 2). Rein präsentational.
// ============================================================
import { FACTOR_DIRECTION_LABEL } from "@/lib/prediction/factors";
import type { FactorRow } from "@/lib/prediction/types";

const KNAPP_LIMIT = 2;

/** Relatives Gewicht als Wort (farbunabhängige Zweitkodierung neben der Balkenlänge). */
function weightWord(weight: number): string {
  if (weight >= 0.66) return "stark";
  if (weight >= 0.33) return "mittel";
  return "leicht";
}

export function InfluenceFactorList({
  factors,
  detail = false,
}: {
  factors: FactorRow[];
  detail?: boolean;
}) {
  const shown = detail ? factors : factors.slice(0, KNAPP_LIMIT);

  if (shown.length === 0) {
    return (
      <section data-block="factors" aria-label="Einflussfaktoren" className="flex flex-col gap-2">
        <h3 className="text-caption font-semibold uppercase tracking-wide text-fg-muted">
          Einflussfaktoren
        </h3>
        <p className="text-body text-fg-muted">Keine ausschlaggebenden Faktoren.</p>
      </section>
    );
  }

  return (
    <section data-block="factors" aria-label="Einflussfaktoren" className="flex flex-col gap-3">
      <h3 className="text-caption font-semibold uppercase tracking-wide text-fg-muted">
        Einflussfaktoren
      </h3>
      <ul className="flex flex-col gap-3">
        {shown.map((f) => {
          const up = f.direction === "increases_risk";
          return (
            <li key={f.key} className="flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <span aria-hidden="true" className="font-mono text-body text-fg-secondary">
                  {up ? "↑" : "↓"}
                </span>
                <span className="text-body text-fg-primary">{f.label}</span>
                <span className="text-caption text-fg-muted">— {FACTOR_DIRECTION_LABEL[f.direction]}</span>
              </div>
              <div className="flex items-center gap-2">
                <div
                  aria-hidden="true"
                  className="h-2 w-full max-w-xs overflow-hidden rounded-full bg-surface-overlay"
                >
                  <div
                    className="h-2 rounded-full bg-fg-secondary"
                    style={{ width: `${Math.max(Math.round(f.weight * 100), 4)}%` }}
                  />
                </div>
                <span className="text-caption text-fg-muted">{weightWord(f.weight)}</span>
              </div>
            </li>
          );
        })}
      </ul>
      {!detail && factors.length > shown.length ? (
        <p className="text-caption text-fg-muted">
          Weitere Faktoren im Techniker-Detail.
        </p>
      ) : null}
    </section>
  );
}
