// ============================================================
//  FOREMAN Frontend — components/memory/archive-result-card.tsx
//  Zweck: Eine Treffer-Karte der ARCHIV-Suche (Paket 1c) — bewusst SCHLICHT:
//         Quellen-Glyph (Notiz/Wartung/Alarm), Wortlaut-Auszug, Zeitstempel,
//         Maschine + quellenspezifische, PII-freie Detail-Chips. KEINE Relevanz-
//         Stufe (kein Prozent/Score), KEIN Autor (der Treffer ist PII-frei), KEINE
//         erfundene Auflösung. Sprungbrett: Maschine (B) als Querlink.
//  Architektur-Einordnung: Sektions-Molekül (Schicht 2). Rein präsentational.
// ============================================================
import Link from "next/link";
import { SOURCE_LABEL } from "@/lib/memory/source";
import { relativeTime } from "@/lib/memory/time";
import type { ArchiveHitView } from "@/lib/memory/types";
import { cx } from "@/lib/ui/cx";
import { SourceGlyph } from "./source-glyph";

export interface ArchiveResultCardProps {
  hit: ArchiveHitView;
  /** Werker: große, knappe Karten. */
  largeCards: boolean;
}

/** Quellenspezifische, PII-freie Detail-Chips (Hallensprache, kein HMAC-Token). */
function detailChips(hit: ArchiveHitView): string[] {
  const chips: string[] = [];
  if (hit.source === "note" && hit.detail.shift) {
    chips.push(`Schicht ${hit.detail.shift}`);
  }
  if (hit.source === "maintenance" && hit.detail.type) {
    chips.push(`Art: ${hit.detail.type}`);
  }
  if (hit.source === "alarm") {
    if (hit.detail.severity) {
      chips.push(`Schwere: ${hit.detail.severity}`);
    }
    if (hit.detail.category) {
      chips.push(`Bereich: ${hit.detail.category}`);
    }
    if (hit.detail.code) {
      chips.push(`Code ${hit.detail.code}`);
    }
  }
  return chips;
}

export function ArchiveResultCard({ hit, largeCards }: ArchiveResultCardProps) {
  const machineLabel = hit.machineId !== null ? `Maschine ${hit.machineId}` : "ohne Maschinenbezug";
  const chips = detailChips(hit);
  return (
    <article
      aria-label={`${SOURCE_LABEL[hit.source]}, ${machineLabel}`}
      className={cx(
        "flex flex-col gap-3 rounded-lg border border-line-subtle bg-surface-raised",
        largeCards ? "p-5" : "p-4",
      )}
    >
      <SourceGlyph source={hit.source} />

      <p className={cx("text-fg-primary", largeCards ? "text-body-l" : "text-body")}>{hit.excerpt}</p>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-caption text-fg-muted">
        <span>{machineLabel}</span>
        <span>{relativeTime(hit.timestamp)}</span>
        {chips.map((chip) => (
          <span key={chip}>{chip}</span>
        ))}
      </div>

      {hit.machineId !== null ? (
        <nav aria-label="Weiter im Kontext">
          <Link
            href={`/machines/${hit.machineId}`}
            className="text-caption text-fg-secondary underline underline-offset-2 hover:text-fg-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
          >
            An Maschine ansehen
          </Link>
        </nav>
      ) : null}
    </article>
  );
}
