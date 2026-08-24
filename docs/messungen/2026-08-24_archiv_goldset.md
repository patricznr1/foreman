# Messbericht — Güte der Archiv-Suche und die vierte Quelle

**Stand:** 2026-08-24 · **Gemessen gegen:** laufende Demo-Instanz (`frontend-production-169a`)
**Code-Stand:** `main` = `8f341ed` · **Status:** intern, nicht freigegeben

> Dieser Bericht hält fest, was gemessen wurde und wie. Die daraus abgeleiteten
> Aussagen stehen im Aussagen-Register als **C-047** bis **C-050**; was hier steht
> und dort nicht, geht nicht nach draussen.

---

## 1. Anlass

`GROUND_TRUTH.md` §15.10 führt als **Freigabe-Bedingung 1** für das Gedächtnis als
vierte Archiv-Quelle einen Bewertungssatz mit zwei Schwellen:

> auf keiner Anfrage schlechter als die Baseline, auf ≥ 30 % ein zusätzlicher
> relevanter Treffer

Dazu vermerkt derselbe Abschnitt: *„Im Bestand liegt dafür nichts — keine
Anfrageliste, kein Messskript, keine Baseline-Zahl."* Genau diese drei Stücke
entstehen hier.

## 2. Aufbau

### 2.1 Bestand

36 Freitext-Einträge der laufenden Instanz, über die API gelesen und als Datei
abgelegt (`bestand_flach.json`) — nicht abgetippt, nicht aus den Szenariodateien
abgeleitet:

| Quelle | Anzahl |
|---|---|
| Schichtnotizen | 14 |
| Wartungsvorgänge | 16 |
| Alarme | 6 |

12 Maschinen in fünf Klassen, Zeitraum 04.06.–22.06.2026 (19 Tage).

### 2.2 Anfragen

18 Anfragen, so formuliert, wie ein Meister sie eintippt — nicht im Wortlaut des
gesuchten Eintrags. Gruppen: Symptom-sucht-Ursache · wiederkehrendes Muster ·
Kette über mehrere Maschinen · Bewertung einer Massnahme · maschinenbezogen mit
hartem Filter · **eine Kontroll-Anfrage** ohne Entsprechung im Bestand.

Die Kontroll-Anfrage ist kein Beiwerk. Ohne sie misst der Aufbau nur, ob *mehr*
Treffer kommen, nicht ob sie stimmen.

### 2.3 Relevanz

Getrennt von der Anfrageformulierung durch **drei voneinander unabhängige
Beurteiler** mit verschiedenem Blickwinkel (Instandhalter · Zuverlässigkeits-
ingenieur · strenger Prüfer), je Zuordnung Stufe 1 (trägt bei) oder 2 (beantwortet).
Aufgenommen ab zwei von drei Stimmen.

**Ergebnis:** 79 Zuordnungen über 17 Anfragen. Von 82 genannten Zuordnungen
trugen 71 alle drei — **86,6 % Übereinstimmung**. Die Kontroll-Anfrage liessen
alle drei leer.

Der Aufwand hat einen Grund: Ein Bewertungssatz aus einem einzigen Urteil misst
dieses Urteil mit. Die Übereinstimmungsquote ist deshalb selbst eine Kennzahl.

### 2.4 Werkzeug

Zwei getrennte Schritte, damit kein Zwischenwert aus dem Kopf in eine Kennzahl
wandert:

- `miss.py` — fährt jede Anfrage gegen `GET /api/v1/archive/search` und legt die
  Trefferlisten **roh** ab. Rechnet nichts. Ein Fehler wird mitgeschrieben und
  geht **nicht** als „keine Treffer" durch.
- `werte_aus.py` — rechnet Trefferquote, Genauigkeit und Ranggüte (k=10) aus den
  Rohdateien gegen den Bewertungssatz und prüft beide Schwellen aus §15.10.

## 3. Kontrollpunkt vor der Messung

Bevor eine Baseline gilt, muss feststehen, dass der Prüfling arbeitet. Sechs
Anfragen mit reinen Sinnverwandten, die im Bestand **nirgends wörtlich** stehen,
gegen zwei wörtliche Gegenproben:

| Anfrage | Art | Ergebnis bei Schwelle 0,55 |
|---|---|---|
| Lärm · Krach · brummt · quietscht · Schleifgeräusch · unrund | sinnverwandt | **alle leer** |
| singt | wörtlich (Notiz 2) | trifft |
| mahlen | wörtlich (Notiz 3) | trifft |

