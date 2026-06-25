// ============================================================
//  FOREMAN Frontend — components/atoms/provenance-stamp.tsx
//  Zweck: Der Herkunftsstempel (§5.5) — Stand + Datenbasis an jeder Erkenntnis;
//         zugleich der AI-Act-Transparenzanker (KI-erzeugt) und der Stand-Stempel
//         für gecachte/degradierte Live-Sichten. Hallensprache, ruhig, kein Alarm.
//         Der Vorbehalt nutzt die eigene Signalfarbe (note-caveat), NICHT Rot.
//  Architektur-Einordnung: Atom (Schicht 2). Rein präsentational.
// ============================================================
import { cx } from "@/lib/ui/cx";

// "live"   = Live-Strom (WS offen UND Eingangs-Stream tickt) — grüner Punkt.
// "cached" = geladen, aber WS-Verbindung weg (eingefrorener Stand).
// "history"= WS verbunden, aber kein laufender Eingangs-Stream → nur Historie
//            („Verlauf", kein grüner Live-Punkt). Ehrlich: kein Live-Etikett ohne Strom.
export type Freshness = "live" | "cached" | "history";

export interface ProvenanceStampProps {
  freshness: Freshness;
  /** Zeitpunkt des Stands (Stand-Stempel). */
  stampedAt?: Date | string | null;
  /** AI-Act-Transparenz: als KI-erzeugt kennzeichnen. */
  aiGenerated?: boolean;
  /** Simulations-/Unsicherheits-Vorbehalt sichtbar machen (ruhige Signalfarbe). */
  caveat?: boolean;
  className?: string;
}

function formatStamp(value: Date | string | null | undefined): string | null {
  if (value == null) {
    return null;
  }
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function ProvenanceStamp({
  freshness,
  stampedAt,
  aiGenerated = false,
  caveat = false,
  className,
}: ProvenanceStampProps) {
  const time = formatStamp(stampedAt);
  const isLive = freshness === "live";
  const freshnessText = isLive ? "Live" : freshness === "history" ? "Verlauf" : "Gecacht";
  const timeText = time ? (isLive ? ` · aktualisiert ${time}` : ` · Stand ${time}`) : "";

  return (
    <span
      className={cx(
        "inline-flex items-center gap-2 text-caption",
        caveat ? "text-note-caveat" : "text-fg-muted",
        className,
      )}
      data-freshness={freshness}
    >
      <span
        aria-hidden="true"
        className={cx("inline-block h-2 w-2 rounded-full", isLive ? "bg-state-ok" : "bg-fg-muted")}
      />
      <span>
        {freshnessText}
        {timeText}
      </span>
      {aiGenerated ? <span className="font-mono uppercase tracking-wide">KI-erzeugt</span> : null}
    </span>
  );
}
