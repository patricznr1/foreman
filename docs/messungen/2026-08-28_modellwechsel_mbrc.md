# Der Wechsel des Einbettungsmodells, gemessen

**Datum:** 28.08.2026 · **Register:** C-092 bis C-095 · **Freigabe:** intern
**Berichtsform:** MBRC 1.0 (Memory Benchmark Reporting Checklist)
**Rohdaten:** `tools/archiv_guete/modellvergleich_2026-08-28/`, 24 Dateien mit
Prüfsummen

---

## Kurzfassung

Die Archiv-Suche lief bis zum 28.08.2026 auf `text-embedding-3-small` (OpenAI,
Cloud) und läuft seither auf `Snowflake/snowflake-arctic-embed-l-v2.0` (lokal).
Dieser Bericht misst den Wechsel gegen den eigenen Bewertungssatz.

**Drei Befunde, in der Reihenfolge ihrer Tragweite:**

1. **Eine Fehleinstellung kostete den Faktor 36 an Antwortzeit** — und wäre ohne
   diese Messung nie aufgefallen. `torch` bemisst seine Threadzahl an den Kernen
   des **Wirts** (48) statt an der Zuteilung des Behälters (24); bei einer
   einzelnen kurzen Anfrage geht die Zeit dann in die Abstimmung zwischen den
   Threads. Median 5,505 s statt 0,154 s. Behoben, siehe Abschnitt 2.
2. **Ob die Suche besser oder schlechter findet, ist mit dem heutigen
   Bewertungssatz NICHT entscheidbar.** Die gewöhnlichen Kennzahlen sprechen
   gegen Arctic, aber sie sind gegen das neue Modell verzerrt; pool-korrigiert
   gerechnet ist der Unterschied nicht gezeigt.
3. **Ein Grenzwert gehört zum Vektorraum, nicht zum Produkt.** Bei derselben
   Schwelle 0,60 liefert OpenAI 133 Treffer, Arctic 35. Die Vektoren beider
   Modelle stehen praktisch senkrecht zueinander.

**Was daraus folgt:** Der Satz „wir sind gewechselt, weil die Suche besser wird"
ist nicht belegbar — die Güte ist nicht unterscheidbar. Belegbar sind
Betriebs- und Rechtsgründe: Apache-2.0 statt US-Drittland, Betrieb beim Kunden
ohne Cloud-Anbindung, keine Kosten je Abfrage, derselbe Vektorraum wie NEXUS.

**Und die Antwortzeit ist nach dem Fix kein Argument dagegen, sondern eines
dafür:** 0,154 s lokal gegen 0,190 s über die Cloud.

---

## 1. Aufbau

### 1.1 Frage

Hat der Wechsel des Einbettungsmodells die Archiv-Suche verbessert — auf dem
eigenen Bewertungssatz, unter sonst gleichen Bedingungen?

### 1.2 Die beiden Arme

Jeder Arm läuft an **seinem eigenen** kalibrierten Arbeitspunkt. Ein gemeinsamer
Grenzwert würde die Kalibrierung messen statt das Modell.

| | Arm A | Arm B |
|---|---|---|
| Einbettungsmodell | `text-embedding-3-small` | `Snowflake/snowflake-arctic-embed-l-v2.0` |
| Betriebsart | Cloud (OpenAI), 1024 Dim. | lokal, CPU, 1024 Dim. |
| Grenzwert | 0,60 (C-048) | 0,75 (C-091) |
| `FOREMAN_EMBED_PRIORITY` | `openai_only` | `st_only` |

Zusätzlich wurde **jeder Arm über acht Grenzwerte** gefahren (0,50 · 0,55 · 0,60
· 0,65 · 0,70 · 0,75 · 0,85 · 0,95), damit die Verteilungen vergleichbar werden
und nicht nur zwei Punkte.

### 1.3 Was über beide Arme identisch war

Produktcode, Bewertungssatz, Ausgabelänge k=15, Quellen
(`note`/`maintenance`/`alarm`), Fusion, Datenbank, Bestand (205 Notizen), kein
Maschinen-Ausschnitt, kein Gedächtnis als vierte Quelle.

