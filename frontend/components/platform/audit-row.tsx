// ============================================================
//  FOREMAN Frontend — components/platform/audit-row.tsx
//  Zweck: Eine unveränderlich-lesende Zeile des Audit-Trails (Studie §4I, §22.1).
//         IDs/Token in Monospace (Nachvollziehbarkeit, §5.3); der Akteur erscheint
//         NUR als pseudonymer '#hex6'-Handle (nie Klartext) plus Rolle. KEINE
//         Aktion/Mutation — der Audit protokolliert, löst nichts aus. detail-JSONB
//         defensiv als flache Schlüssel/Wert-Chips (React escaped den Text).
//  Architektur-Einordnung: Tabellen-Zeile (Schicht 2, präsentational).
// ============================================================
import type { AuditRowModel } from "@/lib/platform/types";

function formatStamp(iso: string | null): string {
  if (iso === null) {
    return "—";
  }
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return date.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

const CELL = "px-3 py-2 align-top text-caption text-fg-secondary";

export interface AuditRowProps {
  row: AuditRowModel;
}

export function AuditRow({ row }: AuditRowProps) {
  return (
    <tr className="border-t border-line-subtle" data-audit-id={row.id}>
      <td className={`${CELL} whitespace-nowrap font-mono`}>{formatStamp(row.occurredAtIso)}</td>
      <td className={CELL}>
        <span className="font-mono text-fg-primary">{row.actorHandle ?? "—"}</span>
        {row.actorRole !== null && (
          <span className="ml-1.5 text-fg-muted">({row.actorRole})</span>
        )}
      </td>
      <td className={CELL}>{row.actionType ?? "—"}</td>
      <td className={CELL}>
        <span>{row.targetKind ?? "—"}</span>
        {row.targetId !== null && <span className="ml-1.5 font-mono text-fg-muted">#{row.targetId}</span>}
        {row.machineId !== null && (
          <span className="ml-1.5 text-fg-muted">
            · Maschine <span className="font-mono">#{row.machineId}</span>
          </span>
        )}
      </td>
      <td className={CELL}>{row.origin ?? "—"}</td>
      <td className={CELL}>
        {row.detailPairs.length === 0 ? (
          <span className="text-fg-muted">—</span>
        ) : (
          <ul className="flex flex-col gap-0.5">
            {row.detailPairs.map(([key, value]) => (
              <li key={key}>
                <span className="text-fg-muted">{key}:</span>{" "}
                <span className="font-mono break-all">{value}</span>
              </li>
            ))}
          </ul>
        )}
      </td>
    </tr>
  );
}