**Befund:** Der bedeutungsbasierte Zweig trug nicht. Die Suche arbeitete faktisch
als reine Volltextsuche. Kein Fehler, kein Log, keine Meldung — die dokumentierte
Rückfallebene griff still.

Die Ursache lag **nicht** am Einbettungsdienst: Die Betriebsprotokolle zeigen
`embed backend=openai` mit 130–250 ms und HTTP 200 für jede Anfrage. Die Anfrage
wurde eingebettet, ihr Ergebnis fiel durch die Ähnlichkeitsschwelle.

## 4. Kalibrierung der Ähnlichkeitsschwelle

`FOREMAN_ARCHIVE_VECTOR_MAX_DISTANCE` stand auf `0.55`, im Code ausdrücklich als
*„konservativer Start, auf Realdaten ohne Redeploy justierbar"* bezeichnet — also
nie gemessen. Fünf Werte gefahren, je Wert ein vollständiger Lauf über alle 18
Anfragen:

| Schwelle | Trefferquote | Genauigkeit | Ranggüte | Anfragen ohne Treffer | Rauschen auf der Kontroll-Anfrage |
|---|---|---|---|---|---|
| 0,55 (Ist) | 0,185 | 0,502 | 0,306 | 6 von 17 | 1 |
| **0,60** | **0,256** | **0,415** | **0,372** | **4 von 17** | 5 |
| 0,65 | 0,319 | 0,300 | 0,418 | 3 von 17 | 6 |
| 0,75 | 0,345 | 0,243 | 0,426 | 3 von 17 | 10 |
| 0,95 | 0,365 | 0,283 | 0,445 | 2 von 17 | 10 |

**Gewählt: 0,60.** Trefferquote +38 %, Ranggüte +22 %, Genauigkeit bleibt über 0,4.
Ab 0,65 fällt die Genauigkeit unter ein Drittel — dann sind zwei von drei
Treffern unbrauchbar, und die Kontroll-Anfrage füllt sich mit Rauschen.

Der Befund ist allgemeiner als der Zahlenwert: Eine zu strenge Schwelle meldet
nichts. Ihr Ausfall sieht von aussen aus wie ein leeres Archiv, nicht wie ein
Defekt.

## 5. Ausgangsmarke

Bei justierter Schwelle, drei eigene Quellen, k=10:

```
Trefferquote  0,256      Genauigkeit  0,415      Ranggüte  0,372
Antwortzeit   0,43 s     ohne Treffer 4 von 17
```

Wiederkehrendes Muster in den Fehlschlägen: **deutsche Wortzusammensetzung.** Die
Volltextsuche zerlegt sie nicht, der bedeutungsbasierte Zweig deckt nur Notizen ab.

| Anfrage | im Bestand vorhanden | gefunden |
|---|---|---|
| „Verschleiss" (Maschine 8) | Alarm „Werkzeug**verschleiss** vermutet" | nein |
| „Schmierung" (Maschine 2) | Wartung „Nach**schmierung** Achslager" | nein |
| „falsches Schmierfett eingesetzt" | Wartung „Mehrzweck**fett** … nicht spezifikationskonform" | nein |
| „Ausschuss gestiegen seit heute" | Alarm „**Ausschuss**rate über Warnschwelle" | nein |

## 6. Die vierte Quelle

Schalter `FOREMAN_ARCHIVE_SUBSTRATE_ENABLED` auf `true`, unmittelbarer Vergleich
gegen dieselbe Ausgangsmarke:

| | ohne Gedächtnis | mit Gedächtnis |
|---|---|---|
| Trefferquote | 0,256 | 0,256 (=) |
| Genauigkeit | 0,415 | **0,223** |
| Ranggüte | 0,372 | **0,266** |
| Antwortzeit | 0,43 s | **2,40 s** |

```
Anfragen mit zusätzlichem zutreffendem Treffer : 0 = 0,0 %   (gefordert ≥ 30 %)
Anfragen mit verschlechterter Reihenfolge      : 11 von 18

FREIGABE-BEDINGUNG 1: NICHT ERFÜLLT
```

**Der Schalter wurde nach der Messung wieder ausgeschaltet und das geprüft.**

### 6.1 Warum — die Ursache liegt im Inhalt, nicht im Verfahren

Eine Erinnerung aus dem Gedächtnis sieht so aus:

