# FOREMAN Frontend-Interaktivität — Implementierungs-Plan

> **Für agentische Worker:** Ausführung task-by-task via `superpowers:subagent-driven-development` oder `superpowers:executing-plans`. Steps mit Checkbox-Syntax.

**Goal:** FOREMANs Sichten durchgängig explorierbar machen — klickbare Alarmzeilen, Alarm-Volltext in der Maschine, und das `manager`-Login zum Werksleiter-/Vorführ-Vollzugriffsprofil (liest C/D/E/H voll, fragt, entscheidet) aufwerten.

**Architecture:** Rein im Frontend (Next.js 15 / React 19 / TS strict / Vitest). Die Rollen-Trennung lebt als UX-Filter in `lib/*/roles.ts`; das Backend prüft auf den Schreib-/Trigger-Routen **keine Rolle** (nur Authentifizierung) → kein Backend-Change, keine toten Klicks. Die drei harten Haltungen (Sim-Vorbehalt sichtbar · HITL ohne Aktorik · Gedächtnis paraphrasiert) bleiben unberührt; Quittieren/Triggern ist keine Anlagen-Aktorik. Abweichung ausschließlich gegen die Rollen-Konvention der Designstudie-Matrix 3.1 — bewusst, dokumentiert.

**Tech Stack:** Next.js App Router, React 19, TypeScript strict (`noUncheckedIndexedAccess`, kein `any`), Tailwind 4 (semantische Token-Utilities), Vitest + Testing Library.

**Detail-Level (bewusste Skalierung):** Ich (Claude Code) bin der ausführende Worker und implementiere direkt nach Plan-Abnahme. Der Plan ist deshalb auf *Überprüfbarkeit durch Patric* + *meine Ausführungs-Landkarte* skaliert: vollständiger Code an den nicht-trivialen Stellen (manager-Voll-Zweige, AlarmRow-Klickfläche, E-Maschinenquelle, repräsentative Tests), präzise Beschreibung statt Voll-Duplikat bei sich wiederholenden Mustern (analoge roles-Tests).

---

## Verfassungs- & Scope-Leitplanken (gelten für jeden Task)
- **Keine Anlagen-Aktorik.** Nur Lese-/Navigations-/Trigger-/Quittier-Ziele. Negativ-Invariante in Tests halten (`isAlarmStatusActionPath`, `predictionDecisionEndpoint()===null`).
- **Keine Backend-Änderung.** Verifiziert: `acknowledge`/`reconstruct`/`predict`/`recommendation` verlangen nur `CurrentUser`, keine Rollenprüfung.
- **Nicht-Drift-Quittierung** bleibt sichtbar deaktiviert-mit-Grund (keine generische Route) — kein toter Klick.
- **Chirurgisch:** nur Whitelist-Dateien. Aggregat-Komponenten werden als Lagebild-Kopf *wiederverwendet*, nicht gelöscht (kein ungefragtes Dead-Code-Entfernen).
- **Hidden-Term-Scan** über sichtbare Quelle vor PR.

---

## Etappe A — Rollen-Logik (lib, rein, transport-neutral)

Macht `manager` auf der Datenebene zur Vollzugriffs-Rolle. Reine Funktionen → TDD trivial.

### Task A1: `lib/alarms/roles.ts` — manager voll
**Files:** Modify `frontend/lib/alarms/roles.ts:47-52` · Test `frontend/lib/alarms/roles.test.ts`

- [ ] **Step 1 — Test zuerst** (ergänzen):
```ts
it("manager (Vorführ-Vollzugriff): volle Liste + quittieren, Scope alle", () => {
  const v = alarmRoleView("manager");
  expect(v.aggregateOnly).toBe(false);
  expect(v.canAcknowledge).toBe(true);
  expect(v.scope).toBe("all");
});
```
- [ ] **Step 2 — Run, erwartet FAIL** (`npx vitest run lib/alarms/roles.test.ts`).
- [ ] **Step 3 — Impl:** manager-Eintrag setzen:
```ts
  manager: {
    canAcknowledge: true,
    aggregateOnly: false,
    scope: "all",
    // Quittieren ist möglich, aber nicht die Default-Geste des Werksleiters.
    acknowledgeIsDefault: false,
  },
```
- [ ] **Step 4 — Run, erwartet PASS.** Bestehende manager-Tests, die `aggregateOnly:true`/`canAcknowledge:false` erwarten, mit anpassen (Suchlauf in der Datei).
- [ ] **Step 5 — Commit:** `feat(alarms): manager als Vollzugriff-Rolle (lesen+quittieren, scope all)`

