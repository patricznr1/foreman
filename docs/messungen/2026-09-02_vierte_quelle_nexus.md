# Die vierte Quelle nach den NEXUS-Änderungen

**Datum:** 02.09.2026 · **Register:** C-105 bis C-108 (Bewertungssatz: C-099) · **Freigabe:** intern
**Berichtsform:** MBRC 1.0 · **Rohdaten:** `tools/archiv_guete/messung_nexus_2026-09-02_*.json`
**Vormessung:** [`2026-08-28b_ausgeliefertes_system.md`](2026-08-28b_ausgeliefertes_system.md)

---

## Kurzfassung

**Anlass.** Zur Vormessung vom 28.08.2026 war das Gedächtnis-Substrat nach eigener
Einschätzung nicht sauber angebunden; seither gab es einen Neuspiegel-Lauf (C-103, C-104)
und Änderungen auf der NEXUS-Seite. Die Frage lautete, ob sich die Aussage über die vierte
Quelle dadurch ändert.

**Sie ändert sich nicht.**

| Kennzahl | drei Quellen | vier Quellen | Differenz | Vormessung 28.08. |
|---|---|---|---|---|
| Trefferquote | 0,558 | 0,609 | **+0,051** (p = 0,172) | +0,057 (p = 0,094) |
| Ranggüte | 0,625 | 0,678 | **+0,053** (p = 0,180) | +0,052 (p = 0,145) |
| Ranggüte verdichtet | 0,633 | 0,692 | **+0,059** (p = 0,109) | +0,060 (p = 0,086) |
| Genauigkeit | 0,541 | 0,530 | −0,011 | — |

**Vier Befunde:**

1. **Die Richtung stimmt, der Nachweis fehlt weiterhin.** Alle drei Kennzahlen steigen,
   keine erreicht das Niveau. Die Werte liegen innerhalb eines Wimpernschlags zu denen vom
   28.08. — die NEXUS-Änderungen haben an der messbaren Güte **nichts** bewegt.
2. **Freigabe-Bedingung 1 bleibt verfehlt.** Zwei Anfragen verlieren zutreffende Treffer:
   B07 (`note:185`) und B09 (`note:71`, `note:108`) — **dieselben zwei wie am 28.08.**
   Die zweite Bedingung ist mit 50 % erfüllt (Schwelle 30 %; am 28.08. waren es 60 %).
3. **Das Gedächtnis liefert 18 % der Plätze exklusiv.** Von 125 ausgelieferten Plätzen
   werden 50 (40 %) auch vom Gedächtnis gefunden, **22 (18 %) ausschließlich** von ihm.
   Zahlengleich zur Vormessung.
4. **Sie kostet weiterhin ein Vielfaches an Zeit,** aber weniger als zuvor:
   Median 0,300 s → 1,060 s, Faktor **3,5**. Am 28.08.: 0,095 s → 0,829 s, Faktor 8,7.
   Der Faktor sinkt, weil die **Basis** langsamer geworden ist, nicht die vierte Quelle
   schneller (1,060 s gegen 0,829 s).

**Damit ist die Frage beantwortbar:** Die vierte Quelle bringt zusätzliche zutreffende
Treffer auf der Hälfte der Anfragen und trägt 18 % der Plätze allein. Sie verdrängt aber
weiterhin zutreffende Treffer auf zwei von zehn Anfragen, und der Mittelwertunterschied ist
bei zehn Anfragen nicht nachweisbar. **Für eine Freigabe reicht das nicht; für die Aussage
„sie trägt etwas bei, das die eigenen Quellen nicht haben" reicht es.**

---

## 1. Aufbau

### 1.1 Die gemessene Zusammenstellung

| | |
|---|---|
| Instanz | `https://frontend-production-169a.up.railway.app`, Stand `3a11968` |
| Bewertungssatz | `goldset_v2_anfragen.yaml` (10 Anfragen) gegen `goldset_v3.json` |
| Ausgabelänge | k = 15 |
| Rolle | `manager` |
| Erhebung | `tools/archiv_guete/miss.py`, Auswertung `werte_aus.py` |

