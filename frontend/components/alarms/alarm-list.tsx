// ============================================================
//  FOREMAN Frontend — components/alarms/alarm-list.tsx
//  Zweck: Virtualisierte, prioritätsgestaffelte Alarmliste (Studie §4C/§5.1). Nur
//         Sichtbares im DOM — die Fenster-Mathematik liegt rein in lib/alarms/window
//         (getestet). Live-Insert ohne Sprung: neue Zeilen erscheinen an ihrer
//         Sortier-Position (Einblend-Puls über die Zeile), die Scroll-Position wird
//         NIE zurückgesetzt. Live-Regionen je Dringlichkeit (höflich/assertiv, §5.8).
//         Uniforme Slot-Höhe (Kopf/Zeile/Bündel) → exakte Virtualisierung.
//  Architektur-Einordnung: Sicht-Komponente (Schicht 3, client).
// ============================================================
"use client";

import { useLayoutEffect, useRef, useState } from "react";
import { windowRange } from "@/lib/alarms/window";
import type { VisualRow } from "@/lib/alarms/types";
import { cx } from "@/lib/ui/cx";
import { AlarmBundleRow } from "./alarm-bundle-row";
import { AlarmRow } from "./alarm-row";
import { PRIORITY_DOT } from "./alarm-styles";

/** Uniforme Slot-Höhe (px): Handschuh-Zeile + Platz fürs ≥64-px-Quittier-Ziel. */
export const ROW_HEIGHT = 80;

export interface AlarmListProps {
  rows: readonly VisualRow[];
  canAcknowledge: boolean;
  online: boolean;
  onAcknowledged: () => void;
  onShelve: (alarmId: number) => void;
  onUnshelve: (alarmId: number) => void;
  expandedBundles: ReadonlySet<string>;
  onToggleBundle: (key: string) => void;
  /** Höfliche Ansage (mittel/niedrig) für Screenreader. */
  politeMessage?: string;
  /** Assertive Ansage (kritisch/hoch). */
  assertiveMessage?: string;
  /** Test-/Override-Hooks: feste Viewport-Höhe und Scroll-Position. */
  viewportHeight?: number;
  scrollTop?: number;
  rowHeight?: number;
}

export function AlarmList({
  rows,
  canAcknowledge,
  online,
  onAcknowledged,
  onShelve,
  onUnshelve,
  expandedBundles,
  onToggleBundle,
  politeMessage,
  assertiveMessage,
  viewportHeight,
  scrollTop,
  rowHeight = ROW_HEIGHT,
}: AlarmListProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [measuredHeight, setMeasuredHeight] = useState(600);
  const [measuredScroll, setMeasuredScroll] = useState(0);
  const prevRowsRef = useRef<readonly VisualRow[]>(rows);

  // Viewport-Höhe messen (ResizeObserver) — außer im Test-Override.
  useLayoutEffect(() => {
    if (viewportHeight !== undefined) {
      return;
    }
    const element = containerRef.current;
    if (element === null) {
      return;
    }
    const update = () => setMeasuredHeight(element.clientHeight || 600);
    update();
    const observer = new ResizeObserver(update);
    observer.observe(element);
    return () => observer.disconnect();
  }, [viewportHeight]);

  // Scroll-Anchoring (Studie: „Live-Push ohne Listen-Sprung"): wird OBERHALB der
  // Leseposition etwas eingefügt, würde der Inhalt unter dem Nutzer wegrutschen.
  // Wir halten die Anker-Zeile an ihrer Bildschirmposition — AUSSER am Listenanfang,
  // wo neue (oben einsortierte) Alarme bewusst sichtbar erscheinen sollen.
  useLayoutEffect(() => {
    const prev = prevRowsRef.current;
    prevRowsRef.current = rows;
    if (scrollTop !== undefined) {
      return; // Test-Override steuert die Scroll-Position
    }
    const element = containerRef.current;
    if (element === null || prev === rows || prev.length === 0) {
      return;
    }
    const currentScroll = element.scrollTop;
    if (currentScroll < rowHeight) {
      return; // am Anfang: neue Alarme oben sichtbar lassen
    }
    const firstIndex = Math.floor(currentScroll / rowHeight);
    const anchor = prev[firstIndex];
    if (!anchor) {
      return;
    }
    const newIndex = rows.findIndex((row) => row.id === anchor.id);
    if (newIndex < 0 || newIndex === firstIndex) {
      return;
    }
    const offsetWithinRow = currentScroll - firstIndex * rowHeight;
    const corrected = newIndex * rowHeight + offsetWithinRow;
    element.scrollTop = corrected;
    setMeasuredScroll(corrected);
  }, [rows, rowHeight, scrollTop]);

  const effectiveHeight = viewportHeight ?? measuredHeight;
  const effectiveScroll = scrollTop ?? measuredScroll;

  const range = windowRange({
    scrollTop: effectiveScroll,
    viewportHeight: effectiveHeight,
    rowHeight,
    count: rows.length,
  });
  const visible = rows.slice(range.startIndex, range.endIndex);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Live-Regionen je Dringlichkeit (§5.8) — visuell versteckt. */}
      <div aria-live="assertive" className="sr-only">
        {assertiveMessage}
      </div>
      <div aria-live="polite" className="sr-only">
        {politeMessage}
      </div>

      <div
        ref={containerRef}
        role="region"
        aria-label="Alarmliste, nach Priorität gestaffelt"
        tabIndex={0}
        onScroll={(event) => {
          if (scrollTop === undefined) {
            setMeasuredScroll((event.target as HTMLDivElement).scrollTop);
          }
        }}
        className="min-h-0 flex-1 overflow-y-auto"
      >
        <div style={{ height: range.totalHeight, position: "relative" }}>
          <div style={{ transform: `translateY(${range.paddingTop}px)` }}>
            {visible.map((item) => (
              <div key={item.id} style={{ height: rowHeight }} className="border-b border-line-subtle">
                {item.kind === "header" ? (
                  <h3 className="flex h-full items-center gap-2 bg-surface-canvas px-3 text-caption font-semibold tracking-wide text-fg-secondary uppercase">
                    {item.priority ? (
                      <span
                        aria-hidden="true"
                        className={cx("h-2.5 w-2.5 rounded-full", PRIORITY_DOT[item.priority])}
                      />
                    ) : null}
                    {item.label}
                    <span className="text-fg-muted">· {item.count}</span>
                  </h3>
                ) : item.kind === "bundle" ? (
                  <AlarmBundleRow
                    bundle={item.bundle}
                    expanded={expandedBundles.has(item.bundle.key)}
                    onToggle={onToggleBundle}
                  />
                ) : (
                  <AlarmRow
                    vm={item.row}
                    canAcknowledge={canAcknowledge}
                    online={online}
                    onAcknowledged={onAcknowledged}
                    onShelve={onShelve}
                    onUnshelve={onUnshelve}
                  />
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
