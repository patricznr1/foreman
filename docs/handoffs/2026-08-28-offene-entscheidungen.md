# Offene Entscheidungen — Stand 28.08.2026

Alles, was auf Patric wartet, mit den Einzelheiten. Zeilennummern gegen
`main` = `f230dd4` (nach #142, #143, #144).

**Heute gelandet:** #142 Ereigniszeit ans Gedächtnis · #143 Werker-Kategorie
kommt an · #144 Eine Schreibweise je Schicht.

---

## 1. GROUND_TRUTH-Nachzug — 7 Stellen, nicht 4

Ich hatte im Chat von vier Stellen gesprochen. Gegen `main` durchgesehen sind es
**sieben**, davon **zwei mit den heutigen Änderungen gar nichts zu tun haben** —
sie stehen schon länger falsch da.

Der Skill `ground-truth-update` verlangt, dass Du die Diffs siehst, bevor etwas
geändert wird. Deshalb steht hier alt/neu, nichts ist angefasst.

### 1.1 — §5, Zeile 238 · Folge von #143

**Alt:**
> `classification` (nullable, **weiterhin ungenutzt** — späterer Encoder, nicht F-SEM)

**Neu:**
> `classification` (nullable; **ab 28.08.2026 über `POST /api/v1/worker_notes` befüllt** — Werker-Kategorie `routine`/`auffaellig`/`kritisch`, im Frontend definiert, vom Werker manuell gewählt; Altbestand bleibt leer)

### 1.2 — §14.3, Zeile 643 · Folge von #143

**Alt:**
> - **`worker_notes.classification` wird NICHT genutzt** (leer/nullable; späterer Encoder, nicht in Scope).

**Neu:**
> - **`worker_notes.classification` wird vom Schreibpfad befüllt** (seit 28.08.2026; Werker-Kategorie, manuell gewählt — eine automatische Klassifikation bleibt [VISION]). Für die **Ketten-Rekonstruktion weiterhin nicht ausgewertet**: Die Notiz-Auswahl bleibt `machine_id` + Zeitfenster + F-SEM.

*Wichtig:* Der zweite Satz muss stehen bleiben. Das Feld ist jetzt gefüllt, aber
kein Reasoner liest es — wer nur den ersten Satz ändert, erweckt den gegenteiligen
Eindruck.

### 1.3 — §21.16, Zeile 1152, Anschlusspunkt (1) · Folge von #143

**Alt:**
> (1) **`classification`** wird mehrkanalig erfasst und im POST MITgesendet, aber das heutige `WorkerNoteCreate`-Schema nimmt das Feld nicht an (DB-Spalte `worker_notes.classification` existiert, §5/§14.3/§15) → wirkt ohne Frontend-Änderung, sobald das Backend-Schema nachzieht; kein FE-Fake. Genau deshalb verbietet das Schema gezielt `author` statt pauschal alle Zusatzfelder (`extra="forbid"` hätte diesen Anschlusspunkt gebrochen, §4).

**Neu:**
> (1) **`classification`** wird mehrkanalig erfasst, im POST mitgesendet und **seit 28.08.2026 vom Backend angenommen** (`WorkerNoteCreate`, freier String mit `max_length=32` wie `shift`) — der Anschlusspunkt ist **eingelöst, ohne eine Frontend-Änderung**. Das gezielte `author`-Verbot statt `extra="forbid"` bleibt: Es hält den Weg offen, ein Feld zu senden, bevor das Backend es annimmt.

### 1.4 — §9/§15, Zeile 750 · Folge von #142 · **die inhaltlich wichtigste**

Der Satz beschreibt die Anzeige richtig, aber seine **Begründung ist seit #142
falsch** — und sie schiebt einem fremden System einen Mangel unter, den wir
hatten.

**Alt (die tragende Passage):**
> Grund, an der laufenden Instanz erhoben: Die Fassade führt unter `occurred_at` den Zeitpunkt, zu dem die Erinnerung ANGELEGT wurde.

**Neu:**
> Grund, an der laufenden Instanz erhoben: Die Fassade **setzte** unter `occurred_at` den Zeitpunkt des Eingangs, **weil FOREMAN das Feld nicht sendete** — die Ereigniszeit reiste nur in den Metadaten mit, und die wertet die Gegenstelle nicht aus. **Seit 28.08.2026 (#142) geht sie als eigenes Feld mit**; der Vorrang der Nutzlast-Schlüssel bleibt als zweite Sicherung bestehen.

**Warum das zählt:** So wie es dasteht, liest sich der Befund als Eigenart der
Fassade. Tatsächlich haben wir das Feld nie befüllt. Das Repository ist
öffentlich, und ein Dritter zieht daraus den falschen Schluss über den
Zulieferer.

### 1.5 — §9, Zeile 353 · Folge von #142

Die Methodenliste beschreibt den `forget`-Vertrag ausführlich, `remember` gar
nicht. **Zu ergänzen:**

> `remember` sendet neben `content`, `namespace` und `metadata` das Feld **`occurred_at`** — den Zeitpunkt, zu dem das Ereignis stattfand. Die Quelle je Ereignisart führt `ZEIT_FELDER` in `substrate/content.py`: `worker_note` → `created_at` · `alarm_raised` → `raised_at` · `maintenance_performed` → `performed_at` · `production_run` → `started_at`. Die drei Erkenntnis-Arten senden bewusst keines — ihr Zeitpunkt *ist* der ihrer Entstehung.

---

### Die zwei Stellen, die schon vorher falsch waren

#### 1.6 — §4, Zeile 143 · **Widerspruch im Dokument selbst**

**Alt:**
> `WorkerNoteCreate` ist `extra="forbid"`: unbekannte Felder ergeben **422** statt eines 201 mit stillschweigend verworfener Eingabe (ehrliche Ablehnung statt scheinbarem Erfolg).

**Der Code war nie so.** §21.16 (Zeile 1152) beschreibt im selben Dokument das
Gegenteil, und der Code folgt §21.16. Belegt durch
`tests/integration/test_authorship_binding.py::test_note_still_accepts_an_unknown_extra_field`
— ein unbekanntes Feld ergibt **201**, nicht 422.

**Neu:**
> `WorkerNoteCreate` verbietet **gezielt `author`** (422) statt pauschal alle Zusatzfelder; unbekannte Felder verfallen nach Pydantic-Vorgabe still. Das hält den Weg offen, ein Feld zu senden, bevor das Backend es annimmt (§21.16) — `author` ist die Ausnahme, weil ein stilles Verwerfen dort die **Zuschreibung** falsch aussehen liesse, nicht bloss unvollständig.

**Deine eigentliche Entscheidung dahinter:** Nach #143 sendet das Frontend
**kein** Feld mehr, das das Backend nicht kennt (`text`, `machine_id`, `shift`,
`classification` — alle angenommen). Der Grund für `extra=ignore` ist damit
weggefallen. Zwei Wege:

| | |
|---|---|
| **A — so lassen** (empfohlen) | Der Weg „Frontend zuerst, Backend zieht nach" bleibt offen. Genau der hat heute funktioniert. Preis: ein Tippfehler im Feldnamen ergibt weiterhin 201 mit fehlendem Wert. |
| **B — `extra="forbid"`** | Ein Tippfehler wird zu 422. Preis: gestaffelte Rollouts brechen, und der Anschlusspunkt-Mechanismus ist weg. |

Ich habe **nichts geändert** — nur die Beschreibung an den Code anzugleichen ist
die kleinere Aussage und ändert kein Verhalten.

#### 1.7 — §21.16, Zeile 1152, Anschlusspunkt (4) · falsch seit 27.08.

**Alt:**
> (4) **`created_at` setzt der Server** (tz-aware) — der Client kann ihn nicht anpassen; das „optional anpassbar" der Studie ist [VISION].

**Der Client kann ihn anpassen**, seit `WorkerNoteCreate.occurred_at` existiert:
`api/routers/worker_notes.py:66` liest ihn, Zeile 81–82 setzt `obj.created_at`.

**Neu:**
> (4) **`created_at` setzt der Server** (tz-aware), **es sei denn, der Client schickt `occurred_at`** — den Zeitpunkt der Schicht, für den Nachtrag einer Notiz, die auf Papier stand. Eine naive Zeitangabe ohne Zone wird mit 422 abgewiesen statt gedeutet. Das „optional anpassbar" der Studie ist damit **umgesetzt**, nicht [VISION].

---

## 2. `retention_policy` — Datenverlust oder Gedächtnis

**Der Sachverhalt:** NEXUS verwirft beim Übergang zwischen den Gedächtnis-Halden
Notizen, die einer bereits gespeicherten **zu ähnlich** sind. Das ist die
Voreinstellung (`default`). Abschaltbar über `forgetting_free`.

**Warum das nicht neutral ist:** Für ein *Gedächtnis* ist Verwerfen richtig —
Redundanz kostet Platz und bringt nichts. Für eine *Schichtdokumentation* ist es
Datenverlust. Zwei Werker, die dieselbe Störung ähnlich melden, sind **zwei
Beobachtungen** — und dass zwei Leute unabhängig dasselbe gesehen haben, ist die
stärkere Information, nicht die redundante.

Dazu die Nachweisseite: Wenn ein Werker eine Notiz schreibt und sie später nicht
mehr auffindbar ist, ist das für ihn ein kaputtes System.

**Du kannst das noch nicht entscheiden** — fünf Fragen sind bei NEXUS offen und
unbeantwortet:

1. **Welche Schwelle?** Ähnlichkeit worüber — Einbettung, Text-Hash, beides? Und
   welcher Wert?
2. **Ist der verworfene Eintrag noch da?** Gelöscht, oder auffindbar und nur von
   der Konsolidierung ausgenommen?
3. **Verschmelzen oder wegwerfen?** Erbt der behaltene etwas vom verworfenen
   (Kennung, Zähler, Metadaten)?
4. **Wirkt `forgetting_free` rückwirkend** oder nur auf künftige Übergänge?
5. **Je Namensraum setzbar?** Wir bräuchten es nur für `foreman`.

Antwort 2 und 3 entscheiden praktisch alles: Ist der Eintrag noch auffindbar und
erbt der behaltene die Herkunft, ist `default` vertretbar. Wird er weggeworfen,
brauchen wir `forgetting_free`.

Steht in `docs/research/2026-08-28_nexus_rueckantwort_2.md`, wiederholt in `…_3.md`.

---

## 3. NEXUS-Frage 1.6 — wie FOREMAN die Ontologie liest

**Der Sachverhalt:** Unser Ausweis öffnet nur `/api/substrate/*`. Alles
Ontologische liegt hinter der JWT-Grenze; `/substrate/reason` antwortet
`active: false`. Eine gepflegte Ontologie wäre für uns heute **unerreichbar**.

NEXUS bittet um eine Position, bevor sie Erhebungsarbeit anfangen. Drei Wege:

| Weg | Was er kostet |
|---|---|
| **A — Durchreichung über die Fassade** (meine Empfehlung) | Arbeit auf NEXUS-Seite. Für uns: ein Ausweis, ein Ablaufpfad, eine Konfigurationsstelle. |
| **B — eigener Ausweis** | Ein zweites Geheimnis im Betrieb, ein zweiter Ablaufpfad, eine zweite Stelle, an der ein Kunde etwas falsch konfiguriert. |
| **C — ausdrücklicher Verzicht** | Die Ontologie wirkt nur intern auf ihre Abrufqualität. Kostet uns nichts. |

**Warum C für uns nicht neutral ist:** Du hast FOREMAN so konzipiert, dass ein
Kunde es *ohne* NEXUS betreiben kann — dann mit einfacher Archivsuche, ohne
Frühwarnung und ohne „hatten wir das schon mal". Diese Funktionen sind der
Aufpreis. Ein Verzicht nähme genau die Schicht weg, für die es NEXUS im Produkt
gibt.

---

## 4. Alarmcode-Katalog — NEXUS unterschätzt das

NEXUS veranschlagt „acht Zeilen: Code, Klartext, Sachverhalt, Stufe, Komponente".

**Es gibt bei uns keinen Katalog.** Die Codes stehen als Zeichenketten in
`src/foreman/adapters/simulation/scenarios/*.yaml`, je Szenario eigene. Gefunden:
`AXIS_VIB_WARN`, `BRG_TEMP_WARN`, `BRG_TEMP_CRIT`, `BRG_B_TEMP_WARN`,
`HYD_PRESS_LOW_WARN`, `HYD_PRESS_LOW_CRIT`. Die Stufe steckt **allein in der
Namenskonvention**.

`sachverhalt_id` + `stufe` einzuführen heißt: eine Katalogtabelle anlegen, eine
Migration, den Bestand darauf abbilden, und die Szenario-Konfigurationen dagegen
validieren. Das ist eine Datenmodell-Entscheidung, keine Durchreiche-Arbeit.

**Der Nutzen ist echt:** Heute sind `HYD_PRESS_LOW_WARN` und
`HYD_PRESS_LOW_CRIT` im Wissensgraphen durch **nichts** verbunden — obwohl die
Eskalation in unseren Rohdaten steht (WARN 20.06. Maschine 7, CRIT 22.06.
dieselbe Maschine, dieselbe Größe). Ohne die Kante ist „welche Warnung geht dem
kritischen Zustand voraus" nicht beantwortbar — der eigentliche Zweck
vorausschauender Instandhaltung.

Ich habe **nicht** gebaut und NEXUS die Korrektur geschickt, damit sie nicht auf
etwas Falsches warten.

---

## 5. `archive_substrate_k` — gesetzt, nie gemessen

`src/foreman/config.py:134` — Vorgabe **5**, Bereich 1–50, über
`FOREMAN_ARCHIVE_SUBSTRATE_K` steuerbar. Der Kommentar begründet nur die
*Richtung* („bewusst kleiner als die Trefferzahl der eigenen Quellen: das
Gedächtnis ergänzt, es dominiert nicht"), nicht den Wert.

Nach dem Modellwechsel und der Schwellen-Kalibrierung (C-091, `0.75`) ist das
die letzte ungemessene Zahl im Abrufpfad. Das Goldset trägt jetzt 81 zusätzliche
Urteile — die Messung wäre machbar, ist aber **nicht gelaufen**. Kein
Registereintrag behauptet etwas über diesen Wert.

---

## 6. Was bei NEXUS liegt, nicht bei Dir

Der Vollständigkeit halber — hierauf warten wir, es ist keine Entscheidung von Dir:

- **Wo `classification` stehen muss**, damit ihr Drift-Monitor es sieht.
  Metadaten scheiden nach ihrer eigenen Auskunft aus; den gespiegelten Satz zu
  ändern würde unsere Archiv-Kalibrierung ungültig machen. Es ist dieselbe
  Entscheidung wie ihre Prompt-Frage zu 1.1/1.4.
- **Die 302 Bestands-Einträge** tragen weiterhin die falsche Ereigniszeit.
  `remember` hat keinen Änderungsweg; `forget` + neu schreiben risse die
  `substrate_ref`-Verknüpfung. Wir brauchen einen Stapel-Weg von ihnen.
- **Der `forget`-Weg selbst** ist auf ihrer Seite noch nicht ausgeliefert
  (NEXUS-PR #100, laut GROUND_TRUTH §9 Zeile 353 nicht gemergt). Solange ist ein
  Löschverlangen für den gespiegelten Teil praktisch nicht durchführbar — das
  ist die einzige Position mit einer Rechtsfolge (Art. 17 DSGVO).

---

## Reihenfolge, wenn Du fragst

1. **1.4** zuerst (öffentliches Repo, schiebt einem Dritten einen Mangel unter).
2. **1.6 / 1.7** — zwei Stellen, die schon länger falsch dastehen; unabhängig von
   allem anderen.
3. **NEXUS-Frage 1.6** (Abschnitt 3) — ein Gespräch, keine Arbeit, und NEXUS
   wartet darauf, bevor sie erheben.
4. Der Rest des GROUND_TRUTH-Nachzugs.
5. `retention_policy`, sobald die fünf Antworten da sind.
6. `substrate_k` messen.
7. Alarmcode-Katalog — der größte Brocken, und der einzige mit einer Migration.
