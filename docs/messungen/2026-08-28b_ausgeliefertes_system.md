# Die Archiv-Suche, wie sie ausgeliefert wird

**Datum:** 28.08.2026 · **Register:** C-096, C-097 (Bewertungssatz: C-099) · **Freigabe:** intern
**Berichtsform:** MBRC 1.0 · **Rohdaten:** `tools/archiv_guete/ausgeliefert_2026-08-28/`

---

## Kurzfassung

Erste vollständige Erhebung der Archiv-Suche in der Zusammenstellung, die
tatsächlich ausgeliefert wird: Snowflake Arctic v2.0 lokal, Grenzwert 0,75,
Ausgabelänge 15, vier Quellen mit `substrate_k = 5`.

Gerechnet gegen den **erweiterten** Bewertungssatz: 216 beurteilte Paare, 119
zutreffend (C-099). Von den 125 ausgelieferten Plätzen sind nur noch 16
unbeurteilt.

**Drei Befunde:**

1. **Keine Anfrage geht leer aus.** 0 von 10 ohne zutreffenden Treffer, in
   beiden Zusammenstellungen. Ranggüte 0,625 (drei Quellen) und 0,677 (vier).
2. **Ob die vierte Quelle trägt, ist nicht entschieden.** Ranggüte +0,052
   (p = 0,145), Trefferquote +0,057 (p = 0,094), verdichtet +0,060 (p = 0,086).
   Alle drei zeigen in dieselbe Richtung, keiner erreicht das Niveau.
3. **Sie kostet das Neunfache an Zeit.** Median 0,097 s → 0,853 s je Suche. Das
   war bis heute nicht beziffert — und ist der eindeutigere der beiden Werte.

**Freigabe-Bedingung 1 bleibt verfehlt** — zwei Anfragen (B07, B09) verlieren
Treffer. Die zweite Bedingung ist mit 60 % erfüllt.

**Vorbedingung, die dieser Erhebung vorausging und selbst ein Befund ist:** Der
am 28.08. erhobene Grenzwert 0,75 war in der laufenden Instanz **nicht wirksam**.
Eine Dienst-Variable `FOREMAN_ARCHIVE_VECTOR_MAX_DISTANCE = 0.60` überstimmte
ihn. Die ausgelieferte Suche lief also in genau der Einstellung, bei der sechs
von zehn Anfragen nichts Zutreffendes liefern. Erst nach dem Entfernen der
Variable und einem erzwungenen Rollout misst dieser Bericht das System, das
gemeint war.

---

## 1. Aufbau

### 1.1 Die gemessene Zusammenstellung

Alle Werte stammen aus der Konfiguration der laufenden Instanz, keiner aus dem
Messwerkzeug — ein zweitgeschriebener Parameter wäre eine zweite Wahrheit.

| | |
|---|---|
| Einbettungsmodell | `Snowflake/snowflake-arctic-embed-l-v2.0`, lokal, CPU |
| Grenzwert | 0,75 (C-091), **wirksam geprüft** |
| Ausgabelänge | k = 15 |
| Vierte Quelle | eingeschaltet, `substrate_k = 5` |
| Bestand | 205 Notizen, Simulations-Adapter |
| Threadgrenze | 16 (C-095) |

### 1.2 Die beiden Arme

| Arm | Quellen |
|---|---|
| **drei Quellen** | `note`, `maintenance`, `alarm` |
| **vier Quellen** | dieselben plus `memory` (Gedächtnis) |

Derselbe Bestand, dasselbe Modell, derselbe Grenzwert, dieselbe Ausgabelänge.
Variiert wird ausschliesslich die vierte Quelle.

### 1.3 Wie erhoben

`search_archive` unmittelbar im Betriebsbehälter gerufen — derselbe Produktcode,
den die Schnittstelle benutzt. Die Trefferlisten wurden **roh** abgelegt, im
Format von `miss.py`, und mit `werte_aus.py` aus dem Repository gerechnet. Kein
Zwischenwert wurde von Hand übertragen.

Kein Fehler in 20 Anfragen.

---

## 2. Güte

| | drei Quellen | vier Quellen |
|---|---|---|
| Trefferquote | 0,558 | **0,615** |
| Präzision | 0,541 | 0,537 |
| Ranggüte | 0,625 | **0,677** |
| Ranggüte verdichtet | 0,633 | **0,693** |
| Anfragen ohne zutreffenden Treffer | **0 von 10** | **0 von 10** |
| ausgelieferte Plätze | 112 | 125 |
| davon unbeurteilt | **5** | **16** |

Die Pool-Verzerrung, die alle früheren Zahlen dieses Tages getragen hat, ist
damit weitgehend weg: 5 von 112 unbeurteilten Plätzen statt 64.

### Trägt der Unterschied?

Gepaarter exakter Permutationstest, zweiseitig, n = 10:

| Kennzahl | Differenz | p |
|---|---|---|
| Trefferquote | +0,057 | 0,094 |
| Ranggüte | +0,052 | 0,145 |
| Ranggüte verdichtet | +0,060 | 0,086 |

