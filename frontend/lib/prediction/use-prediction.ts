// ============================================================
//  FOREMAN Frontend — lib/prediction/use-prediction.ts
//  Zweck: On-Demand-Anbindung der Sektion E über den BFF-Proxy. Trigger =
//         POST /predict → POST .../recommendation (der Dreischritt der Studie §3.2);
//         Autoload = jüngste VOLLSTÄNDIGE Erkenntnis (Vorhersage + ihre Empfehlung)
//         als Snapshot. Liefert NIE eine nackte Vorhersage ohne Empfehlung — fehlt
//         die Empfehlung, bleibt der Ruhezustand. Die Komponente kennt den Transport nie.
//  Architektur-Einordnung: State-Anbindung (Schicht 1 ↔ React).
// ============================================================
"use client";

import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import type { FailurePredictionRead, WorkerRecommendationRead } from "@/lib/api/contracts";
import { type OnDemandPhase, initialPhase, onDemandReducer } from "@/lib/ondemand/machine";
import type { PredictionPair } from "./types";
import { latestPredictionEndpoint, predictEndpoint, recommendationEndpoint } from "./url";

export interface UsePredictionOptions {
  machineId: number;
  /** Beim Mount die jüngste gespeicherte Erkenntnis laden (Werker/Techniker). */
  autoload?: boolean;
}

export interface UsePredictionResult {
  phase: OnDemandPhase<PredictionPair>;
  /** Fordert frisch an: Vorhersage + Empfehlung (nur erlaubte Rollen rufen das auf). */
  trigger: () => void;
  busy: boolean;
  /**
   * Laufender Versuch der Empfehlung, 1 bis `MAX_VERSUCHE`.
   *
   * Ein Wert über 1 heißt: Der vorige Versuch wurde vom Guard verworfen und es
   * läuft weiter. Die Anzeige soll das SAGEN — sonst steht der Wartende vor einer
   * Wartemeldung, die viermal so lange dauert wie sonst, ohne zu wissen, warum.
   */
  versuch: number;
}

const JSON_HEADERS = { "content-type": "application/json" } as const;

/**
 * Wie oft die Empfehlung insgesamt angefordert wird, bevor aufgegeben wird.
 *
 * WARUM ES SIE GIBT: Das Backend verwirft eine Empfehlung hart, wenn sie eine
 * unbelegte Zahl trägt oder den Simulations-Vorbehalt umdeutet (422, Invarianten
 * I/II). Es wird dabei NICHTS abgelegt — eigens geprüft in
 * `test_erfundene_zahl_wird_rejected_und_nicht_persistiert`. Ein zweiter Versuch
 * kann deshalb keine Dublette erzeugen; genau darauf baut diese Schleife.
 *
 * WARUM DREI UND NICHT MEHR: Jeder Versuch ist ein eigener Modellaufruf. Gemessen
 * an der Demo-Instanz am 01.09.2026: 18,7 / 26,6 / 36,9 Sekunden reine
 * Modell-Latenz. Drei Versuche kosten also bis zu knapp zwei Minuten und das
 * Dreifache an Modellzeit. Mehr wäre für den Wartenden nicht mehr zumutbar.
 *
 * WARUM VORN UND NICHT IM BACKEND: Die auslösende Anfrage hat 90 Sekunden
 * (REASONER_TIMEOUT_MS). Drei Modellaufrufe in EINER Anfrage passen dort nicht
 * hinein — schon der langsamste gemessene Aufruf dreimal wären 110 Sekunden. Je
 * Versuch eine eigene Anfrage bleibt innerhalb der Frist und macht nebenbei
 * sichtbar, dass noch gearbeitet wird.
 *
 * GRENZE, offen benannt: Ein zweiter Versuch hilft nur, wenn das Modell streut.
 * Der Cloud-Pfad sendet keine Sampling-Parameter und streut damit. Der LOKALE
 * Pfad läuft mit `temperature = 0.0` — dort liefert jeder Versuch dasselbe
 * Ergebnis, und die Wiederholung kostet nur Zeit. Wer lokal betreibt, sollte die
 * Zahl auf 1 setzen.
 */
export const MAX_VERSUCHE = 3;

/** Fehlertext (Hallensprache) zu einem fehlgeschlagenen Schritt. Reine Funktion,
 *  exportiert für den Test — die Statuscode-Abbildung ist Vertrag, kein Detail. */
export function failureText(
  status: number | null,
  what: "prediction" | "recommendation",
  versuche = 1,
): string {
  if (status === 401) {
    return "Sitzung abgelaufen — bitte neu anmelden";
  }
  if (status === 403) {
    return "Kein Zugriff auf diese Erkenntnis";
  }
  if (what === "recommendation" && status === 422) {
    // Backend rejectet eine unbelegte/umdeutende Empfehlung (Invarianten I/II) —
    // ehrlich benennen. Die Zahl der Versuche gehört dazu: Sie sagt dem Leser,
    // dass es nicht an einem Ausrutscher lag, sondern wiederholt nicht gelang.
    return versuche > 1
      ? `Empfehlung konnte auch nach ${versuche} Versuchen nicht belegbar erzeugt werden`
      : "Empfehlung konnte nicht belegbar erzeugt werden";
  }
  if (status === 429) {
    return "Gerade viele Analysen unterwegs — bitte kurz warten";
  }
  if (status === 503) {
    // Bekannter Betriebszustand, kein Defekt: die Vorhersage selbst ist rein
    // rechnerisch (kein Modell-Aufruf) — nur die Empfehlung braucht das Gateway.
    return what === "prediction"
      ? "Vorhersage vorübergehend nicht abrufbar"
      : "Empfehlung vorübergehend nicht verfügbar — die Vorhersage bleibt gültig";
  }
  if (status === 504) {
    // Die Antwort kam zu spät, die Auswertung läuft aber zu Ende und wird abgelegt
    // (belegt am 01.09.2026: die Empfehlung entstand trotz Abbruch). Deshalb auf
    // das Nachladen verweisen statt einen Fehlschlag zu melden.
    return what === "prediction"
      ? "Vorhersage dauert ungewöhnlich lange — bitte gleich noch einmal nachsehen"
      : "Empfehlung dauert ungewöhnlich lange — sie wird abgelegt und erscheint beim nächsten Aufruf";
  }
  return what === "prediction" ? "Vorhersage nicht abrufbar" : "Empfehlung nicht abrufbar";
}

