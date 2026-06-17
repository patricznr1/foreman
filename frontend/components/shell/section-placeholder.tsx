// ============================================================
//  FOREMAN Frontend — components/shell/section-placeholder.tsx
//  Zweck: Ehrlicher Platzhalter für Sektionen, die als eigener Prompt folgen
//         (C/E zuerst, dann B/H/J, dann A/F/G/I). Markiert das Fundament-Ende,
//         kein „kaputter" Screen. Hallensprache.
//  Architektur-Einordnung: Sicht-Platzhalter (Schicht 3).
// ============================================================
export function SectionPlaceholder({ title, note }: { title: string; note: string }) {
  return (
    <section aria-label={title} className="flex flex-col gap-3">
      <h1 className="text-h1 text-fg-primary">{title}</h1>
      <p className="max-w-prose text-body text-fg-secondary">{note}</p>
    </section>
  );
}
