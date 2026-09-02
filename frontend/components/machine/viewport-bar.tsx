// ============================================================
//  FOREMAN Frontend — components/machine/viewport-bar.tsx
//  Zweck: Die Bedienleiste des Sensortrend-Ausschnitts (Studie §4B/§5.4). Trägt die
//         Schnellwahl (Schicht/Tag/Woche), fünf Knöpfe (−, +, Älter, Neuer, Jetzt),
//         die sichtbaren Statuszeilen und die EINE Ansage der ganzen Sektion.
//         Rein darstellend: kein eigener Zustand, keine Timer, kein Layout-Messen.
//         Alles Gezeigte ist aus `viewport` + `nowMs` ABGELEITET (isAtFloor,
//         isAtWall, matchPreset) — gegen den Fall, dass ein Bedienelement etwas
//         anderes behauptet als der Ausschnitt zeigt (gedrückter „Tag“-Knopf über
//         einem 2-Stunden-Bild, freier Plus-Knopf am Auflösungsboden).
//  Architektur-Einordnung: Steuerung (Schicht 3, client). Tastatur/Fokus, ≥56 px.
// ============================================================
"use client";

import { BUCKET_MS, type TimeWindowId } from "@/lib/machine/time-window";
import {
  MAX_SPAN_MS,
  describeSpan,
  isAtFloor,
  isAtWall,
  matchPreset,
  resolveViewport,
  type TrendViewport,
} from "@/lib/machine/viewport";

import { TimeWindowPicker } from "./time-window-picker";

/** Ein Druck auf „Älter“/„Neuer“ schiebt um ein Viertel der sichtbaren Spanne. */
const PAN_STEP_FRACTION = 0.25;

/** Ein Druck auf „+“ halbiert die Spanne, „−“ verdoppelt sie (Faktor > 1 = hinein). */
const ZOOM_STEP_FACTOR = 2;

/**
 * Die Knöpfe zoomen auf die MITTE des Bildes. Ein Zeigergerät hat einen Anker
 * (Finger, Mauszeiger), ein Knopf hat keinen — die Mitte ist die einzige Stelle,
 * die nicht willkürlich ist.
 */
const CENTER_ANCHOR = 0.5;

/** Gemeinsame Knopfform der Leiste: `touch-target` an EINER Stelle, nicht fünfmal. */
const BUTTON_CLASS =
  "touch-target rounded-md border border-line-subtle px-3 text-body text-fg-primary disabled:opacity-60";

export interface ViewportBarProps {
  /** Der Ausschnitt, den die Leiste beschreibt und bedient. */
  viewport: TrendViewport;
  /**
   * Zeitanker. Fehlt er, gilt `Date.now()`. Als Requisite einspritzbar, damit die
   * Grenzfälle (Boden, Wand, Abstand zum Live-Rand) ohne Uhr prüfbar sind —
   * Bauform wie `viewportHeight` in components/alarms/alarm-list.tsx.
   */
  nowMs?: number;
  /**
   * Der Text der Live-Region. Er wird bewusst von AUSSEN gesetzt und nur beim
   * Gestenende und bei Knopfbefehlen erneuert; eine Ansage, die bei jedem
   * Ausschnittswechsel feuert, ist für Screenreader schlimmer als gar keine.
   */
  announcement: string;
  onQuickPick: (id: TimeWindowId) => void;
  /** `factor` > 1 zoomt hinein (Spanne wird kleiner), `anchorFraction` 0..1. */
  onZoom: (factor: number, anchorFraction: number) => void;
  /** Positiv = Richtung Live-Rand (neuer), negativ = in die Vergangenheit. */
  onPan: (fraction: number) => void;
  onNow: () => void;
}

interface BarButtonProps {
  label: string;
  ariaLabel: string;
  disabled: boolean;
  onClick: () => void;
}

function BarButton({ label, ariaLabel, disabled, onClick }: BarButtonProps) {
  return (
    <button type="button" aria-label={ariaLabel} disabled={disabled} onClick={onClick} className={BUTTON_CLASS}>
      {label}
    </button>
  );
}

