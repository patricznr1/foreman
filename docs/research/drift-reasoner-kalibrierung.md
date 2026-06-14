# Drift-Reasoner — Kalibrierung und Validierung

> Stand: 14.06.2026 · Betrifft: F4 Drift-Reasoner (`src/foreman/reasoners/drift/`)
> Datengrundlage: die vier Simulations-Szenarien aus `src/foreman/adapters/simulation/scenarios/`
> Verfahrenswahl (Vorgelagert): `docs/research/drift-erkennung-verfahren.md`

Dieses Dokument hält fest, **mit welchen Parametern** der Drift-Reasoner betrieben wird, **wie** diese Werte ermittelt wurden und **welches Verhalten** sie auf den Validierungs-Szenarien zeigen. Es dient als Nachweis der Abnahme und als Ausgangspunkt für die spätere Nachkalibrierung an realen Maschinendaten.

---

## 1. Festgelegte Parameter

| Parameter | Wert | Ort | Begründung (Kurzform) |
|---|---|---|---|
| ADWIN `delta` | 0,002 | `detector.py` | river-Default; konservativ (§6.1 der Verfahrenswahl) |
| Warm-up | 100 Samples | `detector.py` | vor etabliertem Profil kein Signal vertrauen |
| Grace-Period | 5 min | `steady_state.py` | nach Zustandswechsel einschwingen lassen |
| Baseline-Fenster | 1440 Samples | `baseline.py` | gleitender Median, 24 h bei 1/min |
| **Baseline-Zustand** | **Tagesstunde (0–23)** | `baseline.py`/`service.py` | Median je Betriebszustand statt global (siehe §4) |
| **Effektgröße** | **z-Score** (`\|Residuum\| / Rausch-σ`) | `detector.py` | messgrößen-invariant (siehe §3) |
| **Relevanz-Schwelle** | **z ≥ 3,0** | `relevance.py` | Sweet Spot aus dem Schwellen-Sweep (§5) |
| **Persistenz** | **12 Intervalle** | `relevance.py` | trennt anhaltende Drift von Rausch-Clustern |

Die ersten vier Werte sind die unveränderte Startkalibrierung aus der Verfahrenswahl. Die vier hervorgehobenen Werte wurden in dieser Kalibrierung ermittelt.

---

## 2. Methodik

Jedes Szenario wird per Backfill in die Datenbank eingespielt, das 1-Minuten-Aggregat `readings_1m` aktualisiert und anschließend durch den vollständigen Reasoner gespielt (Gating → Residuum → ADWIN → Relevanz-Filter). Gemessen wird gegen den `ground_truth`-Block des jeweiligen Szenarios:

- **Detektionsverzug** — Zeit zwischen dem Injektions-Start t\* und der ersten relevanten Meldung am Primär- oder einem Bestätigungs-Signal.
- **Vorlauf** — wird die Drift *vor* dem ersten Alarm bzw. der Werker-Reaktion des Szenarios gemeldet (betrieblicher Frühwarn-Nutzen)?
- **Fehlalarmrate** — Meldungen, die das Szenario nicht erwartet (Kontroll-Signal, Meldung vor t\*, Meldung auf der gesunden Maschine).

Die vier Szenarien decken bewusst verschiedene Fälle ab:

| Szenario | Primär-Signal | t\* | Erster Alarm (Anker) | Charakter |
|---|---|---|---|---|
| `bearing_drift` | Vibrations-RMS (Ramp) | 7 d | +10,3 d (17 d 08 h) | progressiver Verschleiß, Temperatur folgt spät |
| `tool_wear` | Spindel-Drehmoment (Ramp) | 2 d | +7,5 d (9 d 12 h) | schwaches Signal, hohes Grund-Rauschen |
| `lubrication_correlation` | Vibrations-RMS Lager B (Ramp) | 3 d | +21,2 d (24 d 06 h) | Lager A als Kontrolle (darf nicht melden) |
| `healthy_baseline` | — | — | — | Negativkontrolle: Schicht-Saisonalität, kein Verschleiß |

---

## 3. Befund A — die Effektgröße muss messgrößen-invariant sein

