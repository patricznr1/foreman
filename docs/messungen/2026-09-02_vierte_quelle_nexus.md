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
   **Nachtrag (siehe Abschnitt 6): Alle drei verdrängenden Treffer sind unbeurteilt.**
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

---

## 6. Nachtrag vom 02.09.2026 — woran die verfehlte Bedingung gemessen ist

Der Bericht nennt in Abschnitt 5 die Verdrängung als Ansatzpunkt. Eine Nachprüfung der
Rohdaten zeigt, dass sie **so noch nicht beurteilbar ist** — und warum Bedingung 1 auf
dem heutigen Bewertungssatz durch keine Verbesserung erfüllt werden kann.

**Die drei Verdränger hat nie jemand angesehen** (C-110). Sie stehen weder in
`goldset_v3.json` noch in `beurteilt_v3.json` — auch nicht mit der Stufe 0:

| Anfrage | verliert | Rang (Basis) | an | Rang (mit Gedächtnis) | Urteil |
|---|---|---|---|---|---|
| B07 | `note:185` (Stufe 1) | 15 | `maintenance:37` | 6 | **nie beurteilt** |
| B09 | `note:71` (Stufe 2) | 14 | `maintenance:137` | 4 | **nie beurteilt** |
| B09 | `note:108` (Stufe 1) | 15 | `note:195` | 5 | **nie beurteilt** |

Alle drei Verdränger tragen einen intakten Rückweg und landen weit **vor** den Plätzen, die
sie verdrängen. Es ist der Schnitt bei k = 15, der die Notizen herausnimmt — keine
Fehlfunktion der Fusion. Ob dabei etwas verloren geht, hängt allein daran, ob die drei
neuen Treffer zutreffen. Der Maßstab wertet sie als nicht zutreffend, **weil sie fehlen**,
nicht weil jemand sie geprüft und verworfen hätte.

**Das ist kein Einzelfall, sondern die Bauart des Maßstabs** (C-109):

| Herkunft eines ausgelieferten Platzes | beurteilt | davon zutreffend |
|---|---|---|
| nur vom Gedächtnis gefunden | **8 von 22 (36 %)** | 7 von 8 |
| von einer eigenen Quelle gefunden | 100 von 103 (97 %) | 60 von 100 |

61 Prozentpunkte Abstand. Das ist die Pool-Verzerrung, die `baue_goldset_v3.py` im Kopf
zitiert (Buettcher et al., SIGIR 2007) — hier ausgezählt statt vermutet, mit
`tools/archiv_guete/pool_verzerrung.py`. Die Zahl der unbeurteilten Plätze stimmt mit
Grenze 2 dieses Berichts überein (17 im Gedächtnis-Arm, 5 in der Basis); die beiden
Rechnungen sind unabhängig entstanden.

**Der Kreisschluss:** Jeder Treffer, den nur die vierte Quelle findet, ist per Bauart
nicht im Pool — also unbeurteilt — also gewertet wie ein Fehltreffer, und er verdrängt
einen beurteilten. Je besser die vierte Quelle wird, desto sicherer verfehlt sie
Bedingung 1.

**Was daraus folgt — statt Abschnitt 5, Punkt 1:** Nicht die Verdrängung angehen, sondern
zuerst den Pool schließen. Der Bogen dafür ist erzeugt und enthält **13 Paare über sieben
Anfragen**: `tools/archiv_guete/gegenprobe/urteilsbogen_offen.txt`. Erst danach ist die
Frage entscheidbar, ob die vierte Quelle etwas verdrängt oder etwas Besseres einsetzt.

**Was dieser Nachtrag NICHT belegt:** dass die 14 unbeurteilten Treffer zutreffend wären.
Dass 7 der 8 bereits beurteilten es sind, ist ein Hinweis und keine Schätzung für die
übrigen. Die Kennzahlen des Berichts bleiben, wie sie stehen — der Nachtrag sagt nur, was
sie messen.

---

## 7. Nachtrag vom 02.09.2026, abends — der Pool ist geschlossen