### Task A2: `lib/event-chains/roles.ts` — manager voll
**Files:** Modify `frontend/lib/event-chains/roles.ts:29` · Test `…/roles.test.ts`
- [ ] **Test:** `chainRoleView("manager")` → `{ canTrigger:true, canPin:true, aggregateOnly:false }`.
- [ ] **Impl:** `manager: { canTrigger: true, canPin: true, aggregateOnly: false }`.
- [ ] Run FAIL→PASS, bestehende manager-Erwartungen anpassen, Commit `feat(event-chains): manager voll (rekonstruieren+pinnen)`.

### Task A3: `lib/prediction/roles.ts` — manager voll
**Files:** Modify `frontend/lib/prediction/roles.ts:31` · Test `…/roles.test.ts`
- [ ] **Test:** `predictionRoleView("manager")` → `{ canTrigger:true, canDecide:true, factorDetail:true, aggregateOnly:false }`.
- [ ] **Impl:** manager-Eintrag entsprechend setzen.
- [ ] Run FAIL→PASS, Erwartungen anpassen, Commit `feat(prediction): manager voll (anfordern+entscheiden+Faktor-Detail)`.

### Task A4: `lib/memory/roles.ts` — manager Vollzugriff
**Files:** Modify `frontend/lib/memory/roles.ts:51-57` · Test `…/roles.test.ts`
- [ ] **Test:** `memoryRoleView("manager").jumpToDiagnosis` → `true` (Rest unverändert: `aggregateFirst:true` bleibt = Muster zuerst, aber voller Zugang inkl. Sprung in Diagnose).
- [ ] **Impl:** `jumpToDiagnosis: true` im manager-Eintrag.
- [ ] Run FAIL→PASS, Commit `feat(memory): manager Sprung in Diagnose (Vollzugriff)`.

---

## Etappe B — AlarmRow: klickbare Zeile + Volltext

### Task B1: AlarmRow-Zeile als Klickfläche → Maschine (a11y-sicher, kein verschachteltes Interaktiv-Element)
**Files:** Modify `frontend/components/alarms/alarm-row.tsx` · Test `…/alarm-row.test.tsx`

Muster: **Stretched-Link** statt `<article>`-in-`<Link>`. Die `<article>` wird `relative`; ein primärer, die Zeile überdeckender Link (`after:absolute after:inset-0`) auf `machineHref`; die Rand-Querlinks/Buttons bekommen `relative z-10`, damit sie *über* der Klickfläche bedienbar bleiben (keine `<a>`-in-`<a>`-Verschachtelung — der Stretched-Link ist ein Geschwister, kein Vorfahr).

- [ ] **Step 1 — Test zuerst:**
```ts
it("ganze Zeile ist klickbar → Maschine (zeilenspezifischer Accessible Name)", () => {
  render(<AlarmRow vm={vm({ machine_id: 1, message: "Lager heiß" })} {...props} />);
  // Primärer Zeilen-Link trägt Maschinenbezug, damit mehrere Zeilen unterscheidbar sind.
  const rowLink = screen.getByRole("link", { name: /Presse 1 öffnen/ });
  expect(rowLink).toHaveAttribute("href", "/machines/1");
});
it("innere Querlinks bleiben eigenständig bedienbar (nicht im Zeilen-Link verschachtelt)", () => {
  render(<AlarmRow vm={vm({ machine_id: 1, severity: "alarm" })} {...props} />);
  expect(screen.getByRole("link", { name: "Kette" })).toBeInTheDocument();
});
```
- [ ] **Step 2 — Run FAIL.**
- [ ] **Step 3 — Impl:** `<article>` → `className="relative …"`. Den Maschinenbezug-Block (Zeile 84–111) um einen Stretched-Link ergänzen:
```tsx
{/* Primärer Zeilen-Einstieg: ganze Zeile öffnet die Maschine (B), wo der Alarm
    im Kontext + Volltext lebt. Stretched-Link → keine <a>-in-<a>-Verschachtelung. */}
<Link
  href={machineHref}
  aria-label={`${vm.machineLabel} öffnen`}
  className="absolute inset-0 z-0 rounded focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus-ring"
/>
```
  Die bestehende `<nav aria-label="Querlinks">` und die Aktions-Buttons bekommen zusätzlich `relative z-10`. Der bisherige Rand-Querlink „Maschine" entfällt (durch den Zeilen-Link redundant) — chirurgisch nur diesen einen `<Link>` entfernen.
