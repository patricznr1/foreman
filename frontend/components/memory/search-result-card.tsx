// ============================================================
//  FOREMAN Frontend — components/memory/search-result-card.tsx
//  Zweck: Eine Treffer-Karte der Bedeutungssuche (Studie §4H, §5.5). Trägt: Quelle
//         (formcodiert), Relevanz (Stärke/Position, KEIN Prozent), Maschine/Zeit,
//         maskierter Auszug, maskiertes Autor-Handle (#hex6) und — wenn bekannt —
//         die Auflösung (graceful: das Gedächtnis führt derzeit kein Auflösungsfeld,
//         also wird KEINE erfunden). Ein Treffer ist Sprungbrett: Maschine (B) und
//         Ereigniskette (D, folgt) als Querlinks (kein Hover-only, §5.8).
//  Architektur-Einordnung: Sektions-Molekül (Schicht 2). Rein präsentational.
// ============================================================
import Link from "next/link";
import type { MemoryRoleView } from "@/lib/memory/roles";
import { relativeTime } from "@/lib/memory/time";
import type { MemoryHit } from "@/lib/memory/types";
import { cx } from "@/lib/ui/cx";
import { RelevanceMark } from "./relevance-mark";
import { SourceGlyph } from "./source-glyph";

export interface SearchResultCardProps {
  hit: MemoryHit;
  /** Gesamtzahl Treffer (für den Rang-Text "Rang X von N"). */
  total: number;
  roleView: MemoryRoleView;
}

interface CardLink {
  label: string;
  /** Existierende Route oder null (Ziel folgt → graceful, kein toter Link). */
  href: string | null;
}

function CardLinks({ hit, roleView }: { hit: MemoryHit; roleView: MemoryRoleView }) {
  const links: CardLink[] = [];
  if (hit.machineId !== null) {
    links.push({ label: "An Maschine ansehen", href: `/machines/${hit.machineId}` });
  }
  if (roleView.jumpToDiagnosis) {
    // Ereigniskette (Sektion D) ist noch nicht gebaut → bewusst graceful.
    links.push({ label: "Ereigniskette rekonstruieren", href: null });
  }
  if (links.length === 0) {
    return null;
  }
  return (
    <nav aria-label="Weiter im Kontext" className="flex flex-wrap gap-x-4 gap-y-1">
      {links.map((link) =>
        link.href ? (
          <Link
            key={link.label}
            href={link.href}
            className="text-caption text-fg-secondary underline underline-offset-2 hover:text-fg-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
          >
            {link.label}
          </Link>
        ) : (
          <span key={link.label} aria-disabled="true" className="text-caption text-fg-muted">
            {link.label} (folgt)
          </span>
        ),
      )}
    </nav>
  );
}

export function SearchResultCard({ hit, total, roleView }: SearchResultCardProps) {
  const machineLabel = hit.machineId !== null ? `Maschine ${hit.machineId}` : "ohne Maschinenbezug";
  return (
    <article
      aria-label={`Schichtnotiz, ${machineLabel}`}
      className={cx(
        "flex flex-col gap-3 rounded-lg border border-line-subtle bg-surface-raised",
        roleView.largeCards ? "p-5" : "p-4",
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <SourceGlyph source={hit.source} />
        <RelevanceMark strength={hit.strength} rank={hit.rank} total={total} />
      </div>

      <p className={cx("text-fg-primary", roleView.largeCards ? "text-body-l" : "text-body")}>
        {hit.excerpt}
      </p>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-caption text-fg-muted">
        <span>{machineLabel}</span>
        {hit.shift ? <span>Schicht {hit.shift}</span> : null}
        <span>{relativeTime(hit.createdAt)}</span>
        {hit.authorHandle ? <span className="font-mono">{hit.authorHandle}</span> : null}
      </div>

      {hit.resolution ? (
        <p className="text-caption text-fg-secondary">Gelöst durch: {hit.resolution}</p>
      ) : null}

      <CardLinks hit={hit} roleView={roleView} />
    </article>
  );
}