**Variiert wurde ausschliesslich das Einbettungsmodell** — über die
Umgebungsvariable, die auch im Betrieb die Kette wählt, nicht über einen eigens
gebauten Schalter.

### 1.4 Wie erhoben

Nicht über die Schnittstelle: Der Endpunkt liest den Grenzwert aus der
Konfiguration, ein Durchlauf über acht Werte bräuchte acht Deployments.
`search_archive` wurde unmittelbar im Backend-Behälter gerufen — derselbe
Produktcode, variiert wurde allein `max_distance`.

Die Trefferlisten wurden **roh** abgelegt, im Format von `miss.py`, und mit
`werte_aus.py` aus dem Repository gerechnet. Kein Zwischenwert wurde von Hand
übertragen. Die Anfragen las `miss.lade_anfragen` — ein zweiter Leser wäre eine
zweite Wahrheit über den Bewertungssatz gewesen.

Für Arm A wurde der Bestand mit OpenAI neu eingebettet, gemessen, und danach auf
Arctic zurückgesetzt. Das Fenster war rund zwanzig Minuten lang.

### 1.5 Die Kontrollpunkte

Ohne sie belegt der Lauf nichts: Ein Arm, dessen Bestand nicht das Modell trägt,
das darüber steht, liefert plausible Zahlen über ein System, das es nie gab.

| Kontrollpunkt | Erwartung | Ergebnis |
|---|---|---|
| vor Arm B | Bestand trägt Arctic | Kosinus 1,000000 (5 Stichproben) |
| nach Umstellung | Bestand trägt OpenAI | 1,000000 gegen OpenAI |
| dieselbe Stichprobe | **darf nicht** Arctic sein | −0,014 bis +0,044 gegen Arctic |
| nach Rückstellung | wieder Arctic | 1,000000 gegen Arctic |
| dieselbe Stichprobe | **darf nicht** OpenAI sein | −0,014 bis +0,044 gegen OpenAI |

Die Stichprobe läuft quer durch den Bestand (Notizen 1, 42, 83, 124, 165), nicht
über die vorderen Zeilen: Ein abgebrochener Backfill hätte die hinteren alt
gelassen.

**Beide Richtungen waren nötig.** Der erste Kontrollpunkt hätte fast nichts
belegt: Das Prüfskript gab den Modellnamen aus einem festen Feld aus statt aus
der tatsächlich benutzten Kette — die Zahl stimmte, die Beschriftung trug sie
nicht. Erst die Gegenprobe gegen das jeweils andere Modell entscheidet.

### 1.6 Der ausgeschlossene Einwand

Arctic v2.0 verlangt auf der Anfrageseite den Präfix `query: `. Käme er nicht an,
liefe das Modell still schlechter, und der Vergleich mäße einen
Verdrahtungsfehler statt ein Modell.

Geprüft nicht am Feld, sondern an der Wirkung: derselbe Text einmal als Anfrage
und einmal als Dokument eingebettet ergibt **Kosinus 0,772** — klar verschiedene
Vektoren. Der Präfix wirkt.

### 1.7 Wiederholbarkeit

Arm B wurde **dreimal** erhoben: vor dem Deployment von PR #136, danach, und
nach der ganzen Rundreise über OpenAI und zurück. Alle drei Erhebungen sind über
alle acht Grenzwerte **byteweise identisch** — gleiche Trefferlisten, gleiche
Reihenfolge, in jeder der zehn Anfragen.

Damit ist dreierlei belegt: der Messpfad ist deterministisch, das Ergebnis hängt
nicht am Behälter oder Codestand, und die Rückstellung war vollständig — auch
durch den Suchpfad hindurch, nicht nur auf Vektorebene.

---

## 2. Ergebnis: Antwortzeit — und der Fund dahinter

Die erste erhobene Antwortzeit-Verteilung der Plattform überhaupt. Der
allererste Aufruf je Arm ist herausgerechnet — dort lädt Arctic sein Modell
(12,048 s). Gemessen ist der **vollständige Suchaufruf** (Anfrage einbetten,
drei Quellen abfragen, fusionieren), nicht das Einbetten allein.

