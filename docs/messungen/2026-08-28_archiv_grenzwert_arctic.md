# Der Vektor-Grenzwert der Archiv-Suche, erhoben gegen Snowflake Arctic v2.0

**Datum:** 28.08.2026 · **Register:** C-091 · **Freigabe:** intern, fach

## Worum es geht

Der lokale Einbettungspfad läuft seit dem 28.08.2026 auf
`Snowflake/snowflake-arctic-embed-l-v2.0`. Der Relevanz-Grenzwert der hybriden
Notiz-Suche (`archive_vector_max_distance`) stand dabei unverändert auf **0,60** —
einem Wert, der am 24.08.2026 gegen ein anderes, nicht benanntes Modell erhoben
worden war (C-048, C-082).

Ein Abstand hat nur innerhalb **eines** Vektorraums Bedeutung. Ein übernommener
Grenzwert ändert beim Modellwechsel stillschweigend die Strenge der Suche — in
beide Richtungen möglich, und in keiner fällt es auf.

## Wie gemessen wurde

Gegen den Bewertungssatz `goldset_v3.json` (10 Anfragen, 80 zutreffende
Einträge), **k=15**, Quellen `note`/`maintenance`/`alarm`, ohne
Maschinen-Einschränkung.

**Nicht über die Schnittstelle.** Der Endpunkt liest den Grenzwert aus der
Konfiguration; ein Durchlauf über mehrere Werte bräuchte je ein Deployment.
Gerufen wurde stattdessen `search_archive` unmittelbar im Backend-Behälter —
derselbe Produktcode, variiert wurde allein `max_distance`.

Die Trefferlisten wurden **roh** abgelegt, im Format von `miss.py`, und mit
`werte_aus.py` aus dem Repository gerechnet. Kein Zwischenwert wurde von Hand
übertragen. Die Anfragen las derselbe Leser, den `miss.py` benutzt — ein zweiter
wäre eine zweite Wahrheit über den Bewertungssatz gewesen.

### Voraussetzung, belegt statt angenommen

Alle 205 Notizen tragen Arctic-Vektoren. Geprüft wurde das nicht daran, dass der
Backfill Erfolg meldete — seine Meldung fehlte in der Ausgabe sogar —, sondern
so: Der Text von fünf über den Bestand verteilten Notizen wurde mit dem
laufenden Anbieter neu eingebettet und mit dem gespeicherten Vektor verglichen.

| Notiz | 1 | 42 | 83 | 124 | 165 |
|---|---|---|---|---|---|
| Kosinus (gespeichert, frisch) | 1,000000 | 1,000000 | 1,000000 | 1,000000 | 1,000000 |

Quer durch den Bestand, nicht nur vorne: Ein abgebrochener Backfill hätte die
hinteren Zeilen alt gelassen.

## Ergebnis

| Grenzwert | Trefferquote | Präzision | Ranggüte | verdichtet | Anfragen ohne Treffer | Plätze gefüllt |
|---|---|---|---|---|---|---|
| 0,50 | 0,084 | 0,350 | 0,144 | 0,146 | 7 von 10 | 13 / 150 |
| 0,55 | 0,143 | 0,431 | 0,195 | 0,214 | 6 von 10 | 23 / 150 |
| **0,60** (bisher) | **0,197** | 0,340 | **0,245** | 0,268 | **6 von 10** | 35 / 150 |
| 0,65 | 0,275 | 0,215 | 0,291 | 0,324 | 6 von 10 | 56 / 150 |
| 0,70 | 0,362 | 0,230 | 0,345 | 0,416 | 4 von 10 | 82 / 150 |
| **0,75** (neu) | **0,409** | 0,263 | **0,386** | 0,466 | **2 von 10** | 112 / 150 |
| 0,85 | 0,482 | 0,253 | 0,429 | 0,527 | 1 von 10 | 150 / 150 |
| 0,95 | 0,482 | 0,253 | 0,429 | 0,527 | 1 von 10 | 150 / 150 |

**Bei 0,60 lieferten 6 von 10 Anfragen keinen einzigen zutreffenden Treffer.**
Die Suche arbeitete faktisch als reine Volltextsuche — derselbe Ausfall, den
C-048 am 24.08.2026 beschrieben hat, nur mit vertauschten Vorzeichen: Damals war
der Wert nie erhoben, diesmal war er für ein anderes Modell erhoben.

## Warum 0,75 und nicht weiter

**Der Schritt 0,60 → 0,75 trägt.** Gepaarter exakter Permutationstest,
zweiseitig, n=9:

| Kennzahl | mittlere Differenz | p |
|---|---|---|
| Trefferquote | +0,213 | 0,016 |
| Ranggüte | +0,142 | 0,016 |
| Ranggüte verdichtet | +0,198 | 0,016 |

Dazu: **kein einziger verlorener Treffer**, 70 % der Anfragen mit Zusatztreffer.
Freigabe-Bedingung 1 nach GROUND_TRUTH §15.10 erfüllt.

**Der Schritt 0,75 → 0,85 ist nicht gezeigt** (p=0,250 in allen drei
Kennzahlen). Und er sättigt die Ausgabe: alle 150 Plätze gefüllt. Ein Grenzwert,
der nichts mehr abschneidet, ist kein Relevanzboden — jede Anfrage bekäme 15
Treffer, auch eine, zu der nichts im Bestand steht.

## Was diese Messung nicht trägt

**Die Präzision ist über die Schwellen nicht vergleichbar.** Der beurteilte
Vorrat wird mit steigender Schwelle immer lückenhafter — 17 von 35 Plätzen
unbeurteilt bei 0,60, 64 von 112 bei 0,75, 93 von 150 bei 0,85 — und
unbeurteilt zählt in der gewöhnlichen Rechnung als nicht zutreffend. Das ist die
Pool-Verzerrung (Sakai 2007), dieselbe, die schon C-085 beziffert hat.

Die Auswahlregel aus C-048 — *„der Anteil zutreffender Treffer muss über einem
Drittel bleiben"* — ließ sich deshalb **nicht unverändert anwenden**. Angewandt
hätte sie 0,60 bestätigt (Präzision 0,340 gegen 0,215 bei 0,65) und damit genau
den Ausfall festgeschrieben, gegen den C-048 geschrieben wurde.

Getragen wird die Wahl von **Trefferquote und Ranggüte**. Beide sind gegen diese
Verzerrung robust, weil ihr Bezugspunkt der Bewertungssatz ist und nicht die
ausgelieferte Liste.

**Nicht mitgemessen:** das Gedächtnis als vierte Quelle. Der Grenzwert wirkt
allein im Notiz-Zweig; die vierte Quelle hätte den Effekt nur verdünnt.

**Zehn Anfragen tragen eine Richtungsaussage, keine Kennzahl mit
Vertrauensbereich** (Dincer 2013: 10 bis 722 Topics je Systempaar).

## Offen

Anfrage **B01** liefert bis hinauf zu 0,95 keinen zutreffenden Treffer. Ob im
Bestand nichts Passendes steht oder die Zuordnung im Bewertungssatz nicht
greift, ist hier nicht entschieden.

**Der Modellwechsel berührt jede frühere Gütemessung der Archiv-Suche.** Alle
Zahlen aus C-049 bis C-088 wurden gegen das vorige Einbettungsmodell und den
vorigen Grenzwert erhoben. Sie sind damit keine Aussagen mehr über das System,
das läuft. Welche davon neu zu erheben sind, ist eine eigene Entscheidung und
hier nicht getroffen.