**Nicht gezeigt — in keiner der drei.** Alle zeigen dieselbe Richtung, keine
erreicht das Niveau. Bei zehn Anfragen ist das kein Widerspruch, sondern die
Grenze der Erhebung (Dinçer 2013: 10 bis 722 Topics je Systempaar). Was hier
fehlt, sind **Anfragen**, nicht Urteile.

*Gegen den kleineren Bewertungssatz sah es anders aus: Ranggüte +0,092 bei
p = 0,023, also gezeigt. Die neuen Urteile haben vor allem den Arm ohne
Gedächtnis gehoben — er fand schon vorher Zutreffendes, es war nur nicht
beurteilt.*

### Freigabe-Bedingung 1 (GROUND_TRUTH §15.10)

| Bedingung | Ergebnis |
|---|---|
| (1) keine gesunkene Trefferquote | **nicht erfüllt** — B07 und B09 verlieren Treffer |
| (2) mindestens 30 % mit Zusatztreffer | erfüllt (60 %) |
| **insgesamt** | **nicht erfüllt** |

Zwei Anfragen kippen sie. Das ist die Wirkung der Bedingung, nicht ihr Fehler:
Sie fragt nicht nach dem Mittel, sondern danach, ob jemand etwas verliert.

---

## 3. Antwortzeit — und was die vierte Quelle kostet

Der erste Aufruf lädt das Modell und ist aus der Verteilung genommen.

| | n | Median | kleinster | grösster |
|---|---|---|---|---|
| drei Quellen | 9 | **0,097 s** | 0,083 s | 0,151 s |
| vier Quellen | 10 | **0,853 s** | 0,356 s | 5,883 s |

**Faktor 9 im Median.** Die drei eigenen Quellen liegen in derselben Datenbank;
die vierte ist ein Netzaufruf an eine Gegenstelle. Der grösste Wert (5,883 s)
ist der erste Aufruf gegen diese Gegenstelle, also der Verbindungsaufbau.

Das ist der Preis, der bisher nirgends stand. Er gehört neben den Gewinn — und
das Verhältnis ist unbequem: **+0,756 s je Suche, eindeutig gemessen, gegen
+0,052 Ranggüte, die bei zehn Anfragen nicht zu belegen ist.**

Ob dieser Tausch richtig ist, entscheidet der Einsatz und nicht die Messung. An
einer Maschine, an der ein Werker wartet, ist eine Sekunde etwas anderes als in
einer Auswertung.

---

## 4. Was dieser Bericht nicht entscheidet

**Die Pool-Verzerrung ist weitgehend behoben, aber nicht ganz.** 5 von 112
beziehungsweise 16 von 125 Plätzen sind unbeurteilt. Der Rest fällt auf die
vierte Quelle: Sie bringt Einträge mit, die der Bewertungssatz noch nicht
führt — dasselbe Muster, nur kleiner.

**Was jetzt fehlt, sind Anfragen und nicht Urteile.** Zehn tragen eine
Richtungsaussage, keine Kennzahl mit Vertrauensbereich. Alle drei Kennzahlen der
vierten Quelle zeigen nach oben und keine erreicht das Niveau — das ist die
Signatur einer zu kleinen Stichprobe, nicht die eines fehlenden Effekts.

**Anfrage B01 ist beantwortbar.** Sie galt seit dem 27.08.2026 als nicht
beantwortbar, weil der Beurteiler damals alle 19 Pool-Einträge verworfen hatte.
Unter den am 28.08. neu beurteilten war der passende: `note:143` — *„Lager an
AX-03 geprüft, sind in Ordnung. Das Problem liegt woanders. Unten tropft
Schmierstoff aus der Achse."*, Stufe 2. „Nicht beantwortbar" war eine
Eigenschaft der Lücke, nicht des Bestands (C-099).

**Der Bestand ist Simulationsdaten.** Alle Zahlen gelten für ihn.

**Ein Beurteiler**, und er ist der Erbauer des Systems. Verdeckt beurteilt,
paarweise, ohne Kenntnis davon, welche Zusammenstellung einen Eintrag
hochgespült hat — aber ohne Übereinstimmungsquote und ohne Kappa.

---

## 5. Was daraus folgt

**Die Kalibrierung muss im Betrieb ankommen, nicht nur im Quelltext.** Der Fund
zu Beginn dieses Berichts ist der wichtigste: Ein erhobener Wert, den eine
Umgebungsvariable überstimmt, ist wirkungslos — und nichts meldet das. Seit dem
28.08.2026 trägt `config.py` allein; geprüft wurde es an der laufenden
Anwendung, nicht an der Absicht.

**Die vierte Quelle braucht mehr Anfragen, nicht mehr Urteile.** Ihr Preis ist
beziffert und eindeutig (+0,756 s je Suche); ihr Gewinn zeigt in allen drei
Kennzahlen nach oben, ist aber bei zehn Anfragen nicht zu belegen. Das ist der
Punkt, an dem der Bewertungssatz wachsen muss statt der Urteilsdichte.

**Freigabe-Bedingung 1 bleibt offen** und hängt an zwei Anfragen (B07, B09).
Die Erweiterung des Bewertungssatzes hat sie nicht aufgelöst — sie hat die Frage
nur schärfer gestellt: Beide verlieren jetzt Treffer, die als zutreffend BELEGT
sind, nicht bloss unbeurteilte.