### 2.1 Was zuerst dastand

| | n | Median | p95 |
|---|---|---|---|
| **Arm A** `text-embedding-3-small`, Cloud | 79 | 0,190 s | 0,275 s |
| **Arm B** `Arctic v2.0`, lokal | 79 | **5,505 s** | 6,700 s |

Faktor 29, und die Verteilungen überlappen sich nicht einmal. Das sah nach einer
Eigenschaft des lokalen Modells aus.

### 2.2 Es war keine

Der Einwand kam von aussen: NEXUS fährt dasselbe Modell, ebenfalls auf Railway
und ebenfalls auf CPU, und liegt im Millisekundenbereich. Also nachgemessen,
Einbettungszeit einer einzelnen Anfrage gegen die Threadzahl:

| Threads | 48 (Vorgabe) | 24 | **16** | 8 | 4 | 2 | 1 |
|---|---|---|---|---|---|---|---|
| Median | **5,340 s** | 0,193 s | **0,082 s** | 0,087 s | 0,113 s | 0,197 s | 0,322 s |

**Die Ursache:** `torch` bemisst seine Threadzahl an `os.cpu_count()` — und das
meldet im Behälter die **48 Kerne des Wirts**, nicht die Zuteilung von 24
(`/sys/fs/cgroup/cpu.max` = `2400000 100000`).

Der Schaden ist nicht Überlastung, sondern **Abstimmung**: Eine einzelne kurze
Anfrage ist eine winzige Rechnung. Je mehr Threads sich darüber verständigen,
desto mehr Zeit geht dafür drauf statt für die Rechnung. Der Stapel-Wert zeigt
dasselbe von der anderen Seite: zehn Texte auf einmal kosteten 1,197 s je Text
statt 4,5 s — der Aufwand amortisiert sich über die Menge.

### 2.3 Nach dem Fix

Threadzahl auf 16 begrenzt, gedeckelt an der Zuteilung
(`backends._begrenze_threads`):

| | n | Median | p95 | Mittel |
|---|---|---|---|---|
| Arctic, 48 Threads (Zustand bis heute) | 79 | 5,505 s | 6,700 s | 5,592 s |
| **Arctic, 16 Threads (Fix)** | 79 | **0,154 s** | 0,351 s | 0,200 s |
| OpenAI, Cloud | 79 | 0,190 s | 0,265 s | 0,213 s |

**Faktor 36.** Und der lokale Pfad ist damit **schneller als der Cloud-Aufruf** —
0,154 s gegen 0,190 s. Der Netzweg entfällt eben auch.

### 2.4 Die Einstellung ändert keine Ergebnisse

Das musste geprüft werden, bevor der Fix ein Fix sein darf: Gleitkomma-Summen
hängen von der Reihenfolge ab, und die Reihenfolge hängt bei paralleler Rechnung
an der Threadzahl.

- **Vektoren:** Abweichung 2·10⁻⁷ je Komponente zwischen 48 und 16 Threads,
  Kosinus 1,000000000. Reines Rundungsrauschen.
- **Rangfolge:** Der vollständige Armlauf über alle acht Grenzwerte, einmal mit
  48 und einmal mit 16 Threads — **byteweise identische Trefferlisten**.

Damit ist es eine Geschwindigkeits- und keine Genauigkeitsfrage, und alle
Gütezahlen dieses Berichts gelten unverändert.

### 2.5 Warum das niemandem aufgefallen ist

Im Register steht bis heute: *„Die Antwortzeit der Plattform ist nicht erhoben;
es liegen ausschliesslich Messpunkte des Gedächtnis-Dienstes vor"* — null
erhobene Verteilungen. Eine Suche, die fünfeinhalb Sekunden braucht, meldet
keinen Fehler. Sie ist nur langsam, und langsam sieht aus wie „das dauert eben".

---

## 3. Ergebnis: Güte

### 3.1 Beide Kurven

