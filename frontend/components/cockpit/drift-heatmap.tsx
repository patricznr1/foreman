// ============================================================
//  FOREMAN Frontend — components/cockpit/drift-heatmap.tsx
//  Zweck: Das Herzstück von Sektion A (Studie §4A/§5.5) — die DriftHeatmap als
//         maßgeschneidertes, token-getriebenes SVG (KEINE Charting-/Heatmap-Lib,
//         wie B's TimeSeriesChart): Zeilen = Maschinenklassen, Spalten = Maschinen.
//         MEHRKANALIG (§5.8): Füllung = entsättigte sequenzielle Intensität
//         (heatmap-1..5, kein Regenbogen) + Schraffur = Richtung (Abweichung/Warnung,
//         farbunabhängiger Winkel) + FCSM-Buchstabe (halo-lesbar) + Position +
//         aria-Label. Severity-Farbe erscheint NICHT in der Fläche (§4A). Klick/Enter
//         → Maschinen-Detail (B). Tastatur: Roving-Tabindex über das Raster. Kipp-Puls
//         einmalig (§5.6), reduced-motion global behandelt. Sehr große Flotten:
//         markiertes WebGL-Zielbild (§5.1) — hier bespoke SVG für den realen Bestand.
//  Architektur-Einordnung: Visualisierung (Schicht 3). Liest nur abgeleiteten State.
// ============================================================
"use client";

import { type KeyboardEvent, useRef, useState } from "react";

import { StatusIndicator } from "@/components/atoms/status-indicator";
import { cx } from "@/lib/ui/cx";
import { FCSM_LETTER, MACHINE_STATUS_LABEL } from "@/lib/ui/wording";

import { type GridPos, isGridKey, moveFocus } from "@/lib/cockpit/grid-nav";
import { cellFillToken, hatchFor } from "@/lib/cockpit/palette";
import type { HeatmapCell, HeatmapMatrix, HeatmapRow } from "@/lib/cockpit/types";

import { HeatmapLegend } from "./heatmap-legend";

const LABEL_W = 150;
const CELL = 46;
const GAP = 6;
const ROW_GAP = 12;
const TOP = 8;

const HATCH_OVER_ID = "fmn-cockpit-hatch-over";
const HATCH_UNDER_ID = "fmn-cockpit-hatch-under";

export interface DriftHeatmapProps {
  matrix: HeatmapMatrix;
  /** Maschinen-IDs, deren Zelle gerade in eine Abweichung gekippt ist (einmaliger Puls). */
  kippedMachineIds?: ReadonlySet<number>;
  /** Zell-Auswahl (Querlink → Maschinen-Detail B). Ohne Handler bleibt die Zelle lesend. */
  onSelectCell?: (cell: HeatmapCell) => void;
}

function cellAria(cell: HeatmapCell, row: HeatmapRow): string {
  const alarms = cell.openAlarmCount > 0 ? `, ${cell.openAlarmCount} offene Alarme` : "";
  return `${cell.label}, Klasse ${row.label}, ${MACHINE_STATUS_LABEL[cell.status]}${alarms}`;
}

function rowAria(row: HeatmapRow): string {
  const systematic = row.systematic ? ", systematische Abweichung in der Klasse" : "";
  return `${row.label}, ${row.cells.length} Maschinen${systematic}`;
}