- [ ] **Step 4 — Run PASS** + bestehenden Test „Querlinks → Maschine/Kette/Ausfall" anpassen (statt Rand-Link „Maschine" prüft er nun den Zeilen-Link `/machines/1`).
- [ ] **Step 5 — Commit:** `feat(alarms): Alarmzeile klickbar → Maschine (stretched-link, a11y)`

### Task B2: Alarm-Message — Tooltip in C, Volltext-Variante für B
**Files:** Modify `frontend/components/alarms/alarm-row.tsx` · `frontend/lib/alarms/types.ts` (kein neuer Typ nötig — neue **Prop**, nicht VM-Feld) · Test `…/alarm-row.test.tsx`

Neue optionale Prop `fullMessage?: boolean` (Default `false`). In C bleibt `truncate` + `title={vm.message}` (Sofort-Blick, Screenreader); in B (`fullMessage`) wird die Message vollständig umgebrochen statt abgeschnitten. **Keine** variable Zeilenhöhe in C (Virtualisierung `window.ts` bleibt unangetastet) — der `title`-Tooltip braucht keine Layout-Änderung.

- [ ] **Step 1 — Test:**
```ts
it("C-Liste: Message truncated mit title-Tooltip (Volltext für Hover/Screenreader)", () => {
  render(<AlarmRow vm={vm({ message: "Lager heiß, Geräusch seit Frühschicht" })} {...props} />);
  const msg = screen.getByText("Lager heiß, Geräusch seit Frühschicht");
  expect(msg).toHaveClass("truncate");
  expect(msg).toHaveAttribute("title", "Lager heiß, Geräusch seit Frühschicht");
});
it("fullMessage: Volltext ohne truncate (für die Maschinensicht B)", () => {
  render(<AlarmRow vm={vm({ message: "Lager heiß, Geräusch seit Frühschicht" })} {...props} fullMessage />);
  const msg = screen.getByText("Lager heiß, Geräusch seit Frühschicht");
  expect(msg).not.toHaveClass("truncate");
});
```
- [ ] **Step 2 — Run FAIL.**
- [ ] **Step 3 — Impl:** Prop ergänzen; Message-`<div>` (Zeile 110):
```tsx
<div
  className={cx("text-caption text-fg-secondary", fullMessage ? "whitespace-pre-wrap" : "truncate")}
  title={fullMessage ? undefined : vm.message}
>
  {vm.message}
</div>
```
- [ ] **Step 4 — Run PASS.**
- [ ] **Step 5 — Commit:** `feat(alarms): Message-Tooltip in C + Volltext-Variante (fullMessage)`

### Task B3: MachineAlarms (B) nutzt die Volltext-Variante
**Files:** Modify `frontend/components/machine/machine-alarms.tsx:82-92` · Test `…/machine-alarms.test.tsx` (falls vorhanden; sonst neu)
- [ ] **Test:** In B gerenderte AlarmRow zeigt die volle Message (kein `truncate`).
- [ ] **Impl:** `<AlarmRow … fullMessage />` an der Render-Stelle ergänzen.
- [ ] Run FAIL→PASS, Commit `feat(machine): Alarm-Volltext in der Maschinensicht`.

---

## Etappe C — View-Orchestratoren: manager-Voll-Zweige (Aggregat-Kopf + volle Sicht)

### Task C1: AlarmsView — manager: Lagebild-Kopf + volle Liste über overview
**Files:** Modify `frontend/components/alarms/alarms-view.tsx` · neu evtl. `frontend/components/alarms/alarm-situation-header.tsx` (Aggregat-Inhalt als wiederverwendbarer Kopf) · Test `…/alarms-view.test.tsx`