| Grenzwert | A Trefferquote | A Ranggüte | A verd. | B Trefferquote | B Ranggüte | B verd. |
|---|---|---|---|---|---|---|
| 0,50 | 0,380 | 0,378 | 0,405 | 0,084 | 0,144 | 0,146 |
| 0,55 | 0,481 | 0,439 | 0,481 | 0,143 | 0,195 | 0,214 |
| **0,60** | **0,565** | **0,493** | **0,542** | 0,197 | 0,245 | 0,268 |
| 0,65 | 0,565 | 0,493 | 0,542 | 0,275 | 0,291 | 0,324 |
| 0,70 | 0,565 | 0,493 | 0,542 | 0,362 | 0,345 | 0,416 |
| **0,75** | 0,565 | 0,493 | 0,542 | **0,409** | **0,386** | **0,466** |
| 0,85 | 0,565 | 0,493 | 0,542 | 0,482 | 0,429 | 0,527 |
| 0,95 | 0,565 | 0,493 | 0,542 | 0,482 | 0,429 | 0,527 |

Fett: der jeweils kalibrierte Arbeitspunkt.

**Arm A sättigt ab 0,65, Arm B erst ab 0,85.** Bei OpenAI liegt zwischen „zu
scharf" und „schneidet gar nichts mehr ab" fast kein Spielraum; Arctic spreizt
die Abstände breiter.

### 3.2 Der Vergleich

Gepaarter exakter Permutationstest, zweiseitig, statistische Einheit ist die
Anfrage.

| Von → Nach | Trefferquote | Ranggüte | Ranggüte **verdichtet** |
|---|---|---|---|
| A@0,60 → B@0,75 | −0,156 · p=0,031 | −0,106 · p=0,008 | −0,076 · **p=0,148** |
| A@0,60 → B@0,85 | −0,083 · p=0,031 | −0,064 · p=0,012 | −0,015 · **p=0,570** |

Freigabe-Bedingung 1 (GROUND_TRUTH §15.10): **nicht erfüllt**, sechs von zehn
Anfragen verlieren Treffer.

### 3.3 Warum daraus NICHT „Arctic ist schlechter" folgt

Der beurteilte Vorrat stammt aus der Zeit, in der `text-embedding-3-small` lief.
Er wurde aus dem gebaut, was **dieses** System gefunden hat. Was Arctic
zusätzlich hochholt, hat niemand beurteilt — und unbeurteilt zählt in der
gewöhnlichen Rechnung als *nicht zutreffend*.

| | unbeurteilte Plätze |
|---|---|
| A @0,60 | 55 von 133 — 41 % |
| B @0,75 | 64 von 112 — **57 %** |
| B @0,85 | 93 von 150 — **62 %** |

Das ist die Pool-Verzerrung (Büttcher et al. SIGIR 2007), und sie benachteiligt
systematisch das System, das den Vorrat **nicht** erzeugt hat. Verdichtet
gerechnet — die dafür vorgesehene Korrektur (Sakai 2007, unbeurteilte Einträge
entfernen statt abwerten) — ist der Unterschied **nicht gezeigt**: p=0,148
beziehungsweise p=0,570.

**Das Urteil lautet deshalb: nicht entscheidbar.** Nach MBRC R8 ist das ein
eigener Ausgang, weder bestanden noch verfehlt, und wird nicht in einen der
beiden anderen gedrückt.

### 3.4 Was den Streit entscheiden würde

Den Vorrat erweitern: die unbeurteilten Plätze **beider** Arme beurteilen
lassen, dann neu rechnen. Das sind rund 119 zusätzliche Urteile. Genau dieser
Schritt stand als „E2" in der Recherche vom 27.08.2026, mit der Begründung
*„sonst sind alle Folgezahlen Pool-Bias"*. Dieser Lauf zeigt, dass das keine
theoretische Sorge war.

---

## 4. Ergebnis: Der Grenzwert gehört zum Vektorraum

### 4.1 Dieselbe Zahl, verschiedene Bedeutung

Treffer über zehn Anfragen, höchstens 150:

| Grenzwert | 0,50 | 0,55 | **0,60** | 0,65 | 0,70 | **0,75** | 0,85 | 0,95 |
|---|---|---|---|---|---|---|---|---|
| Arm A | 73 | 110 | **133** | 150 | 150 | 150 | 150 | 150 |
| Arm B | 13 | 23 | **35** | 56 | 82 | **112** | 150 | 150 |

Bei derselben Schwelle 0,60 liefert Arm A **133** Treffer, Arm B **35**.

### 4.2 Die Räume stehen senkrecht zueinander

Derselbe Notiztext, mit beiden Modellen eingebettet:

| Notiz | 1 | 42 | 83 | 124 | 165 |
|---|---|---|---|---|---|
| Kosinus zwischen den Modellen | −0,014329 | 0,044336 | 0,021077 | −0,010444 | 0,005346 |

Das beziffert, was `backfill.py` im Kommentar behauptet: Vektoren verschiedener
Modelle liegen in **verschiedenen Räumen**. Wer nach einem Modellwechsel den
Backfill vergisst, bekommt keine schlechtere Suche — er bekommt **Rauschen in
Trefferform**, ohne Fehler und ohne Meldung.

---

## 5. Berichtsform nach MBRC 1.0

| Regel | Zustand | Anmerkung |
|---|---|---|
| **R1** Leser fixieren, Gedächtnis variieren | **erfüllt** | Kein Sprachmodell im Pfad. Produktcode, Bewertungssatz, k, Quellen, Fusion, Bestand über beide Arme identisch; variiert allein das Einbettungsmodell. |
| **R2** Bewerter festnageln und kalibrieren | **kein Gegenstand** | Kein LLM im Bewertungspfad. Die Relevanzurteile liegen als Bewertungssatz vor, die Kennzahlen sind gerechnet. Nach MBRC ist das die stärkere Evidenzform. |
| **R3** Abgestuft statt binär | **erfüllt** | Urteile 0/1/2, Ranggüte über abgestufte Relevanz. |
| **R4** Zehn Läufe, Streuung berichten | **begründete Abweichung** | siehe unten |
| **R5** Kosten neben der Güte | **teilweise** | Token: kein Gegenstand. Antwortzeit: erhoben, Abschnitt 2. Kontextreduktion: kein Gegenstand. |
| **R6** Module einzeln messen | **teilweise** | Abruf gemessen. Extraktion, Wegewahl, Pflege: kein Gegenstand für diese Einheit. |
| **R7** Keine fremden Blogzahlen | **erfüllt** | siehe unten |
| **R8** Nicht messbar bleibt nicht messbar | **erfüllt** | Güte-Unterschied als *nicht entscheidbar* geführt, Anfrage B01 als *nicht messbar*. |

### Zu R4 — die Abweichung, und warum

Der Abrufpfad ist **deterministisch**: dieselbe Anfrage, derselbe Bestand,
derselbe Grenzwert ergeben dasselbe Ergebnis. Belegt in Abschnitt 1.7 durch drei
byteweise identische Erhebungen. Zehn Läufe ergäben Streuung null; die Zahl wäre
Theater.

Statistische Einheit ist deshalb die **Anfrage** (n=10), und verglichen wird mit
einem gepaarten **exakten Permutationstest**. MBRC 1.0 nennt an dieser Stelle
Wilcoxon. Urbano, Lima und Hanjalic (SIGIR 2019) empfehlen ausdrücklich, den
Wilcoxon-Test **aufzugeben** und Permutationstest oder t-Test zu verwenden, weil
diese das Signifikanzniveau einhalten.

Das ist ein Punkt, an dem MBRC selbst schärfer werden könnte: Die Regel ist für
stochastische Systeme mit Sprachmodell im Pfad geschrieben. Für einen
deterministischen Abrufpfad hat „zehn Läufe" keinen Gegenstand — was nach der
eigenen R8-Logik ein vierter Zustand wäre und kein verfehlter.

### Zu R7 — die Fremdzahlen, die NICHT hierher gehören

