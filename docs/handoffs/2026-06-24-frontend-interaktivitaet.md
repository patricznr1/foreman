# Hand-off — FOREMAN Frontend-Interaktivitäts-Sprint — 2026-06-24

## Kontext
FOREMAN ist live auf Railway (main `4600388`, alle Services SUCCESS, Login als Rolle **manager** — Zugangsdaten nicht im Repo, siehe Secret-Store/separaten Kanal). Beim Durchklicken fällt durchgängig auf: die Sichten zeigen Daten an, sind aber **nicht explorierbar** — man will intuitiv klicken (Alarmzeile, Aggregat-Einträge, Ketten-Summaries) und wird nirgends hingeleitet, oder Texte sind abgeschnitten ohne Volltext-Zugang. Frühere Fixes (PR #40 Cockpit-Drill-Down, #42 Sensor-Default) waren punktuell und lösen das **nicht**.

**Schlüssel-Einsicht:** Der Manager hat `aggregateOnly` (lib/machine/roles.ts) und bekommt deshalb die **Aggregat-Varianten** der Sichten (AlarmAggregate „Häufigste Quellen", ChainsAggregate 1-Satz-Summaries) — und genau die sind als Sackgassen gebaut (Anzeige ohne Drill-Down). Dazu die generellen AlarmRow-Lücken (Zeile nicht klickbar, Message truncated).

## Ziel
FOREMANs Sichten **durchgängig explorierbar** machen — jede intuitive Klick-Erwartung führt zu Navigation oder mehr Detail; keine abgeschnittenen Texte ohne Volltext-Zugang. Verfassungslinie der Designstudie bleibt: **HITL = nur Navigation/Anzeige, keine Anlagen-Aktorik**; „graceful" bleibt nur dort, wo das Ziel real noch nicht existiert (F/G).

## ⚠️ ZUERST KLÄREN (Design, nicht blind bauen)
Der Builder soll NICHT sofort drauflos coden (das war der vorige Fehler). Erst mit Patric die Interaktions-Form festlegen — am besten per `brainstorming`-Skill + 1-2 gezielte `AskUserQuestion`:
1. **Alarm-Detail:** Soll ein Klick auf eine Alarmzeile zu einer eigenen Detail-Ansicht führen (Modal vs. eigene Route `/alarms/[id]`) — mit Volltext, Verlauf, Querlinks, zugehöriger Kette? Oder direkt zur Maschine?
2. **Manager-Aggregat-Konflikt:** Sollen die Aggregat-Sichten (Häufigste Quellen, Ketten-Summaries) **klickbar→gefilterte Detail-Liste** werden (Aggregat bleibt, wird aber Einstieg), ODER soll der Manager Zugang zu den vollen Sichten bekommen (Designstudie sagt aktuell `aggregateOnly` — bewusste Abweichung wäre nötig)? Das ist ein Design-Entscheid gegen die Matrix 3.1 / Studie §4 — mit Patric bestätigen.
3. **Volltext:** Inline-Expand (line-clamp + „mehr") vs. im Detail-Modal?

## Plan (nach der Design-Klärung, priorisiert nach Frust-Impact)
1. **AlarmRow-Zeile klickbar** → Alarm-Detail bzw. Maschine. Datei: `frontend/components/alarms/alarm-row.tsx:64` (das `<article>`). Querlinks am Rand bleiben, aber die Zeile selbst wird primärer Einstieg.
2. **Alarm-Message Volltext** statt `truncate` ohne Ausweg. `frontend/components/alarms/alarm-row.tsx:110`.
3. **AlarmAggregate „Häufigste Quellen" klickbar** → gefilterte Alarmliste der Quelle/Maschine. `frontend/components/alarms/alarm-aggregate.tsx:62`.
4. **ChainsAggregate (Manager) klickbar** → zur vollen Ketten-Erzählung in D. `frontend/components/event-chains/chains-aggregate.tsx:42`.
5. **Alarm-Detail-Ansicht** (zentraler fehlender Baustein): Volltext + Verlauf + Querlinks (Maschine/Kette/Vorhersage/Notiz) + ggf. zugehörige Ereigniskette. Neue Komponente/Route — Form aus Schritt „Zuerst klären".
6. **Maschinen-Alarme (B)** erben automatisch die AlarmRow-Fixes (`frontend/components/machine/machine-alarms.tsx` nutzt dieselbe `AlarmRow`).
7. **SiblingChains** (`frontend/components/event-chains/sibling-chains.tsx:45`): nicht-anspringbare Verweise klarer kennzeichnen (Icon + Tooltip „noch keine gespeicherte Kette").

## Was GUT ist (nicht anfassen)
Ereignisketten-Detail (D: Rekonstruktion, Zeitachse, klickbare Quell-Chips), Maschinen-Trend/Specs (B), Cockpit-Drill-Down (A, PR #40), Querlinks in AlarmRow. F/G sind bewusst grau/„folgt" — KEINE Scheinfunktion einbauen.

## Erlaubte Dateien
- `frontend/components/alarms/alarm-row.tsx` (+ `.test.tsx`)
- `frontend/components/alarms/alarm-aggregate.tsx` (+ `.test.tsx`)
- `frontend/components/event-chains/chains-aggregate.tsx` (+ `.test.tsx`)
- `frontend/components/event-chains/sibling-chains.tsx` (+ `.test.tsx`)
- ggf. NEU: `frontend/components/alarms/alarm-detail*.tsx` + Route `frontend/app/(app)/alarms/[id]/page.tsx` (falls eigene Route gewählt)
- ggf. `frontend/components/alarms/alarms-view.tsx` / `frontend/components/machine/machine-alarms.tsx` (Verdrahtung)
- zugehörige `lib/alarms/*` nur falls View-State nötig (transport-neutral, testbar)
- KEINE Backend-Änderung erwartet (Daten sind vorhanden: Alarm trägt machine_id/component_id/message; Ketten-Narrativ via GET .../event_chain/explanations).

## Konventionen
Siehe `GROUND_TRUTH.md` (§21 Frontend, §4/§5 Verträge) + Designstudie `docs/research/FOREMAN_Designstudie_Frontend.md` (ISA-101-Ruhe, HITL ohne Aktorik, bespoke token-SVG statt Charting-Lib, mehrkanalige Zustände). Chirurgisch ändern; TypeScript strict, kein `any`; deutsche Kommentare/Fehlermeldungen.

## TESTS (Pflicht — test-defaults-nextjs)
- **Vitest** pro geänderter/neuer Komponente: klickbare Zeile rendert Link/Button mit korrektem Ziel; Aggregat-Eintrag löst Filter/Navigation aus; Volltext wird nach Expand/Detail sichtbar; Detail-Ansicht zeigt vollen Kontext.
- **Reine View-State-Logik** (Filter-Auswahl, Detail-Auflösung) als transport-neutrale `lib/`-Funktionen mit eigenen Unit-Tests (wie bestehende `lib/alarms/*`).
- **a11y:** klickbare Zeile als `<button>`/`<Link>` mit zeilenspezifischem Accessible Name (mehrere Alarme unterscheidbar); Fokus-Handling bei Modal (Fokus-Falle + Rückgabe).
- **HITL-Invariante:** keine neuen Pfade, die Anlagen-Aktorik auslösen — nur Lese-/Navigations-Ziele.

## Abnahme-Kriterien
- `cd frontend && npx tsc --noEmit` clean
- `npx eslint <geänderte Dateien>` clean
- `npx vitest run <betroffene Tests>` grün (+ neue Tests für jede neue Interaktion)
- `npm run build` ok
- Hidden-Term-Scan über die Produktiv-Quelle sauber (keine NEXUS-Interna)
- **Browser-Durchklick (Playwright, als manager):** Alarmzeile klickbar → Detail/Maschine; Volltext sichtbar; „Häufigste Quellen" + Ketten-Summary führen weiter; keine toten Klick-Erwartungen mehr in C/B/D.
- PR erstellen, NICHT selbst mergen (Patrics Wort). Frontend ist Railway-Upload-Service → nach Merge finaler `railway up --service frontend` von main für Live.

---

## Claude-Code-Prompt (kopierbereit)
```text
Lies docs/handoffs/2026-06-24-frontend-interaktivitaet.md komplett.
Lies GROUND_TRUTH.md (§21 Frontend) und überfliege docs/research/FOREMAN_Designstudie_Frontend.md.

WICHTIG: NICHT sofort coden. Erst den Abschnitt "ZUERST KLÄREN" mit mir
durchgehen — nutze den brainstorming-Skill + AskUserQuestion, um die
Interaktions-Form (Alarm-Detail Modal vs. Route, Manager-Aggregat-Konflikt,
Volltext-Form) festzulegen. Erst nach meiner Bestätigung den Plan bauen.

Halte dich an die Whitelist "Erlaubte Dateien". Bei jeder offenen Frage
stoppen, nicht raten. Chirurgische Changes, TypeScript strict, Tests pro
Interaktion. Nach Implementation: tsc + eslint + vitest laufen lassen,
Output zeigen; dann Browser-Durchklick als manager. PR erstellen, nicht mergen.
```