Da `manager.aggregateOnly` jetzt `false`: der bestehende `if (roleView.aggregateOnly) return <AlarmAggregate/>` greift nicht mehr. Neuer manager-Zweig: wie `LeadAlarmsView` (overview-Abo → Maschinen-Labels + Live-Zähler, scope „all") **plus** das Alarm-Lagebild als Kopf über der Liste.

- [ ] **Step 1 — Refactor (kein Verhaltens-Change):** Den Lagebild-Inhalt aus `alarm-aggregate.tsx` (Prioritäts-Zähler-Grid + „Häufigste Quellen") in eine reine Präsentations-Komponente `AlarmSituationHeader({ overview })` extrahieren. `AlarmAggregate` rendert weiterhin denselben Kopf (DRY) — bestehendes Verhalten unverändert. Tests für `AlarmAggregate` bleiben grün.
- [ ] **Step 2 — Test (manager-Zweig):**
```ts
it("manager: Lagebild-Kopf UND volle Alarmliste (kein reines Aggregat)", async () => {
  // Render AlarmsView mit manager-User + Fake-Transport (overview-Snapshot + alarms).
  // Erwartung: Häufigste-Quellen-Kopf sichtbar + mindestens eine AlarmRow gerendert.
});
```
- [ ] **Step 3 — Impl:** in `AlarmsView`:
```tsx
if (user.role === "manager") return <ManagerAlarmsView user={user} />;
```
  `ManagerAlarmsView`: overview-Abo (`useTopicView(store,"overview")`), rendert `<AlarmSituationHeader overview={overview}/>` über `<AlarmsWorkspace user canAcknowledge overview signalTopics={OVERVIEW_TOPICS} />`. Scope „all" liefert `roleView` bereits.
- [ ] **Step 4 — Run PASS.** **Step 5 — Commit:** `feat(alarms): manager-Vollsicht (Lagebild-Kopf + volle Liste)`

### Task C2: ChainsView — manager: volle Ketten-Sicht
**Files:** Modify `frontend/components/event-chains/chains-view.tsx:42-44` · Test `…/chains-view.test.tsx`

`manager.aggregateOnly` jetzt `false` → der `if (roleView.aggregateOnly) return <ChainsAggregate/>`-Zweig greift nicht mehr; manager fällt automatisch in `ChainsSingle` (volle Erzählung, `canTrigger`/`canPin` aus A2). Der Kennzahl-/Summary-Überblick (`ChainsAggregate`) wird als optionaler Kopf oberhalb der `SavedChainsList` eingehängt.
- [ ] **Test:** manager-User → `ChainTriggerPanel`-Pfad verfügbar (mit `anchor`), `SavedChainsList` gerendert; **nicht** nur die Aggregat-Liste.
- [ ] **Impl:** Da der aggregateOnly-Zweig leerläuft, genügt: Aggregat-Kennzahl als Kopf in `ChainsSingle` einhängen (kleiner „Gespeicherte Ketten: N"-Block — `toSummary`/`list.length` aus `useSavedChains`), darunter die bestehende Zwei-Spalten-Sicht. Chirurgisch additiv.
- [ ] Run FAIL→PASS, Commit `feat(event-chains): manager-Vollsicht (Kennzahl-Kopf + volle Erzählung + Trigger)`.

### Task C3: PredictionView — manager: volle Sicht + overview-Maschinenquelle
**Files:** Modify `frontend/components/prediction/prediction-view.tsx` · Test `…/prediction-view.test.tsx`

**Kernproblem:** `PredictionSingle` zieht Maschinen aus `user.assigned_machine_ids` — manager hat dort nichts. Lösung: ein manager-Zweig, der die Maschinen-Auswahl aus dem **overview-Topic** (`machines[].id/label`) speist statt aus `assigned_machine_ids`.
- [ ] **Step 1 — Test:** manager-User + overview-Snapshot mit 2 Maschinen → Maschinen-Auswahl zeigt beide; `PredictionPanel` mit `roleView.canTrigger=true` gerendert.
- [ ] **Step 2 — Impl:** `manager.aggregateOnly` ist `false` → neuer expliziter Zweig vor `PredictionSingle`:
```tsx
if (user.role === "manager") return <ManagerPredictionView roleView={roleView} />;
```
  `ManagerPredictionView`: `useTopicView(store,"overview")` → `overview.machines`; lokaler `selected`-State (erste Maschine default); Auswahl-`<select>` aus `overview.machines` (Label statt „Maschine {id}"); optional `<PredictionAggregate/>` als Risiko-Kopf darüber; `<PredictionPanel machineId={selected} roleView label={machineLabel}/>`. Fünf-Zustände/Degradation über das overview-Topic.
- [ ] **Step 3 — Run PASS.** **Step 4 — Commit:** `feat(prediction): manager-Vollsicht (overview-Maschinenquelle + Trigger/Entscheidung)`

### Task C4: Memory — manager Sprung in Diagnose verdrahtet
**Files:** ggf. Modify `frontend/components/memory/memory-view.tsx` (nur falls `jumpToDiagnosis` dort gated) · Test entsprechend.
- [ ] Prüfen, ob `memory-view` `roleView.jumpToDiagnosis` liest; falls ja, Test ergänzen (manager sieht Diagnose-Sprung). Falls die Komponente das Flag schon generisch nutzt, genügt A4 + ein View-Test. Commit `feat(memory): manager Diagnose-Sprung verdrahtet`.

---

## Etappe D — SiblingChains-Kennzeichnung + Aufräumen

### Task D1: SiblingChains — nicht-anspringbare Verweise klar kennzeichnen
**Files:** Modify `frontend/components/event-chains/sibling-chains.tsx:54-61` · Test `…/sibling-chains.test.tsx`
- [ ] **Test:** Nicht-navigierbarer Sibling rendert ein Hinweis-Icon (`aria-hidden`) + zugänglichen Tooltip/Text „noch keine gespeicherte Kette zum Anspringen".
- [ ] **Impl:** Im nicht-navigierbaren Zweig (Zeile 55–60) ein dezentes Symbol (z. B. `◷`/Info-Glyph, `aria-hidden`) vor den bestehenden Hinweistext setzen + `title` am Container. Chirurgisch additiv, bestehender Text bleibt.
- [ ] Run FAIL→PASS, Commit `feat(event-chains): nicht-anspringbare Schwesterketten klar gekennzeichnet`.

---

## Etappe E — Doku, Gates, Browser, PR

### Task E1: GROUND_TRUTH-Update (Pflicht — ground-truth-update)
**Files:** Modify `foreman/GROUND_TRUTH.md` §21.9 / §21.10 / §21.12 / §21.15
- [ ] In jeder betroffenen Sektion die manager-Zeile auf „Vollzugriff (Vorführ-/Werksleiter-Profil)" aktualisieren; einen zentralen Vermerk ergänzen: *manager = bewusste Abweichung von Matrix 3.1 (volle Lese-Dichte + Trigger + Quittieren), harte Haltungen intakt (kein Aktorik), Backend ohne Rollen-AuthZ → kein Block; Begründung Vorführbarkeit + Werksleiter-Transparenz.*
- [ ] Commit `docs(ground-truth): manager-Vollzugriffsprofil dokumentiert (§21.9/.10/.12/.15)`

### Task E2: Gates (lokal, alle grün — Abnahme)
- [ ] `cd frontend && npx tsc --noEmit` → 0 Fehler
- [ ] `npx eslint <geänderte Dateien>` → 0
- [ ] `npx vitest run` → grün (neue Tests inklusive)
- [ ] `npm run build` → ok
- [ ] `npm run tokens:check` → synchron
- [ ] Hidden-Term-Scan über sichtbare Quelle → sauber

### Task E3: Browser-Durchklick als manager (Playwright/MCP)
- [ ] Login als Rolle **manager** (Zugangsdaten nicht im Repo — Secret-Store/separater Kanal).
- [ ] Verifizieren: Alarme = volle Liste mit Lagebild-Kopf; Alarmzeile klickbar → Maschine; in der Maschine Alarm-Volltext lesbar; Ketten = volle Erzählung + „rekonstruieren" auslösbar; Vorhersage = Maschine wählbar + „anfordern" auslösbar; keine toten Klick-Erwartungen mehr in C/B/D/E.

### Task E4: PR (nicht mergen)
- [ ] Branch `feat/frontend-interaktivitaet`, alle Commits, PR mit Zusammenfassung + Gate-Nachweis + Verfassungs-Note. **Nicht selbst mergen** (Patrics Wort). Nach Merge: `railway up --service frontend` von main.

---

## Self-Review (Spec-Abdeckung)
- Handoff-Fix 1 (Zeile klickbar) → **B1**. Fix 2 (Message Volltext) → **B2/B3**. Fix 3 (AlarmAggregate) → **C1** (als Kopf). Fix 4 (ChainsAggregate) → **C2**. Fix 5 (Alarm-Detail) → **B1/B3** (Maschine als Detail-Ort, kein Modal — Patrics Wahl). Fix 6 (B erbt AlarmRow) → **B3**. Fix 7 (SiblingChains) → **D1**.
- manager-Vollzugriff (Patrics Kern) → **A1–A4 + C1–C4**. Backend-Verifikation → erledigt (kein Change). GROUND_TRUTH → **E1**. Tests pro Interaktion → in jedem Task. Browser-Durchklick → **E3**. PR ohne Merge → **E4**.
- Offen/abhängig: Maschinen-Labels für manager-E kommen aus overview (vorhanden). Aggregat-Komponenten bleiben (als Kopf wiederverwendet), kein Dead-Code-Löschen.