export function DriftHeatmap({ matrix, kippedMachineIds, onSelectCell }: DriftHeatmapProps) {
  const [active, setActive] = useState<GridPos>({ row: 0, col: 0 });
  const [focusedId, setFocusedId] = useState<number | null>(null);
  const [preview, setPreview] = useState<HeatmapCell | null>(null);
  const cellRefs = useRef(new Map<number, SVGGElement | null>());

  const rows = matrix.rows;
  if (rows.length === 0) {
    return (
      <p role="status" className="text-body text-fg-muted">
        Keine Maschinen im Geltungsbereich.
      </p>
    );
  }

  const rowLengths = rows.map((row) => row.cells.length);
  const maxCols = Math.max(1, ...rowLengths);
  const width = LABEL_W + maxCols * (CELL + GAP);
  const height = TOP + rows.length * (CELL + ROW_GAP);

  const cellAt = (pos: GridPos): HeatmapCell | undefined => rows[pos.row]?.cells[pos.col];

  const focusCell = (pos: GridPos): void => {
    const cell = cellAt(pos);
    if (cell === undefined) {
      return;
    }
    setActive(pos);
    setPreview(cell);
    cellRefs.current.get(cell.machineId)?.focus();
  };

  const handleKeyDown = (event: KeyboardEvent<SVGSVGElement>): void => {
    if (isGridKey(event.key)) {
      event.preventDefault();
      focusCell(moveFocus(rowLengths, active, event.key));
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      const cell = cellAt(active);
      if (cell !== undefined) {
        onSelectCell?.(cell);
      }
    }
  };

  const previewAssertive = (preview?.criticalCount ?? 0) > 0;

  return (
    <div className="flex flex-col gap-4">
      <svg
        role="grid"
        aria-label="Abweichungs-Heatmap — Maschinenklassen mal Maschinen"
        viewBox={`0 0 ${width} ${height}`}
        className="h-auto w-full"
        onKeyDown={handleKeyDown}
      >
        <defs>
          {/* Haloed Schraffur: ein breiter neutraler Unterstrich (surface-canvas) macht das
              Muster auch auf HELLEN Zellen sichtbar (≥3:1), der schmale Differenz-Strich traegt
              die farbsehschwaeche-sichere Richtung (Blau/Orange) auf dunklen Zellen. */}
          <pattern id={HATCH_OVER_ID} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke="var(--color-surface-canvas)" strokeWidth="3.2" />
            <line x1="0" y1="0" x2="0" y2="6" stroke="var(--color-diff-over)" strokeWidth="1.4" />
          </pattern>
          <pattern id={HATCH_UNDER_ID} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
            <line x1="0" y1="0" x2="0" y2="6" stroke="var(--color-surface-canvas)" strokeWidth="3.2" />
            <line x1="0" y1="0" x2="0" y2="6" stroke="var(--color-diff-under)" strokeWidth="1.4" />
          </pattern>
        </defs>

        {rows.map((row, r) => {
          const y = TOP + r * (CELL + ROW_GAP);
          return (
            <g key={row.machineClass ?? "__none__"} role="row" aria-label={rowAria(row)}>
              <text
                x={0}
                y={y + CELL / 2 + 5}
                fontSize="14"
                fill={row.systematic ? "var(--color-fg-primary)" : "var(--color-fg-secondary)"}
                fontWeight={row.systematic ? 600 : 400}
              >
                {row.label}
              </text>

              {row.cells.map((cell, c) => {
                const x = LABEL_W + c * (CELL + GAP);
                const hatch = hatchFor(cell.kind);
                const kipped = kippedMachineIds?.has(cell.machineId) ?? false;
                const isActive = r === active.row && c === active.col;
                return (
                  <g
                    key={cell.machineId}
                    ref={(el) => {
                      cellRefs.current.set(cell.machineId, el);
                    }}
                    role="gridcell"
                    tabIndex={isActive ? 0 : -1}
                    aria-label={cellAria(cell, row)}
                    className={cx("cursor-pointer outline-none", kipped && "state-flip")}
                    onClick={() => {
                      setActive({ row: r, col: c });
                      setPreview(cell);
                      onSelectCell?.(cell);
                    }}
                    onFocus={() => {
                      setActive({ row: r, col: c });
                      setFocusedId(cell.machineId);
                      setPreview(cell);
                    }}
                    onBlur={() => setFocusedId((prev) => (prev === cell.machineId ? null : prev))}
                    onMouseEnter={() => setPreview(cell)}
                  >
                    <title>{cellAria(cell, row)}</title>
                    <rect
                      x={x}
                      y={y}
                      width={CELL}
                      height={CELL}
                      rx={6}
                      fill={`var(--color-${cellFillToken(cell.level)})`}
                      stroke="var(--color-line-subtle)"
                      strokeWidth={1}
                    />
                    {hatch !== null ? (
                      <rect
                        x={x}
                        y={y}
                        width={CELL}
                        height={CELL}
                        rx={6}
                        fill={`url(#${hatch === "over" ? HATCH_OVER_ID : HATCH_UNDER_ID})`}
                        pointerEvents="none"
                      />
                    ) : null}
                    {cell.level > 0 ? (
                      <text
                        x={x + CELL / 2}
                        y={y + CELL / 2}
                        textAnchor="middle"
                        dominantBaseline="central"
                        fontSize="16"
                        fontWeight={600}
                        fill="var(--color-fg-primary)"
                        stroke="var(--color-surface-canvas)"
                        strokeWidth={3}
                        paintOrder="stroke"
                        pointerEvents="none"
                      >
                        {FCSM_LETTER[cell.fcsm]}
                      </text>
                    ) : null}
                    {focusedId === cell.machineId ? (
                      <>
                        {/* Fokusring im Zwischenraum gezeichnet (gegen die stabile
                            Grundflaeche, nicht die variable Zellfuellung) + neutraler
                            Halo darunter → sichtbar ueber jeder Nachbarfuellung (≥3:1). */}
                        <rect
                          x={x - 3}
                          y={y - 3}
                          width={CELL + 6}
                          height={CELL + 6}
                          rx={9}
                          fill="none"
                          stroke="var(--color-surface-canvas)"
                          strokeWidth={4}
                          pointerEvents="none"
                        />
                        <rect
                          x={x - 3}
                          y={y - 3}
                          width={CELL + 6}
                          height={CELL + 6}
                          rx={9}
                          fill="none"
                          stroke="var(--color-focus-ring)"
                          strokeWidth={2}
                          pointerEvents="none"
                        />
                      </>
                    ) : null}
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>

      {/* Live-Region der Mini-Vorschau: bei offenen kritischen Alarmen assertiv
          (ISA-18.2/§5.8 — kritisch verlangt sofortige Aufmerksamkeit), sonst hoeflich. */}
      <div
        role={previewAssertive ? "alert" : "status"}
        aria-live={previewAssertive ? "assertive" : "polite"}
        className="min-h-9"
      >
        {preview ? (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-body text-fg-secondary">
            <span className="text-fg-primary">{preview.label}</span>
            <span aria-hidden="true">·</span>
            <span>{preview.machineClass ?? "Ohne Klasse"}</span>
            <span aria-hidden="true">·</span>
            <StatusIndicator status={preview.fcsm} label={MACHINE_STATUS_LABEL[preview.status]} size="s" />
            {preview.openAlarmCount > 0 ? (
              <>
                <span aria-hidden="true">·</span>
                <span className="tabular-nums">{preview.openAlarmCount} offene Alarme</span>
              </>
            ) : null}
          </div>
        ) : (
          <p className="text-caption text-fg-muted">Zelle ansteuern oder antippen für Details.</p>
        )}
      </div>

      <HeatmapLegend />
    </div>
  );
}