export function ViewportBar({
  viewport,
  nowMs,
  announcement,
  onQuickPick,
  onZoom,
  onPan,
  onNow,
}: ViewportBarProps) {
  const now = nowMs ?? Date.now();
  const { startMs, endMs } = resolveViewport(viewport, now);
  // Beide Größen laufen als Text ausschließlich durch `describeSpan`, das negative
  // Eingaben auf 0 rundet. Ein von außen gereichter unsinniger Ausschnitt (Spanne
  // ≤ 0, rechter Rand hinter dem Jetzt) ergibt deshalb „0 Minuten“ statt einer
  // negativen Dauer — eine eigene Klemme hier wäre eine zweite, stille Fassung
  // derselben Regel. Ein Test hält den Ausgang fest.
  const spanMs = endMs - startMs;
  const behindMs = now - endMs;

  const following = viewport.mode === "follow";
  const atFloor = isAtFloor(viewport, now);
  const atWall = isAtWall(viewport, now);
  // Am weitesten Ausschnitt gibt es nichts mehr herauszuzoomen. Dieser Zustand
  // fällt mit der Wand zusammen (eine Spanne von MAX_SPAN_MS reicht bei einem
  // rechten Rand ≤ jetzt zwangsläufig bis an sie heran), deshalb steht der Grund
  // dafür schon in der Wandzeile — ein Test fordert dieses Zusammenfallen ein.
  const atCeiling = spanMs >= MAX_SPAN_MS;

  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        {/* Der gedrückte Zustand wird ZURÜCKGELESEN, nicht daneben gespeichert. */}
        <TimeWindowPicker value={matchPreset(viewport, now)} onChange={onQuickPick} />

        <div role="group" aria-label="Ausschnitt bedienen" className="inline-flex flex-wrap gap-1">
          <BarButton
            label="−"
            ariaLabel="Herauszoomen"
            disabled={atCeiling}
            onClick={() => onZoom(1 / ZOOM_STEP_FACTOR, CENTER_ANCHOR)}
          />
          <BarButton
            label="+"
            ariaLabel="Hineinzoomen"
            disabled={atFloor}
            onClick={() => onZoom(ZOOM_STEP_FACTOR, CENTER_ANCHOR)}
          />
          <BarButton
            label="Älter"
            ariaLabel="Älter: Ausschnitt in die Vergangenheit schieben"
            disabled={atWall}
            onClick={() => onPan(-PAN_STEP_FRACTION)}
          />
          <BarButton
            label="Neuer"
            ariaLabel="Neuer: Ausschnitt Richtung Live-Rand schieben"
            disabled={following}
            onClick={() => onPan(PAN_STEP_FRACTION)}
          />
          {/* „Jetzt“ ist der Ausweg aus dem festen Zustand — es gibt ihn genau dort.
              Sein Text ist FEST: ein Label, das mit dem Abstand mitwächst, ließe das
              Ziel unter der greifenden (behandschuhten) Hand wandern. Der Abstand
              zählt deshalb in der Statuszeile daneben hoch, nicht im Knopf. */}
          {following ? null : (
            <BarButton label="Jetzt" ariaLabel="Jetzt: zurück zum Live-Rand" disabled={false} onClick={onNow} />
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-caption text-fg-muted">
        <span>Ausschnitt: {describeSpan(spanMs)}</span>
        <span>
          {following ? "folgt dem Live-Rand" : `steht fest · ${describeSpan(behindMs)} hinter dem Live-Rand`}
        </span>
        {/* Ein grauer Knopf ohne Begründung ist eine Sackgasse: zu jeder Sperre
            steht der Grund sichtbar daneben. Die Zahlen stehen nicht hier, sondern
            kommen aus BUCKET_MS bzw. MAX_SPAN_MS — eine abgetippte „1 Minute“
            liefe der Bucket-Breite davon, sobald jemand sie anfasst. */}
        {atFloor ? <span>Feinste Auflösung: {describeSpan(BUCKET_MS)} je Punkt</span> : null}
        {atWall ? <span>Älter als {describeSpan(MAX_SPAN_MS)}: kein Verlauf über diese Ansicht</span> : null}
      </div>

      {/* GENAU EINE Live-Region für die ganze Sektion. Nicht je Panel und nicht je
          Statuszeile: drei gestapelte Sensoren kündigten denselben Vorgang sonst
          dreimal an, und eine Vorlesehilfe wird davon unbenutzbar. Sie steht auch
          leer im Baum — eine Region, die erst mit ihrem Text entsteht, wird von
          Screenreadern nicht zuverlässig vorgelesen. */}
      <p role="status" aria-live="polite" className="sr-only">
        {announcement}
      </p>
    </div>
  );
}