export function usePrediction({ machineId, autoload = true }: UsePredictionOptions): UsePredictionResult {
  const [phase, dispatch] = useReducer(
    onDemandReducer<PredictionPair>,
    initialPhase<PredictionPair>(),
  );
  const inflight = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  const [versuch, setVersuch] = useState(1);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      inflight.current?.abort();
    };
  }, []);

  /** Jüngste VOLLSTÄNDIGE Erkenntnis laden (Snapshot) — nie eine nackte Vorhersage. */
  const loadLatest = useCallback(async () => {
    const controller = new AbortController();
    inflight.current?.abort();
    inflight.current = controller;
    try {
      const predRes = await fetch(latestPredictionEndpoint(machineId), {
        credentials: "same-origin",
        signal: controller.signal,
      });
      if (!predRes.ok) {
        return;
      }
      const list = (await predRes.json()) as FailurePredictionRead[];
      const prediction = list[0];
      if (!prediction) {
        return; // keine gespeicherte Vorhersage → Ruhezustand bleibt leer
      }
      const recRes = await fetch(recommendationEndpoint(prediction.id), {
        credentials: "same-origin",
        signal: controller.signal,
      });
      if (!recRes.ok) {
        return; // Vorhersage ohne Empfehlung → keine Karte, Ruhezustand bleibt leer
      }
      const recommendation = (await recRes.json()) as WorkerRecommendationRead;
      if (mounted.current) {
        dispatch({
          type: "resolve",
          data: { prediction, recommendation },
          stampedAt: recommendation.created_at,
        });
      }
    } catch {
      // Autoload ist best-effort: still bleiben, der Trigger kann frisch holen.
    }
  }, [machineId]);

  useEffect(() => {
    if (autoload) {
      void loadLatest();
    }
  }, [autoload, loadLatest]);

  const trigger = useCallback(() => {
    const controller = new AbortController();
    inflight.current?.abort();
    inflight.current = controller;
    // Zuruecksetzen VOR der Vorhersage: Endete der vorige Lauf bei Versuch 3,
    // stuende sonst waehrend des ganzen Vorhersage-Schritts noch die alte Zahl
    // in der Anzeige — eine Wartemeldung, die einen Versuch behauptet, der
    // noch gar nicht laeuft.
    setVersuch(1);
    dispatch({ type: "request" });

    void (async () => {
      try {
        const predRes = await fetch(predictEndpoint(), {
          method: "POST",
          credentials: "same-origin",
          headers: JSON_HEADERS,
          body: JSON.stringify({ machine_id: machineId }),
          signal: controller.signal,
        });
        if (!predRes.ok) {
          if (mounted.current) {
            dispatch({ type: "reject", message: failureText(predRes.status, "prediction") });
          }
          return;
        }
        const prediction = (await predRes.json()) as FailurePredictionRead;

        // WIEDERHOLT WIRD NUR DIE 422 — und das ist die tragende Unterscheidung:
        // Sie heißt „der erzeugte INHALT hat den Guard nicht bestanden", und ein
        // streuendes Modell kann beim nächsten Mal etwas Belegbares liefern. Jede
        // andere Lage ist eine Störung des WEGES (Netz, Sitzung, Zugriff, Frist)
        // oder ein fehlender Gegenstand (404) — die wiederholt sich unverändert,
        // und ein zweiter Versuch kostete nur Zeit und Geld.
        let recRes: Response | null = null;
        let gefahren = 0;
        for (let n = 1; n <= MAX_VERSUCHE; n += 1) {
          if (mounted.current) {
            setVersuch(n);
          }
          gefahren = n;
          recRes = await fetch(recommendationEndpoint(prediction.id), {
            method: "POST",
            credentials: "same-origin",
            headers: JSON_HEADERS,
            body: "{}",
            signal: controller.signal,
          });
          if (recRes.status !== 422) {
            break;
          }
        }
        if (recRes === null || !recRes.ok) {
          if (mounted.current) {
            dispatch({
              type: "reject",
              // `gefahren` und nicht MAX_VERSUCHE: Bei einem anderen Fehler wurde
              // genau EINMAL gefahren, und die Meldung darf keine Versuche
              // behaupten, die es nicht gab.
              message: failureText(recRes?.status ?? null, "recommendation", gefahren),
            });
          }
          return;
        }
        const recommendation = (await recRes.json()) as WorkerRecommendationRead;
        if (mounted.current) {
          dispatch({
            type: "resolve",
            data: { prediction, recommendation },
            stampedAt: recommendation.created_at,
          });
        }
      } catch (caught) {
        if ((caught as Error).name === "AbortError") {
          return;
        }
        if (mounted.current) {
          dispatch({ type: "reject", message: "Erkenntnis nicht abrufbar (Netz oder Backend)" });
        }
      }
    })();
  }, [machineId]);

  return { phase, trigger, busy: phase.kind === "processing", versuch };
}
