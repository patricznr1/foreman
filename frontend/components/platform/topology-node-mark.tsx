// ============================================================
//  FOREMAN Frontend — components/platform/topology-node-mark.tsx
//  Zweck: Die zugängliche Knoten-Karte der Topologie (Studie §4I/§5.8): Status
//         MEHRKANALIG (Form-Glyph + Token-Farbe + Wort), Datenrichtung als FORM
//         (Pfeil, NICHT Farbe), letzte Aktivität dezent, interne/[VISION]-Knoten
//         klar markiert. Die exportierten Glyphen (StatusGlyph/DirectionArrow) sind
//         bespoke, token-getriebenes SVG (`var(--color-*)` / currentColor, KEINE
//         Lib) und werden auch vom Lagebild-Graphen genutzt. Ruhig (ISA-101),
//         „unbekannt" bleibt neutral — nie grün.
//  Architektur-Einordnung: bespoke SVG-Atom + Knoten-Karte (Schicht 2, client).
// ============================================================
import { cx } from "@/lib/ui/cx";
import {
  connectionStatusLabel,
  directionPresentation,
  statusPresentation,
  type StatusGlyph as Glyph,
} from "@/lib/platform/status";
import { nodeDetailChips } from "@/lib/platform/topology-view-model";
import type { TopologyNodeModel } from "@/lib/platform/types";

/** Reiner SVG-Körper je Status-Form (16×16). Farbe trägt der Aufrufer (`color`). */
export function statusShape(glyph: Glyph, color: string) {
  switch (glyph) {
    case "filled":
      // Verbunden: gefüllter Kreis.
      return <circle cx="8" cy="8" r="6" fill={color} />;
    case "warning":
      // Gestört: gefülltes Dreieck (abgesetzte Form) + neutraler Ausrufungs-Strich.
      return (
        <>
          <path d="M8 2 L15 14 L1 14 Z" fill={color} />
          <rect x="7.25" y="6" width="1.5" height="4" rx="0.5" fill="var(--color-surface-canvas)" />
          <rect x="7.25" y="11" width="1.5" height="1.5" rx="0.5" fill="var(--color-surface-canvas)" />
        </>
      );
    case "hollow":
      // Inaktiv: offener Kreis.
      return <circle cx="8" cy="8" r="6" fill="none" stroke={color} strokeWidth="2" />;
    case "question":
      // Unbekannt: offener Kreis + Fragezeichen — ehrlich offen, nie grün.
      return (
        <>
          <circle cx="8" cy="8" r="6" fill="none" stroke={color} strokeWidth="1.5" />
          <text
            x="8"
            y="11.5"
            textAnchor="middle"
            fontSize="9"
            fontWeight="700"
            fill={color}
          >
            ?
          </text>
        </>
      );
  }
}

export interface StatusGlyphProps {
  status: string;
  className?: string;
}

/** Mehrkanaliger Status-Glyph (Form + Token-Farbe). aria-hidden — das Wort trägt. */
export function StatusGlyph({ status, className }: StatusGlyphProps) {
  const p = statusPresentation(status);
  const color = `var(--color-${p.colorToken})`;
  return (
    <svg
      viewBox="0 0 16 16"
      aria-hidden="true"
      focusable="false"
      className={cx("h-4 w-4 shrink-0", className)}
      data-status={p.status}
    >
      {statusShape(p.glyph, color)}
    </svg>
  );
}

export interface DirectionArrowProps {
  direction: string;
  className?: string;
}

/** Datenrichtung als Form (currentColor, NICHT farbcodiert). aria-hidden. */
export function DirectionArrow({ direction, className }: DirectionArrowProps) {
  const arrow = directionPresentation(direction).arrow;
  return (
    <svg
      viewBox="0 0 28 12"
      aria-hidden="true"
      focusable="false"
      className={cx("h-3 w-7 shrink-0", className)}
      data-direction={arrow}
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      fill="none"
    >
      {arrow === "none" ? (
        // Keine Verbindung: gestrichelte Linie ohne Spitze.
        <line x1="3" y1="6" x2="25" y2="6" strokeDasharray="3 3" />
      ) : (
        <line x1="3" y1="6" x2="25" y2="6" />
      )}
      {(arrow === "in" || arrow === "both") && <path d="M20 2 L25 6 L20 10" />}
      {(arrow === "out" || arrow === "both") && <path d="M8 2 L3 6 L8 10" />}
    </svg>
  );
}

function formatActivity(iso: string | null): string {
  if (iso === null) {
    return "keine Aktivität gemessen";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "keine Aktivität gemessen";
  }
  const stamp = date.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
  return `zuletzt aktiv ${stamp}`;
}

export interface TopologyNodeMarkProps {
  node: TopologyNodeModel;
}

/** Eine Knoten-Karte: Status + Richtung + letzte Aktivität + kuratierte Details. */
export function TopologyNodeMark({ node }: TopologyNodeMarkProps) {
  const status = statusPresentation(node.status);
  const direction = directionPresentation(node.direction);
  const chips = nodeDetailChips(node);

  return (
    <li
      className={cx(
        "flex flex-col gap-1.5 rounded-lg border p-3",
        node.isVision
          ? "border-line-subtle border-dashed bg-surface-canvas"
          : "border-line-subtle bg-surface-raised",
      )}
      data-node-id={node.id}
      data-vision={node.isVision ? "true" : undefined}
    >
      <div className="flex items-center gap-2">
        <StatusGlyph status={node.status} />
        <span className="text-body font-medium text-fg-primary">{node.label}</span>
        {node.isVision && (
          <span className="rounded-sm border border-line-subtle px-1.5 text-caption text-fg-muted">
            [VISION] · nicht verbunden
          </span>
        )}
        {node.internal && !node.isVision && (
          <span className="rounded-sm border border-line-subtle px-1.5 text-caption text-fg-muted">
            intern
          </span>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-fg-secondary">
        <span className="inline-flex items-center gap-1.5">
          <span className="text-fg-muted">Status:</span>
          <span title={status.description}>
            {connectionStatusLabel(node.status, node.internal)}
          </span>
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="text-fg-muted">Richtung:</span>
          <DirectionArrow direction={node.direction} />
          <span title={direction.description}>{direction.label}</span>
        </span>
      </div>

      <p className="text-caption text-fg-muted">{formatActivity(node.lastActivityIso)}</p>

      {chips.length > 0 && (
        <ul className="flex flex-wrap gap-1.5">
          {chips.map((chip) => (
            <li
              key={chip}
              className="rounded-sm border border-line-subtle px-1.5 text-caption text-fg-secondary"
            >
              {chip}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}
