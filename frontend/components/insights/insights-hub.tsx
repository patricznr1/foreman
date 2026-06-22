// ============================================================
//  FOREMAN Frontend — components/insights/insights-hub.tsx
//  Zweck: Das Erkenntnisse-Dach (Studie §3.3): die On-Demand-Reasoner D/E/F/G
//         unter einer Sekundärnavigation, weil sie dasselbe Interaktionsmuster
//         teilen (Trigger → Herkunft → Vorbehalt). E (Ausfallvorhersage) ist live,
//         D/F/G folgen als eigene Prompts — GRACEFUL als „folgt" markiert, kein
//         toter Link.
//  Architektur-Einordnung: Sektions-Hub (Schicht 2, server).
// ============================================================
import Link from "next/link";

interface ReasonerEntry {
  id: string;
  title: string;
  blurb: string;
  /** Existierende Route oder null (folgt → graceful). */
  href: string | null;
}

const ENTRIES: ReasonerEntry[] = [
  {
    id: "D",
    title: "Ereignisketten",
    blurb: "Vorfälle über Zeit und Anlagen zu einer belegten Kette rekonstruieren.",
    href: "/insights/chains",
  },
  {
    id: "E",
    title: "Ausfallvorhersage & Empfehlung",
    blurb:
      "Wahrscheinlichkeit, Einflussfaktoren und eine Werker-Empfehlung — mit untrennbarem Simulations-Vorbehalt.",
    href: "/insights/prediction",
  },
  {
    id: "F",
    title: "Wartungszyklen",
    blurb: "Welche Wartung welches Risiko senkt — als Vorschlag, nie als Schaltung.",
    href: null,
  },
  {
    id: "G",
    title: "Belastungs-Simulation",
    blurb: "Folgen einer Lasteinstellung durchspielen — beeinflusst die reale Anlage nicht.",
    href: null,
  },
];

export function InsightsHub() {
  return (
    <section className="flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <h1 className="text-h1 text-fg-primary">Erkenntnisse</h1>
        <p className="text-body text-fg-secondary">
          On-Demand-Reasoner — jede erzeugte Erkenntnis durchläuft denselben Dreischritt:
          Trigger → Herkunft → Vorbehalt.
        </p>
      </div>
      <ul className="grid gap-3 sm:grid-cols-2">
        {ENTRIES.map((entry) => {
          const inner = (
            <>
              <div className="flex items-center justify-between gap-2">
                <span className="text-body-l font-medium text-fg-primary">{entry.title}</span>
                <span className="text-caption text-fg-muted">{entry.href ? "live" : "folgt"}</span>
              </div>
              <p className="text-caption text-fg-secondary">{entry.blurb}</p>
            </>
          );
          return (
            <li key={entry.id}>
              {entry.href ? (
                <Link
                  href={entry.href}
                  className="flex h-full flex-col gap-2 rounded-lg border border-line-strong bg-surface-raised p-4 transition-colors duration-[var(--motion-base)] motion-reduce:transition-none hover:bg-surface-overlay focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
                >
                  {inner}
                </Link>
              ) : (
                <div
                  aria-disabled="true"
                  className="flex h-full flex-col gap-2 rounded-lg border border-line-subtle bg-surface-raised p-4 opacity-70"
                >
                  {inner}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