**Nicht belegt:** Grenzwert, `substrate_k` und Einbettungsmodell der laufenden Instanz
konnten für diesen Bericht **nicht** aus dem Prozess gelesen werden — der Railway-Zugang
stand nicht zur Verfügung. Sie werden hier deshalb **nicht** wiederholt. Dass die vierte
Quelle wirksam war, ist funktional belegt (siehe 1.2), nicht über die Konfiguration.

### 1.2 Kontrollpunkt: war die vierte Quelle überhaupt an?

Die Gefahr dieser Messung ist ein stiller Schalter: Steht
`FOREMAN_ARCHIVE_SUBSTRATE_ENABLED` auf `false`, misst der zweite Lauf dasselbe wie der
erste und die Messung meldet null Zusatztreffer — was sich wie ein Urteil liest, aber ein
Verdrahtungsfehler wäre.

**Belegt, dass sie an war:** Die Trefferzahlen unterscheiden sich zwischen den Armen
(B03 4 → 7, B04 4 → 8, B06 8 → 13), die Herkunftsangabe `gefunden_von` weist 50 Plätze mit
`memory` aus, und 22 Plätze tragen `memory` als **einzige** Quelle.

### 1.3 Wiederholbarkeit

Der Gedächtnis-Arm wurde **zweimal** erhoben
(`…_gedaechtnis.json`, `…_gedaechtnis_wdh.json`). Die Auswertung beider Läufe gegen dieselbe
Basis ist **zeilengleich**: dieselben Zusatztreffer, dieselben Verluste, dieselben
Kennzahlen. Innerhalb eines Messfensters ist das Verfahren deterministisch.

---

## 2. Ergebnis je Anfrage

| ID | Trefferquote | Ranggüte | neue zutreffende Treffer | verlorene |
|---|---|---|---|---|
| B01 | 1,00 → 1,00 | 0,92 → 0,89 | — | — |
| B02 | 0,27 → **0,36** | 0,43 → 0,54 | `note:145` | — |
| B03 | 0,50 → **0,67** | 0,67 → 0,83 | `maintenance:107` | — |
| B04 | 0,09 → **0,27** | 0,14 → 0,38 | `maintenance:43`, `maintenance:92` | — |
| B05 | 0,60 → 0,60 | 0,75 → 0,75 | — | — |
| B06 | 0,25 → **0,42** | 0,28 → 0,43 | `maintenance:44`, `maintenance:71` | — |
| B07 | 0,63 → **0,58** | 0,80 → 0,78 | — | **`note:185`** |
| B08 | 0,90 → 0,90 | 0,83 → 0,83 | — | — |
| B09 | 0,50 → **0,38** | 0,58 → 0,45 | — | **`note:71`, `note:108`** |
| B10 | 0,83 → **0,92** | 0,84 → 0,90 | `maintenance:58` | — |

- mit Zusatztreffer: **5 von 10 (50 %)** → Bedingung 2 erfüllt
- mit Verlust: **2 von 10** → Bedingung 1 **nicht** erfüllt
- unverändert: 3
- ohne einen zutreffenden Treffer: **0 von 10** in beiden Armen

**Bemerkenswert:** Alle sechs neu gewonnenen Treffer sind **Wartungsvorgänge**
(`maintenance:*`, fünf von sechs) — alle drei verlorenen sind **Schichtnotizen** (`note:*`).
Die vierte Quelle verschiebt das Ergebnis systematisch von Notizen zu Wartungsberichten.
Das ist kein Zufallsrauschen und im Register bislang nicht erfasst.

---

## 3. Vergleich mit der Vormessung — misst das überhaupt frisch?

