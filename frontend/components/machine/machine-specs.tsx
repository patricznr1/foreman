// ============================================================
//  FOREMAN Frontend — components/machine/machine-specs.tsx
//  Zweck: Stammdaten/Spezifikation einer Maschine lesbar dargestellt (Pull): Identität,
//         Komponenten, Datenpunkte. Keine PII (Stammdaten sind sach-/anlagenbezogen,
//         external_id ist anonymisiert).
//  Architektur-Einordnung: Sicht-Baustein (Schicht 3, client).
// ============================================================
import type { ComponentRead, DataPointRead, MachineRead } from "@/lib/api/contracts";

export interface MachineSpecsProps {
  machine: MachineRead;
  components: ComponentRead[];
  dataPoints: DataPointRead[];
}

export function MachineSpecs({ machine, components, dataPoints }: MachineSpecsProps) {
  const rows: ReadonlyArray<readonly [string, string | null]> = [
    ["Klasse", machine.machine_class],
    ["Hersteller", machine.manufacturer],
    ["Standort", machine.location],
    ["Linie", machine.line_id !== null ? `Linie ${machine.line_id}` : null],
    ["Kennung", machine.external_id],
  ];

  return (
    <section
      aria-label="Stammdaten"
      className="flex flex-col gap-4 rounded-lg border border-line-subtle bg-surface-raised p-4"
    >
      <h2 className="text-h2 text-fg-primary">Stammdaten</h2>

      <dl className="grid grid-cols-1 gap-x-6 gap-y-2 sm:grid-cols-2">
        {rows.map(([label, value]) =>
          value !== null ? (
            <div key={label} className="flex justify-between gap-3 border-b border-line-subtle py-1">
              <dt className="text-caption text-fg-muted">{label}</dt>
              <dd className="text-body text-fg-primary">{value}</dd>
            </div>
          ) : null,
        )}
      </dl>

      <div className="flex flex-col gap-1">
        <h3 className="text-caption text-fg-muted">Komponenten</h3>
        {components.length > 0 ? (
          <ul className="flex flex-col gap-1">
            {components.map((component) => (
              <li key={component.id} className="text-body text-fg-secondary">
                {component.label}
                {component.component_type ? ` (${component.component_type})` : ""}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-body text-fg-muted">Keine Komponenten hinterlegt.</p>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <h3 className="text-caption text-fg-muted">Datenpunkte</h3>
        {dataPoints.length > 0 ? (
          <ul className="flex flex-col gap-1">
            {dataPoints.map((dataPoint) => (
              <li key={dataPoint.id} className="text-body text-fg-secondary tabular-nums">
                {dataPoint.name}
                {dataPoint.unit ? ` · ${dataPoint.unit}` : ""}
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-body text-fg-muted">Keine Datenpunkte hinterlegt.</p>
        )}
      </div>
    </section>
  );
}
