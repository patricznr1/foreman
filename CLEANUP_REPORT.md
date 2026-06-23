# CLEANUP_REPORT — Aufräum- & Konsistenz-PR nach Sektion I

> Branch `chore/cleanup-post-i` von `main` (6f69d57). Charakter: Doku-/Konzept-Korrektur, minimaler Code. **Kein Feature-Bau** (G-Frontend, F4-Overlay, Reasoner #4 bleiben außen vor). CC merged nicht selbst.

Dieser Report listet (A) die durchgeführten **eindeutigen** Korrekturen und (B) die **uneindeutigen / entscheidungsbedürftigen** Funde, die nicht geraten, sondern Patric/Lena vorgelegt werden.

---

## A — Durchgeführte Korrekturen (eindeutig)

### Teil 1 — Reasoner #5 / Belastungs-Simulation → MCP-Datenfähigkeit

Autoritativ aus der NEXUS-Entscheidung „FOREMAN Belastungs-Simulation Korrektur" (23.06.2026): FOREMAN führt **keine** eigene Belastungs-Simulation durch (Parameter außerhalb der Beobachtungsgrenze). #5 ist **kein interner Reasoner**, sondern eine **MCP-Datenfähigkeit** (beobachtete Lastdaten read-only exponiert; Simulation fährt extern). **Vier** interne Reasoner. Sektion G = **Anzeige**, kein Simulator.

| Datei | Stelle | Korrektur |
|---|---|---|
| `GROUND_TRUTH.md` | §2 Z.31 | „fünf Reasoner" → „vier Reasoner" |
| `GROUND_TRUTH.md` | §2 Z.36–47 | Überschrift „Die fünf Reasoner" → „Die vier Reasoner"; Tabellen-Zeile 5 (Belastungs-Simulation) entfernt; Bau-Status #4 als datenabhängig; neuer Absatz „Belastungsdaten — kein Reasoner, sondern MCP-Datenfähigkeit" (extern simuliert, noch nicht gebaut) |
| `GROUND_TRUTH.md` | §21.6 Z.683 | FE-Tabelle „G Belastungs-Simulation" → „G Belastung (Lastprofil-Historie)" + Hinweis **Anzeige, kein Simulator**, G-FE folgt separat |
| `README.md` | Architektur | Mermaid „Five Reasoners"/R5 Load Simulation → „Four Reasoners" (R5 entfernt); Tabelle „The five reasoners" → „The four reasoners" (Load-Simulation-Zeile entfernt); neuer Hinweis „Load data, not load simulation" (MCP, extern); Frage-Bullet „Can the plant handle this load?" → ehrliche Beobachtungs-Frage |
| `docs/assets/foreman-hero.svg` | Motiv | „FIVE REASONERS · ONE MEMORY CORE" → „FOUR REASONERS …"; 5 Kreise + 5 Speichen → 4 (symmetrisches Quadrat, viewBox unverändert) — **öffentliches** Artefakt |
| `docs/research/FOREMAN_Designstudie_Frontend.md` | §3.1/§3.2/§4G/§5.1 | §4G vollständig recastet (Slider-Simulator → reine Lastprofil-/Grenzwert-**Anzeige**); Rollen-Matrix-Zeile G („durchspielen" → „lesen"); Begründungs-Absatz; ASCII-Flussdiagramm („simulieren"/„G Belastungs-Simulation" → „abrufen"/„G Belastung (Lastprofil-Historie)"); WebGL-Begründung (G als 2. Einsatzort entfällt → nur A); Z.17-Aufzählung (G nicht mehr „Erkenntnis erzeugen") |
| `docs/WALKTHROUGH.md` | Z.23 | „Fünf spezialisierte Denker" → „Vier spezialisierte Denker" |
| `docs/compliance/eu-ai-act-assessment.md` | §1 Z.12 | „Fünf Reasoner (…, Belastungs-Simulation)" → „Vier Reasoner (…)"; Zusatz: beobachtete Lastdaten = **reine Messdaten/Nicht-KI** über MCP, FOREMAN simuliert nicht selbst (AI-Act spiegelt Belastungsdaten ehrlich als Nicht-KI) |
| `docs/research/ausfallvorhersage-methodenwahl.md` | Z.13 | „datenhungrigste der fünf Reasoner" → „… der vier Reasoner" |
| `src/foreman/reasoners/__init__.py` | Header-Kommentar Z.4 | „fünf Reasoner (GROUND_TRUTH §2)" → „vier Reasoner …" |
| `frontend/components/insights/insights-hub.tsx` | G-Eintrag (Z.41–44) | Titel „Belastungs-Simulation" → „Belastung"; Blurb „Folgen einer Lasteinstellung durchspielen …" → „Beobachtete Lastprofile und Grenzwerte einsehen — reine Anzeige, kein Simulator" (Platzhalter bleibt disabled — **keine** G-Feature-Implementierung) |

### Teil 2 — Konsistenz-Audit GROUND_TRUTH ↔ Code (nach Sektion I)

Code-Realität via Explore-Agenten verifiziert (Schema, Routen, Migrationen, Reasoner, FE-Sektionen):

- **Schema §5 ↔ `db/models.py`:** 15 Modelle, deckungsgleich. `audit_logs` append-only via Trigger (Migration `0010`) bestätigt. **Keine Abweichung.**
- **Routen §4/§22 ↔ `api/routers/`:** `/api/v1/audit` + `/api/v1/topology` vorhanden, wie dokumentiert. **Keine Abweichung.**
- **Migrationen §5 ↔ `migrations/versions/`:** `0001`–`0010` vollständig, Liste stimmt. **Keine Abweichung.**
- **Reasoner-Stand §2:** Drift/Ereignisketten/Ausfallvorhersage gebaut; #4 Wartung offen/datenabhängig; **kein** Load-/Belastungs-Reasoner im Code (bestätigt: #5 nie gebaut → reine Doku-Korrektur). Konsistent hergestellt.
- **FE-Reifegrade §21 ↔ gebaute Sektionen:** A/B/C/D/E/H/I/J gebaut; F/G graceful-disabled Platzhalter. Stimmt mit §21.6.
- **`profile_band` / F4-Eigenprofil-Overlay:** im Schema **nicht** vorhanden; in §5/§20.5/§21.6/§21.11/§21.14 durchgängig als „reserviert/null, graceful weggelassen" markiert. **Bereits konsistent — keine Änderung nötig.**
- **Tech-Stack-Drift (korrigiert):** `GROUND_TRUTH.md` §3 + `README.md` nannten „shadcn/ui, Recharts". `frontend/package.json` enthält **weder** noch (nur next/react + tailwind/vitest/eslint/prettier); §21 sagt durchgängig „bespoke SVG, keine Charting-Lib". → §3 + README auf realen Stack korrigiert (bespoke SVG, kein shadcn/Recharts).

### Verifikation

- `ground-truth-check`: Pflicht-Sektionen §18 (Privacy & Compliance) + §19 (Security) vorhanden; Schema/Routen/Reifegrade deckungsgleich mit Code.
- Frontend-Gates: `tsc --noEmit` 0 · `eslint` clean · Vitest **633/633** grün.
- Python-Gates: `ruff check` clean · `mypy --strict` 0 (132 Dateien). (Full-`pytest` läuft gegen TimescaleDB auf der CI; die Python-Änderung ist ein reiner Header-Kommentar ohne Logikwirkung.)
- Hidden-Term-Scan über die berührten außen-sichtbaren Strings (README, SVG, FE-Card): Substrat bleibt „Gedächtnis-Substrat" / „external service"; keine internen Vokabeln/Bibliotheksnamen geleakt.

---

## B — Uneindeutige / entscheidungsbedürftige Funde (NICHT geraten)

### B1 — README „Status" + „Testing" sind veraltet (öffentlich, kuratierte Narrative)
- `README.md` §Status: „In main: …F6… In review: F-SEM. Next: operator dashboard or failure prediction." — real sind F-SEM, F-PRED, F-REC, F7-MCP, F5-Dashboard, die **komplette FE-Serie (A/B/C/D/E/H/I/J)** und **Sektion I** in `main`.
- `README.md` §Testing: „Current state (main, F2–F6): ~370 tests" — real deutlich mehr (allein FE Vitest 633).
- **Warum nicht geändert:** Es ist eine kuratierte öffentliche Fortschritts-Narrative; *was* als „Next" genannt wird und die exakten Zahlen sind Patrics/Lenas Darstellungs-Entscheidung (und Zahlen veralten je Commit). Unterschätzt den Stand (kein Falsch-Überschuss wie bei „FIVE REASONERS"), daher niedrige Dringlichkeit.
- **Empfehlung:** Status auf „F5-FE komplett (alle Sektionen) + Sektion I + MCP in main; offen: G-Anzeige, F4-Overlay, Reasoner #4, Härtung/Deploy" aktualisieren; Testzahl auf den realen Stand oder auf „siehe CI-Badge" umstellen.

### B2 — Designstudie: Charting-Bibliotheks-Prämisse vs. bespoke-SVG-Build
- `FOREMAN_Designstudie_Frontend.md` argumentiert mehrfach (Z.32, §5.1 Z.513–533, Anhang Z.658) für eine „spezialisierte Charting-Bibliothek" / „kuratierte Komponentenbasis". Der reale Build nutzt **bespoke token-getriebenes SVG** (keine Charting-Lib, kein shadcn).
- **Warum nicht geändert:** Das ist die *ursprüngliche Empfehlung* der Designstudie (Forschungs-/Entscheidungsdokument), keine punktuelle Falschaussage; eine Korrektur zöge die ganze React-vs-Angular-/Charting-Analyse mit und liegt außerhalb des #5-Scopes.
- **Empfehlung:** Lena entscheidet, ob die Designstudie eine kurze Notiz „Build-Abweichung: bespoke SVG statt Charting-Lib (siehe GROUND_TRUTH §21)" erhält oder als historischer Stand bleibt.

### B3 — Designstudie [VISION]-Marker (Sektion I) — geprüft, **bewusst belassen**
- `FOREMAN_Designstudie_Frontend.md` führt I unter [VISION] (§4I + Anhang Z.658 „A/F/G/I [VISION]"). Sektion I ist gebaut.
- **Bewertung:** Kein toter Marker. GROUND_TRUTH §21.16/§21.17 stellt explizit klar: §4I (volles Multi-System-Bild) ist **[VISION]**; gebaut ist die **ehrlich abgeleitete Teilmenge** ([STEHT]). Die Designstudie beschreibt das volle Zielbild — bleibt korrekt [VISION]. **Keine Änderung.** (Zur Entscheidung vorgelegt, falls Lena die Designstudie dennoch synchronisieren will.)

### B4 — Verwaiste Backup-Datei
- `docs/~WALKTHROUGH.md.saved.bak` (untracked) enthält noch den alten „Fünf spezialisierte"-Stand. Wurde **nicht** committet und **nicht** gelöscht (von einem früheren Tool/Editor angelegt, nicht von diesem PR).
- **Empfehlung:** löschen (`rm docs/~WALKTHROUGH.md.saved.bak`) — gehört nicht ins Repo.

### B5 — Öffentliche Showcase-Seite (gh-pages, außerhalb dieses PR)
- Laut NEXUS-Spur zeigt die GitHub-Pages-Seite (`gh-pages`-Branch, `index.html`) noch „5 Reasoner". Dieser PR liegt auf `chore/cleanup-post-i` von `main` — der `gh-pages`-Branch ist **nicht** im Arbeitsbaum.
- **Empfehlung:** separater `gh-pages`-Fix (Lena) — zusammen mit der externen Pitch-Doku (Pitch-Deck, Projektzusammenfassung, Interview-Briefing), die laut Prompt ohnehin außerhalb des Repos von Lena korrigiert wird.

### B6 — insights-hub.tsx: interne Bezeichner (kein User-sichtbarer Text)
- Header-Kommentar + Typ `ReasonerEntry` gruppieren D/E/F/G weiterhin lose unter „Reasoner". Das ist **interner Code**, nicht im UI sichtbar.
- **Warum nicht geändert:** chirurgische-Change-Disziplin (User-sichtbarer G-Titel/Blurb ist korrigiert). Eine Umbenennung des Typs würde nur Identifier-Churn erzeugen.
- **Empfehlung:** optional beim separaten G-FE-Bau mitziehen.

---

## Offen nach Merge (nicht in diesem PR — zur Erinnerung)
Lena zieht den Sprintpfad nach (#5 als MCP-Fähigkeit, 4 Reasoner, G als Anzeige) und korrigiert die externe Pitch-Doku + gh-pages. Danach: G-Dashboard (Lastprofil-**Anzeige**), F4-Eigenprofil-Overlay, Reasoner #4 (datenabhängig), Härtung/Deploy, F8.

> Dieser Report ist ein transientes Audit-Artefakt. Kann nach dem Merge entfernt werden (oder vor dem Merge aus dem Commit genommen werden, falls er nicht in `main` landen soll).