> `Wartung (lubrication) an Maschine 1 durchgeführt (2026-06-06T17:03:51+00:00).`

Der Vorgangsgrund fehlt. Im Bestand lautet die zugehörige Beschreibung:

> *Nachschmierung Achslager AX-02 mit Schmierstoff Y (Mehrzweckfett NLGI 2,
> Grundöl ISO VG 46) — Grundölviskosität zu niedrig für Drehzahl/Last, NICHT
> spezifikationskonform.*

Das ist die Antwort auf die Frage, warum AX-02 lauter wird. Sie steht nicht im
Gedächtnis.

Zwei belegte Gründe:

1. **Von sieben Formulierungsbausteinen führt nur einer echten Freitext.**
   `_worker_note` nimmt den Notiztext mit (seit 24.08.2026); die übrigen sechs
   geben allein die Struktur wieder — Code, Typ, Zeitpunkt.
2. **Schichtnotizen waren zum Messzeitpunkt gar nicht gespiegelt.** Die
   Verteilung in `semantic_events` der laufenden Instanz:

   ```
   maintenance_performed      32
   failure_recommendation     12
   alarm_raised               12
   event_chain_reconstructed   9
   worker_note                 0
   ```

   Der Dual-Write dafür kam mit demselben Merge; die 14 Bestandsnotizen haben
   keine Zeile, weshalb auch `backfill.py` nicht greift — es wählt
   `substrate_ref IS NULL`, und es existiert nichts zum Auswählen.

Damit ist die Bedingung nicht widerlegt, sondern **noch nicht prüfbar**.

### 6.2 Zustand des Gedächtnisses

| | |
|---|---|
| Erinnerungen im FOREMAN-Bereich | 63 (0 flüchtig · **62 formbar** · 1 gefestigt) |
| Art | durchweg `observation` |
| Wissensnetz | 1 von 63 verarbeitet → 26 Gegenstände, 12 Sachverhalte; seither „nichts zu tun" |
| Einbettung | `arctic` / `snowflake-arctic-embed-l-v2.0`, 1024 Stellen — **aktiv** |

Die Verdichtung hat also praktisch nicht stattgefunden. Das ist ein zweiter, vom
Inhaltsproblem unabhängiger Punkt: Material, das nur aus Strukturzeilen besteht,
gibt einer Verdichtung auch wenig zu tun.

## 7. Grenzen dieser Messung

Ehrlich benannt, weil sie das Ergebnis begrenzen:

1. **Kein Vorgang wiederholt sich.** Der Bestand umfasst 19 Tage; jede
   Störungsgeschichte kommt genau einmal vor. Die Frage „hatten wir das schon
   mal" hat in diesem Bestand keine Antwort — unabhängig davon, wie gut das
   Gedächtnis arbeitet.
2. **Die maschinenübergreifende Stichprobe ist eins.** Drei Anfragen zielen auf
   die Kette FD-02 → PR-02 → VS-01, alle auf denselben Vorfall vom 08.06. Wird
   diese Kette gut oder schlecht gefunden, bewegen sich drei Anfragen gemeinsam.
3. **Acht der 18 Anfragen sind lexikalisch nah am Zieltext.** Sie können nicht
   zeigen, ob eine zusätzliche Quelle beiträgt.
4. **Über die Alarmquelle sagt die Messung wenig.** Nur eine Anfrage ist
   alarmgetrieben, und sie zitiert den Alarmtext wörtlich.
5. **Die Deckenwirkung bei Maschinenfilter-Anfragen.** Bei vier bzw. drei
   Kandidaten und k=10 ist die Trefferquote dort wenig aussagekräftig.

Punkt 1 ist der schwerwiegendste und mit einem besseren Anfragesatz **nicht**
heilbar — er verlangt mehr und wiederkehrendes Material im Bestand.

## 8. Nachvollziehen

```bash
python miss.py baseline note,maintenance,alarm && python werte_aus.py messung_baseline.json
```

Ein Lauf über alle 18 Anfragen dauert rund 30 Sekunden. Für einen Vergleich:

```bash
python werte_aus.py messung_cut060.json messung_mit_gedaechtnis.json
```

## 9. Was als Nächstes gemessen wird

Sobald die Erinnerungen beschreibenden Text führen, wird Abschnitt 6 mit
demselben Anfragesatz wiederholt. Bis dahin bleibt die vierte Quelle
ausgeschaltet und die Freigabe-Bedingung offen.