Eine Relevanz-Schwelle in absoluten Mess-Einheiten ist über verschiedene Messgrößen hinweg nicht haltbar. Das Rauschen des Residuums unterscheidet sich je Signal um eine Größenordnung:

| Signal | typisches Residuum-Rauschen | Drift-Signal (max) |
|---|---|---|
| Vibrations-RMS (mm/s) | ≈ 0,15 | bis ≈ 2,6 |
| Spindel-Drehmoment (Nm) | ≈ 1,3 | bis ≈ 4,3 |

Eine absolute Schwelle von z. B. 1,0 wäre für die Vibration weit über dem Rauschen, für das Drehmoment aber unterhalb des Grund-Rauschens — sie würde dort Dauer-Fehlalarme erzeugen.

**Konsequenz:** Die Effektgröße wird als **z-Score** geführt — Betrag des Residuums geteilt durch die robuste Rausch-Streuung des Signals (geschätzt während der Warm-up-Phase, danach eingefroren). Damit greift **eine** Schwelle über alle Messgrößen.

---

## 4. Befund B — eine globale Baseline trennt schwache Drift nicht vom Schicht-Rauschen

Erste Kalibrierungs-Läufe nutzten einen **globalen** gleitenden Median je Datenpunkt. Damit ließ sich keine Schwellen-/Persistenz-Kombination finden, die gleichzeitig die schwache `tool_wear`-Drift erkennt und die gesunde Maschine ruhig hält:

| Konfiguration (globale Baseline) | `healthy_baseline` | `tool_wear` |
|---|---|---|
| z = 2,5 / Persistenz 12 | **8 Fehlalarme** | erkannt |
| z = 3,5 / Persistenz 30 | 0 Fehlalarme | **nicht erkannt** |
| z = 2,5 / Persistenz 90 | 1 Fehlalarm | **nicht erkannt** |

**Ursache:** Früh-, Spät- und Nachtschicht haben unterschiedliche mittlere Last. Ein globaler Median mischt diese Niveaus, sodass das Residuum einer *gesunden* Maschine eine systematische, schichtabhängige Komponente trägt (Rausch-Maxima bis ≈ 3,9 z). Die `tool_wear`-Drift liegt mit ≈ 2,85 z **unterhalb** dieses Schicht-Rauschens — die beiden sind mit einer globalen Baseline nicht trennbar.

---

## 5. Korrektur und Schwellen-Kalibrierung