Die Begründung des Wechsels im Quelltext nennt CLEF-Werte: `arctic-l-v2.0` bei
52,9 beziehungsweise 54,3 gegen 40,8 beziehungsweise 41,3 für **bge-m3**.

Diese Zahlen sind **nicht vergleichbar** im Sinne von R7, und zwar doppelt:
Sie stammen aus einem fremden Aufbau, und sie vergleichen gegen **bge-m3** —
ein Modell, das in FOREMAN produktiv nie lief. Produktiv lief
`text-embedding-3-small`. Die Fremdzahl beantwortet also nicht einmal die
Frage, um die es beim Wechsel ging.

---

## 6. Grenzen

**Der Bestand ist Simulationsdaten.** FOREMAN führt bislang ausschliesslich den
Simulations-Adapter (`source=simulation`); die 205 Notizen sind synthetisch, die
Verfasser pseudonymisiert. Alle Zahlen dieses Berichts gelten für diesen
Bestand. Ob sie auf echte Werkerprotokolle übertragen, ist offen.

**Zehn Anfragen tragen eine Richtungsaussage, keine Kennzahl mit
Vertrauensbereich.** Dinçer (2013) beziffert den Bedarf je Systempaar auf
zwischen 10 und 722 Anfragen.

**Die Präzision ist über die Grenzwerte nicht vergleichbar** — derselbe
Pool-Effekt wie in Abschnitt 3.3, nur innerhalb eines Arms.

**Anfrage B01** liefert in beiden Armen bis 0,95 keinen zutreffenden Treffer. Ob
im Bestand nichts Passendes steht oder die Zuordnung im Bewertungssatz nicht
greift, ist nicht entschieden.

**Die Antwortzeit gilt für den Behälter, wie er läuft** — 24 CPUs Zuteilung,
Threadzahl 16, Bestand 205 Notizen. Eine andere Zuteilung oder ein grösserer
Bestand ändern sie. Der Wert belegt einen Betriebszustand, keine Eigenschaft des
Modells.

**Die 5,5-Sekunden-Zahl stand zwischenzeitlich in diesem Bericht als Befund über
Arctic.** Sie war einer über die Konfiguration. Der Weg dorthin gehört zur
Messung: Erst der Einwand „NEXUS fährt dasselbe Modell auf derselben Plattform
im Millisekundenbereich" hat die Frage aufgeworfen, die die Ursache fand. Eine
Zahl, die zu einem anderen Messpunkt nicht passt, ist ein Anlass zum Nachsehen —
nicht ein Ergebnis.

**Eigeninteresse:** Diese Messung ist eine Selbstmessung am eigenen Produkt.
Rohdaten und Prüfsummen liegen offen, damit sie nachrechenbar ist.

---

## 7. Was daraus folgt

**Kein Rückbau auf die Cloud.** Die Güte-Messung stützt ihn nicht — sie
entscheidet nichts —, die Betriebsgründe bestehen unverändert, und nach dem
Threads-Fix ist der lokale Pfad auch der schnellere.

**Die Threadbegrenzung gehört ausgerollt.** Sie ist der einzige Punkt dieses
Berichts, der eine Codeänderung nach sich zieht.

**Die Aussage nach aussen:** Nicht „die Suche wurde besser" — das ist nicht
belegbar. Sondern: Der Wechsel bringt Betrieb ohne Cloud-Anbindung, eine freie
Lizenz und keine Kosten je Abfrage, bei nicht unterscheidbarer Suchgüte und
einer Antwortzeit, die den Cloud-Weg unterbietet.

**Und ein Befund über das Vorgehen, nicht über das Produkt:** Die
Fehleinstellung lag seit dem Wechsel im Betrieb und hätte dort bleiben können.
Gefunden hat sie nicht ein Test und keine Überwachung, sondern eine Messung, die
für eine ganz andere Frage angelegt war — und ein Vergleich mit einem zweiten
System, das dieselbe Aufgabe schneller löste. Antwortzeiten, die niemand erhebt,
verschlechtern sich lautlos.