**C-104 hält fest, dass Messungen vor und nach dem Neuspiegel-Lauf nicht vergleichbar sind,**
weil sich jeder gespiegelte Satz geändert hat, und fordert genau diese Erhebung an
(„Die Guete-Messung steht aus und kann erst nach diesem Lauf erhoben werden"). Der Einwand
ist berechtigt und wird hier nicht übergangen: Ein Vergleich der **Kennzahlen** über den Lauf
hinweg wäre unzulässig, wenn sich die Trefferlisten darunter beliebig verschoben hätten.

Deshalb wurde zuerst geprüft, **ob** sie sich verschoben haben — und sie haben es:

Weil die Aggregate denen vom 28.08. so nahe liegen, wurde geprüft, ob beide Läufe
dieselbe zwischengespeicherte Antwort gesehen haben könnten. **Nein:**

| Vergleich 28.08. → 02.09. (Gedächtnis-Arm) | Anfragen |
|---|---|
| identische Liste inkl. Reihenfolge | 2 von 10 |
| gleiche Menge, andere Reihenfolge | 6 |
| inhaltlich verschieden | 2 (B01 ohne `note:126`; B09 mit `note:202`) |

Die Listen bewegen sich also, die Kennzahlen bleiben stehen. **Die Stabilität ist echt,
kein Artefakt eines Zwischenspeichers.**

Damit lässt sich C-104 beantworten: Verglichen werden hier **nicht** zwei Kennzahlen über
einen Bruch hinweg, sondern es wird festgestellt, dass die Kennzahlen *trotz* des Bruchs
gleich bleiben. Das ist die zulässige Form der Aussage — und sie ist die inhaltlich
interessantere: Der Neuspiegel-Lauf hat die Sätze verändert, die Rangfolgen verschoben und
die Güte **nicht** bewegt.

---

## 4. Grenzen dieser Messung

1. **Zehn Anfragen tragen keine Kennzahl mit Vertrauensbereich.** Der Permutationstest ist
   exakt gerechnet, aber bei n = 10 reicht die Erhebung für eine Richtungsaussage, nicht für
   einen Nachweis. `p > 0,05` heißt **nicht gezeigt**, nicht „kein Unterschied".
2. **17 von 125 Plätzen des Gedächtnis-Arms sind unbeurteilt** (Basis: 5 von 112). Genau die
   Treffer, die nur die vierte Quelle liefert, sind im Bewertungssatz überdurchschnittlich
   oft ohne Urteil — die verdichtete Ranggüte trägt dem Rechnung, die einfache nicht.
3. **Die Konfiguration der Instanz ist nicht aus dem Prozess gelesen** (siehe 1.1). Ein
   Vergleich mit dem 28.08. setzt voraus, dass Grenzwert und `substrate_k` unverändert sind;
   das ist plausibel, aber hier nicht belegt.
4. **Der Bestand wiederholt sich weiterhin nicht.** Die schwerwiegendste Grenze aus dem
   Bericht vom 27.08. gilt unverändert: Die Frage „hatten wir das schon mal" hat in diesem
   Bestand kaum eine Antwort — unabhängig von der Güte der Suche.

---

## 5. Was daraus folgt

- **Die Freigabe-Bedingung ist weiterhin nicht erfüllt.** Wer sie erfüllen will, muss die
  Verdrängung angehen — nicht die Trefferzahl. Ansatzpunkt sind B07 und B09, dieselben zwei
  Anfragen wie vor fünf Tagen, und dort jeweils Schichtnotizen, die von Wartungsvorgängen
  verdrängt werden.
- **Die NEXUS-Änderungen seit dem 28.08. haben die Güte nicht verändert.** Wer sie belegen
  will, braucht eine andere Messgröße als diese — die Rückwege der gespiegelten Einträge
  (C-103/C-104) betreffen die Auflösbarkeit einer Erinnerung, nicht ihre Auffindbarkeit.
- **Für eine Aussage nach außen taugt heute:** „Die vierte Quelle steuert 18 % der
  ausgelieferten Plätze exklusiv bei und liefert auf der Hälfte der Anfragen einen
  zusätzlichen zutreffenden Treffer." Beides ist ausgezählt und reproduziert.
  **Nicht** taugt: „Sie verbessert die Suche" — das ist bei n = 10 nicht gezeigt.
