// ============================================================
//  FOREMAN Frontend — components/capture/voice-capture-placeholder.tsx
//  Zweck: Die Spracheingabe als markiertes ZIELBILD ([VISION], Studie §4J) — NICHT
//         als funktionsloses Fake-Mikrofon. Bewusst NICHT interaktiv (kein <button>,
//         kein onClick, kein Aufnahme-Versprechen): ein ruhiger, gestrichelt
//         abgesetzter Hinweis, dass Diktieren mit editierbarem Transkript folgt.
//         Die Whisper-Transkription ist nicht gebaut; nichts wird vorgetäuscht.
//  Architektur-Einordnung: Sicht-Komponente (Schicht 3). Rein präsentational.
// ============================================================
import { cx } from "@/lib/ui/cx";

/** Mikrofon-Glyph (rein dekorativ, aria-hidden). */
function MicGlyph() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className="h-5 w-5 shrink-0"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="9" y="3" width="6" height="11" rx="3" />
      <path d="M5 11a7 7 0 0 0 14 0" />
      <path d="M12 18v3" />
    </svg>
  );
}

export function VoiceCapturePlaceholder({ prominent = false }: { prominent?: boolean }) {
  return (
    <div
      // Bewusst kein button/role — nicht bedienbar, nur ein gekennzeichnetes Zielbild.
      className={cx(
        "flex items-center gap-3 rounded-lg border border-dashed border-line-strong",
        "bg-surface-raised px-4 py-3 text-fg-muted",
        prominent ? "text-body" : "text-caption",
      )}
    >
      <span className="text-fg-muted">
        <MicGlyph />
      </span>
      <span>
        <span className="font-mono uppercase tracking-wide text-fg-secondary">In Vorbereitung</span>
        {" — "}
        Spracheingabe: diktieren statt tippen, mit editierbarem Text zum Bestätigen. Bis dahin per
        Tastatur erfassen.
      </span>
    </div>
  );
}
