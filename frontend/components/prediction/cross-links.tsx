// ============================================================
//  FOREMAN Frontend — components/prediction/cross-links.tsx
//  Zweck: Kontextnavigation der Sektion E (Studie §4E „Verbindungen"). Eine
//         Erkenntnis mündet in andere Sichten: belegender Sensorverlauf (B),
//         auslösender Alarm (C), ähnliche Vorfälle (H), risikosenkende Wartung (F).
//         GRACEFUL: existierende Sektionen werden verlinkt, noch nicht gebaute
//         Ziele (F-Brücke, B-Sensorbeleg-Anker) sind sichtbar als „folgt" markiert,
//         nie ein toter Link.
//  Architektur-Einordnung: Navigations-Molekül (Schicht 2). Rein präsentational.
// ============================================================
import Link from "next/link";

interface CrossTarget {
  label: string;
  /** Existierende Route oder null (Ziel folgt → graceful, kein toter Link). */
  href: string | null;
}

export function PredictionCrossLinks({ machineId }: { machineId: number }) {
  // Hinweis: die Routen existieren als Sektionen; der maschinen-genaue Anker (z. B.
  // der belegende Sensorverlauf) folgt mit Sektion B — darum bewusst die Sektion,
  // nicht ein vorgetäuschter Deep-Link.
  const targets: CrossTarget[] = [
    { label: "Belegender Sensorverlauf (Maschinen)", href: "/machines" },
    { label: "Auslösender Alarm", href: "/alarms" },
    { label: "Ähnliche Vorfälle (Gedächtnis)", href: "/memory" },
    { label: "Risikosenkende Wartung", href: null },
  ];

  return (
    <nav aria-label={`Weiter im Kontext zu Maschine ${machineId}`} className="flex flex-col gap-1">
      <span className="text-caption font-semibold uppercase tracking-wide text-fg-muted">
        Weiter im Kontext
      </span>
      <ul className="flex flex-wrap gap-x-4 gap-y-1">
        {targets.map((t) =>
          t.href ? (
            <li key={t.label}>
              <Link
                href={t.href}
                className="text-caption text-fg-secondary underline underline-offset-2 hover:text-fg-primary focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
              >
                {t.label}
              </Link>
            </li>
          ) : (
            <li key={t.label}>
              <span className="text-caption text-fg-muted" aria-disabled="true">
                {t.label} (folgt)
              </span>
            </li>
          ),
        )}
      </ul>
    </nav>
  );
}
