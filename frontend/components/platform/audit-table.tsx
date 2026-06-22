// ============================================================
//  FOREMAN Frontend — components/platform/audit-table.tsx
//  Zweck: Die chronologische, unveränderlich-lesende Audit-Tabelle (Studie §4I,
//         §22.1) — jüngste zuerst (Reihenfolge kommt vom Backend, hier NICHT
//         umsortiert). Semantische Tabelle mit caption + scope-Headern. KEINE
//         Edit-/Quittier-/Aktor-Spalte (der Audit löst nichts aus).
//  Architektur-Einordnung: Tabelle (Schicht 2, präsentational).
// ============================================================
import type { AuditRowModel } from "@/lib/platform/types";
import { AuditRow } from "./audit-row";

const HEAD = "px-3 py-2 text-left text-caption font-semibold text-fg-secondary";

export interface AuditTableProps {
  rows: AuditRowModel[];
}

export function AuditTable({ rows }: AuditTableProps) {
  return (
    <div className="overflow-x-auto rounded-lg border border-line-subtle">
      <table className="w-full border-collapse text-left">
        <caption className="sr-only">
          Audit-Trail: abgerufene Erkenntnisse und Human-in-the-Loop-Entscheidungen, jüngste zuerst.
          Nur lesend.
        </caption>
        <thead className="bg-surface-overlay">
          <tr>
            <th scope="col" className={HEAD}>
              Zeit
            </th>
            <th scope="col" className={HEAD}>
              Akteur
            </th>
            <th scope="col" className={HEAD}>
              Aktion
            </th>
            <th scope="col" className={HEAD}>
              Ziel
            </th>
            <th scope="col" className={HEAD}>
              Herkunft
            </th>
            <th scope="col" className={HEAD}>
              Detail
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <AuditRow key={row.id} row={row} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