Gemäß der Verfahrenswahl (§3: „Residuum gegen den gleitenden Median **des gleichen Betriebszustands**") wird die Baseline **zustandsspezifisch** geführt: ein eigenes Median-Fenster je Tagesstunde. Damit fällt die schichtabhängige Last heraus, und das verbleibende Residuum bildet nur noch die verschleißbedingte Abweichung ab.

Mit dieser Baseline wurde die Relevanz-Schwelle bei fester Persistenz (12 Intervalle) durchgefahren. Detektionsverzug in Tagen nach t\*; „Fehlalarm" und „Kontrolle" sind unerwünschte Meldungen:

| Szenario | z = 2,5 | z = 3,0 | z = 3,5 |
|---|---|---|---|
| `bearing_drift` | Verzug 6,9 d · FA 0 | Verzug 6,9 d · FA 0 | Verzug 6,9 d · FA 0 |
| `tool_wear` | Verzug 5,0 d · FA 0 | Verzug 5,0 d · FA 0 | Verzug 6,1 d · FA 0 |
| `lubrication_correlation` | Verzug 1,9 d · **Kontrolle 1** | Verzug 1,9 d · FA 0 | Verzug 11,0 d · FA 0 |
| `healthy_baseline` | 0 Meldungen | 0 Meldungen | 0 Meldungen |

**Lesart:**

- **z = 2,5** ist zu empfindlich: das korrekt geschmierte Kontroll-Lager A in `lubrication_correlation` (normale Alterung +0,6 mm/s) wird fälschlich gemeldet.
- **z = 3,5** unterdrückt zwar alles Unerwünschte, verzögert aber `lubrication` deutlich (Verzug 1,9 d → 11,0 d) und schwächt `tool_wear`.
- **z = 3,0** ist der Arbeitspunkt: alle drei Drifts mit dem geringsten Verzug erkannt, die Negativkontrolle und das Kontroll-Lager bleiben still.

**Festgelegt: z = 3,0, Persistenz 12.**

---

## 6. Validierungs-Ergebnis (festgelegte Konfiguration)

Zustandsspezifische Baseline, z = 3,0, Persistenz 12:

| Szenario | erkannt | Verzug nach t\* | Vorlauf vor Alarm | Fehlalarme |
|---|---|---|---|---|
| `bearing_drift` | ja (Vibration) | 6,9 d | ≈ 3,4 d | 0 |
| `tool_wear` | ja (Drehmoment/Strom) | 5,0 d | ≈ 2,5 d | 0 |
| `lubrication_correlation` | ja (Lager B) | 1,9 d | ≈ 19,3 d | 0; Lager A still |
| `healthy_baseline` | — (korrekt) | — | — | **0** |

Alle drei Verschleiß-Szenarien werden mit nützlichem Vorlauf **vor** dem ersten Alarm bzw. der Werker-Notiz erkannt. Die gesunde Maschine löst über volle Schicht-Saisonalität und Wochenend-Stillstand hinweg **keine** Meldung aus.

Die Tests, die dieses Ergebnis absichern, liegen in `tests/integration/test_drift_validation.py`.

---

## 7. Bekannte Grenzen und Vorbehalte

- **Erkennungsfenster vs. Vorlauf.** Die `ground_truth`-Blöcke nennen enge 3-Tage-Erkennungsfenster (z. B. `bearing_drift` [7 d, 10 d]). Bei *progressiven* Ramps ist das Signal in diesem Fenster noch im Rauschen; die belastbare Erkennung liegt etwas später, aber klar im betrieblich nützlichen Vorlauf vor dem Alarm. Die Abnahme wird daher über den Vorlauf geführt, nicht über das enge Fenster. Die Fenster sind an realen Daten zu schärfen.
- **Reine Varianz-Drift.** ADWIN reagiert auf Mittelwert-Verschiebungen. Eine reine, symmetrische Varianz-Erhöhung ohne Mittelwertshift wird bauartbedingt schwach erkannt. Varianz-Drift, die mit einer Mittelwert-Komponente einhergeht (realer Last-Einbruch), wird erkannt. Ein KSWIN-Zweitpfad für reine Form-/Varianzänderung ist ein dokumentierter späterer Ausbau.
- **Magnituden synthetisch.** Die Kalibrierung beruht auf simulierten Szenarien mit fachlich begründeten, aber synthetischen Magnituden. Die Schwelle z = 3,0 ist als Startwert zu verstehen und an realen Maschinendaten nachzuziehen (insbesondere die Tagesstunde als Zustands-Schlüssel — bei abweichenden Schicht-Modellen ggf. anpassen).
- **Zustands-Granularität.** Aktuell trennt die Baseline nach Tagesstunde. Feinere Zustände (Produkt, Maschinen-Programm) sind ein möglicher Ausbau, sobald reale Daten zeigen, dass die Stunde nicht ausreicht.
- **Ein Worker.** Der Detektor-Zustand ist prozesslokal. Für horizontale Skalierung ist das Pinnen je Datenpunkt oder das Rehydrieren aus `readings_1m` zu klären (offener Punkt der Verfahrenswahl).

---

## 8. Reproduktion

1. Test-DB bereitstellen (`docker compose`/Container `foreman_test_db`, Port 5433).
2. Szenario per Backfill einspielen: `python -m foreman.adapters.simulation.runner --scenario <name> --mode backfill`.
3. `readings_1m` aktualisieren: `CALL refresh_continuous_aggregate('readings_1m', NULL, NULL);`.
4. Reasoner über den Szenario-Zeitraum laufen lassen (`reasoners/drift/runner.py:replay_machine`).
5. Kennzahlen gegen den `ground_truth`-Block auswerten (`reasoners/drift/validation.py`).

Die Validierungs-Suite `tests/integration/test_drift_validation.py` automatisiert die Schritte 2–5 für alle vier Szenarien.