Die 13 Paare aus Abschnitt 6 wurden vorgelegt und beurteilt
(`gegenprobe/relevanz_urteile_2026-09-02.txt`). Sieben davon sind zutreffend. Der
Bewertungssatz wuchs damit auf 229 beurteilte Einträge (126 zutreffend); **kein Eintrag ist
weggefallen**, und **an System und Rohdaten wurde nichts geändert** — dieselben Läufe, nur
ein vollständigerer Maßstab.

### 7.1 Die Lücke

| Herkunft eines Platzes | vorher | nachher |
|---|---|---|
| nur vom Gedächtnis gefunden | 8 von 22 (36 %) | **21 von 22 (95 %)** |
| von einer eigenen Quelle | 100 von 103 (97 %) | 100 von 103 (97 %) |
| Abstand | 61 Prozentpunkte | **2 Prozentpunkte** |

Exklusive Treffer, die zutreffen: von 7 auf **14**. (C-111)

### 7.2 Was sich am Ergebnis ändert

| Kennzahl | Abschnitt 1 (Pool offen) | **jetzt (Pool geschlossen)** |
|---|---|---|
| Trefferquote | +0,051 (p = 0,172) | **+0,139 (p = 0,031)** |
| Ranggüte | +0,053 (p = 0,180) | **+0,107 (p = 0,023)** |
| Ranggüte verdichtet | +0,059 (p = 0,109) | **+0,105 (p = 0,023)** |
| Anfragen mit Zusatztreffer | 5 von 10 (50 %) | **8 von 10 (80 %)** |
| Anfragen mit Verlust | 2 (B07, B09) | **1 (B09)** |

**Alle drei Kennzahlen erreichen jetzt das Niveau.** Der Befund aus der Kurzfassung — „die
Richtung stimmt, der Nachweis fehlt" — war eine Eigenschaft des Bewertungssatzes, nicht des
Systems. Vierzehn Treffer der vierten Quelle standen im Nenner als Fehltreffer, weil
niemand sie angesehen hatte. (C-112)

**B07 zählt nicht mehr als Verlust:** `maintenance:37` ist Stufe 2 — der Prüfbericht nennt
Umkehrspiel von 0,08 bis 0,11 mm gegen einen Sollwert von 0,02, und die Anfrage lautete
„Nullpunktverschiebung an AX". Er trat an die Stelle von `note:185` (Stufe 1); die Ranggüte
stieg dort von 0,78 auf 0,82. **B09 bleibt ein Verlust** (C-113).

### 7.3 Freigabe-Bedingung

- **(2) mindestens 30 % Zusatztreffer: ERFÜLLT** mit 80 %.
- **(1) auf keiner Anfrage ein Verlust: weiterhin NICHT ERFÜLLT** — B09.

Bei fester Ausgabelänge und einer zusätzlichen Quelle verlangt Bedingung (1), dass **jeder**
neue Treffer besser ist als der schlechteste alte. Ob sie so gemeint war, ist eine Frage an
die Bedingung; diese Messung entscheidet sie nicht.

### 7.4 Grenzen — und die wiegen hier schwerer als sonst

1. **Die Urteile sind NICHT blind gefällt.** Der Bogen wies jeden Eintrag als `[memory]`
   aus. Alle 13 Paare stammten aus derselben Quelle, es gab also keinen Gegensatz, zu dem
   hin verzerrt werden konnte — ausgeschlossen ist eine Verzerrung damit nicht. Da genau
   diese Urteile den Unterschied zwischen „nicht gezeigt" und „gezeigt" tragen, gehört das
   an jede Weitergabe der Zahl.
2. **Ein Beurteiler, kein Übereinstimmungsmaß.**
3. **Zehn Anfragen tragen keine Kennzahl mit Vertrauensbereich.** `p < 0,05` ist hier eine
   belegte Richtungsaussage, kein Effektmaß.
4. **Vier Plätze bleiben unbeurteilt** — ihre Einträge führt `goldset_v2_zuordnung.json`
   nicht, sie sind nicht beurteilbar.
5. **Grenze 4 aus Abschnitt 4 bleibt bestehen:** Der Bestand ist dünn.

**Rohauswertung:** [`2026-09-02b_rohauswertung_erweitert.txt`](2026-09-02b_rohauswertung_erweitert.txt)
