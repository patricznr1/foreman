# Werker-Notizen — Stilguide & Beispiel-Bibliothek (FOREMAN-Simulation)

> Stand Juni 2026 · für die Erzeugung realistischer deutscher Schichtbericht-Notizen (`worker_notes.text`) in FOREMAN-Simulations-Szenarien.
> **Zweck:** Demo-/Test-Notizen, die klingen wie echte Werkstatt-Schichtberichte — knapp, fachsprachlich, abkürzungslastig, von verschiedenen Schreibern. Sie werden in Szenarien (siehe [`szenarien.md`](./szenarien.md)) eingebettet und durchlaufen beim Insert die **NER-Maskierung + Autor-Tokenisierung** ([`../research/anonymisierung-werkerdaten.md`](../research/anonymisierung-werkerdaten.md)).
> **Anschluss:** Themen Lager / Werkzeug / Schmierung passend zu den vier Szenarien, inkl. der „Symptom zwei Schichten vor dem Ausfall"-Erzählung.
> **Klassen** (`worker_notes.classification`): `routine` / `auffaellig` / `kritisch`. **Schichten** (`shift`): `frueh` / `spaet` / `nacht`.
> **Hinweis:** Einige Beispiele enthalten **bewusst Kollegen-Namen** — sie sind **nicht** vorab anonymisiert, damit die NER-Maskierung im Pipeline-Pfad etwas zu fassen bekommt. (Falls erwähnt: das Gedächtnis ist ein externer Dienst hinter HTTP-API; keine Interna.)

---

## 1. Voice-Varianten

Echte Schichtberichte haben keinen einheitlichen Ton — sie hängen am Schreiber. Vier wiederkehrende Register, die die Generierung mischen soll:

**A — knapp / telegrammartig.** Stichworte, kaum Verben, Punkt oder gar nichts am Satzende. Der Schichtführer, der es eilig hat.
> „Sp.1 Geräusch beim Hochlauf. Beobachten."
> „Lg. AS warm, 68°. io soweit."

**B — gesprächig / ausführlich.** Ganze Sätze, etwas Erklärung, manchmal eine Vermutung dazu. Der, der gern dokumentiert.
> „Beim Anfahren von BAZ-02 heute Morgen ein deutliches Mahlen aus der Spindel, hört sich nach Lager an. Werte noch unauffällig, hab's aber der Frühschicht gesagt."
> „Schmierung an Pumpe 3 gemacht, allerdings war das vorgesehene Fett leer, hab das Ersatzfett genommen. Müsste passen, schreib's trotzdem hin."

**C — abkürzungslastig.** Dichte aus Kürzeln, Einheiten, Codes. Der Instandhalter, der die Anlage seit zehn Jahren kennt.
> „Wkz gewechselt, Drz io, Vib Sp. leicht erhöht ~3,2 mm/s, VB beobachten."
> „AL F-1042 quittiert, Temp Lg. DE 71°, nio, Wartung informiert."

**D — leicht dialektgefärbt.** Süddeutscher/regionaler Einschlag, umgangssprachlich, ohne zu übertreiben.
> „D'Spindel läuft heiß, mecht scho a bissl komisch. Schau ma morgen."
> „Des Lager hinten brummt, gfallt mir net. Hab's der Spätschicht gsagt."

Mischungsregel: pro Szenario verschiedene Voices über die Schichten verteilen — derselbe Werker schreibt tendenziell im gleichen Register (Autor-Token konsistent halten).

---

## 2. Abkürzungen & Fachjargon (Referenztabelle)

Diese Tabelle dient doppelt: als Generierungs-Wortschatz **und** als Startpunkt für das Synonym-/Abkürzungs-Mapping der semantischen Suche ([`../research/vektor-suche-pgvector.md`](../research/vektor-suche-pgvector.md) §6).

| Kürzel / Jargon | Bedeutung | Kontext |
|---|---|---|
| `Sp.` / `Spi` | Spindel | CNC, Bearbeitungszentrum |
| `Lg.` | Lager | Spindel, Pumpe, Motor |
| `AS` / `DE` | Antriebsseite / Drive End | Lager-Position |
| `AbS` / `NDE` | Abtriebs-/Nichtantriebsseite | Lager-Position |
| `Wkz` | Werkzeug | Fräser, Bohrer, Schaftfräser |
| `Drz` | Drehzahl | rpm |
| `Vib` | Vibration / Schwingung | mm/s |
| `Temp` | Temperatur | °C |
| `VB` | Verschleißmarkenbreite (Flankenverschleiß) | Werkzeug |
| `io` / `i.O.` | in Ordnung | Statusvermerk |
| `nio` / `n.i.O.` | nicht in Ordnung | Statusvermerk |
| `AL` | Alarm / Alarmmeldung | SPS, HMI |
| `F-1042` (o. ä.) | Fehlercode | Anlagensteuerung |
| `E-Stop` / `Notaus` | Not-Halt | Sicherheit |
| `quittiert` | Alarm bestätigt | Operator-Handlung |
| `getauscht` / `gewechselt` | Bauteil/Werkzeug ersetzt | Instandhaltung |
| `nachgeschmiert` | Schmierung erneuert | Wartung |
| `läuft heiß` / `wird warm` | Temperaturauffälligkeit | Lager, Motor |
| `Geräusch` / `mahlt` / `singt` / `brummt` / `klackt` | akustische Auffälligkeit | Lager, Getriebe |
| `Späne` (blau/bläulich) | Spanfarbe → Hitze/Verschleiß | Zerspanung |
| `Oberfläche` (rau, Rattermarken) | Werkstückqualität | Zerspanung |
| `Ausschuss` | Teil außerhalb Toleranz | Qualität |
| `Stillstand` / `steht` | Maschine läuft nicht | Schicht/WE |
| `KW` | Kalenderwoche | Zeitbezug |
| `F` / `S` / `N` | Früh-/Spät-/Nachtschicht | Schichtbezug |
| `BAZ` | Bearbeitungszentrum | Maschinen-Typ |
| `~` (Tilde) | „ungefähr" vor Messwert | „~3,2 mm/s" |

---

## 3. Aufbau-Muster eines realistischen Schichtberichts

Echte Notizen sind **kein** Fließtext-Absatz, sondern folgen lose einem dieser Muster:

1. **Maschine/Bauteil → Beobachtung → (optional) Wert → Status/Maßnahme.**
   „Sp.1 Geräusch beim Hochlauf, ~3 mm/s, beobachten."
2. **Handlung → Ergebnis.**
   „Wkz gewechselt, läuft wieder rund. io."
3. **Beobachtung → Vermutung → Weitergabe.**
   „Lager AS wird warm, evtl. Schmierung. Der Spätschicht gesagt."
4. **Status-only (Routine).**
   „Schicht ruhig, nichts Besonderes. Alles io."

Merkmale, die Realismus erzeugen: **keine vollständige Grammatik**, fehlende Satzzeichen, Maßeinheiten direkt am Wert (`68°`, `3,2 mm/s`), Komma statt Punkt im Dezimalwert, gelegentliche Weitergabe an die nächste Schicht, gelegentlich ein Kollegenname.

---

## 4. Beispiel-Bibliothek (42 Notizen)

Direkt als `worker_notes` einsetzbar. Spalten: **#**, **Text**, **Klasse**, **Maschinen-/Komponentenart**, **Schicht**, **Voice**, **Name?** (enthält Personennamen → NER-Testfall).

### 4.1 Routine (`classification: routine`)

| # | Text | Maschine/Komponente | Schicht | Voice | Name? |
|---|---|---|---|---|---|
| 1 | „Schicht ruhig, nichts Besonderes. Alles io." | allg. | frueh | A | – |
| 2 | „BAZ-01 läuft rund, Routinekontrolle F-Schicht ok." | cnc / spindle | frueh | A | – |
| 3 | „Sp. und Lg. unauffällig, Temp normal. io." | cnc / bearing | spaet | C | – |
| 4 | „Nachtschicht ruhig, Maschine unauffällig. Wochenende stand sie wie geplant." | cnc | nacht | B | – |
| 5 | „Drz io, keine Auffälligkeiten, Teile in Toleranz." | cnc / spindle | frueh | C | – |
| 6 | „Pumpe 3 läuft sauber, beide Lager ruhig, Temp um 50°." | pump / bearing | spaet | A | – |
| 7 | „Alles im grünen Bereich. Mit Kollege Bauer Übergabe gemacht, nix offen." | allg. | spaet | B | **ja** |
| 8 | „Frühkontrolle: Wkz neu seit gestern, Späne normal, Oberfläche io." | cnc / spindle | frueh | C | – |
| 9 | „Routine N-Schicht, nix los. Schmierstände geprüft, io." | allg. / motor | nacht | A | – |
| 10 | „Anlage sauber gelaufen, keine AL. Übergabe an Yilmaz." | cnc | spaet | A | **ja** |
| 11 | „BAZ-02 unauffällig, Vib Sp. ~1,9 mm/s, alles normal." | cnc / spindle | frueh | C | – |
| 12 | „Schicht ohne Vorkommnisse, Maschine durchgelaufen." | allg. | nacht | A | – |
| 13 | „Des lief heid sauber, koa Theater. io." | cnc | frueh | D | – |
| 14 | „Wartungstermin vorbereitet, Material geholt, sonst Routine." | allg. | frueh | B | – |

### 4.2 Auffälligkeit (`classification: auffaellig`)

| # | Text | Maschine/Komponente | Schicht | Voice | Name? |
|---|---|---|---|---|---|
| 15 | „Sp.1 macht beim Hochlauf ein mahlendes Geräusch, letzte Woche noch nicht da. Werte unauffällig, beobachten." | cnc / bearing | spaet | B | – |
| 16 | „Lg. AS wird wärmer als sonst, ~63°. Noch io, aber im Auge behalten." | pump / bearing | nacht | A | – |
| 17 | „Vib Sp. leicht erhöht ~3,2 mm/s, VB beobachten. Wartung Bescheid." | cnc / spindle | frueh | C | – |
| 18 | „Müller meint das Lager hinten läuft heiß, hab nachgefühlt, stimmt, wird warm." | pump / bearing | spaet | B | **ja** |
| 19 | „Oberfläche am Teil wird rauer, Späne werden bläulich. Wkz läuft schon paar Tage, riecht nach Standzeitende." | cnc / spindle | frueh | B | – |
| 20 | „Spindel singt ein bisschen unter Last, Strom laut Anzeige höher als üblich." | cnc / spindle | spaet | A | – |
| 21 | „D'Spindel läuft heiß, mecht scho a bissl komisch. Schau ma morgen." | cnc / spindle | nacht | D | – |
| 22 | „Pumpe 3 Abtriebsseite spürbar wärmer und lauter als Antriebsseite. Komisch, beide gleich alt." | pump / bearing | nacht | B | – |
| 23 | „Nachgeschmiert Lg. B, vorgesehenes Fett war leer, Ersatzfett genommen. Vermerkt für später." | pump / bearing | frueh | B | – |
| 24 | „Drz zittert leicht unter Last, Regelung nicht ganz sauber. Beobachten." | cnc / spindle | spaet | C | – |
| 25 | „Geräusch am Antriebsmotor, klackt unregelmäßig. Mit Schmidt getauscht wer drauf schaut." | cnc / motor | nacht | A | **ja** |
| 26 | „Temp Lg. DE kriecht hoch, jetzt 66°, war Anfang der Woche 58°. Trend nach oben." | cnc / bearing | frueh | C | – |
| 27 | „Werkzeug hält nicht mehr so lange wie sonst, öfter nachstellen. Evtl. Charge schlechter." | cnc / spindle | spaet | B | – |
| 28 | „Leichtes Rattern bei hoher Drz, Oberfläche grenzwertig. Kowalski schaut sich's an." | cnc / axis | frueh | A | **ja** |
| 29 | „Lager vorn brummt tiefer als gewohnt, noch keine Alarmwerte. Notiert." | pump / bearing | nacht | A | – |
| 30 | „Schmierung war fällig, gemacht. Danach kurz besser, mal sehen ob's hält." | cnc / bearing | frueh | B | – |
| 31 | „Vib steigt langsam über die Schichten, von ~2 auf ~3,5 mm/s in paar Tagen. Aufpassen." | cnc / bearing | spaet | C | – |
| 32 | „Des Lager hinten gfallt mir net, brummt. Hab's der Spätschicht gsagt." | pump / bearing | frueh | D | – |

### 4.3 Kritischer Vorfall (`classification: kritisch`)

| # | Text | Maschine/Komponente | Schicht | Voice | Name? |
|---|---|---|---|---|---|
| 33 | „AL Lagertemp Sp. über Warnschwelle, 76°. F-1042 quittiert, Wartung gerufen." | cnc / bearing | spaet | C | – |
| 34 | „Lg. DE jetzt 82°, kritisch. Maschine runtergefahren, Inspektion angefordert." | cnc / bearing | nacht | A | – |
| 35 | „Spindel laut, Vib ~7 mm/s, deutlich nio. Sofort gestoppt, Frühschicht muss Lager prüfen." | cnc / bearing | nacht | A | – |
| 36 | „Notaus ausgelöst, Späne haben geklemmt, Wkz gebrochen. E-Stop quittiert nach Kontrolle. Hoffmann informiert." | cnc / spindle | spaet | B | **ja** |
| 37 | „Pumpe 3 AbS Lager kreischt, Temp 78°, abgeschaltet. So lief das vor zwei Schichten schon mal warm an — siehe meine Notiz." | pump / bearing | nacht | B | – |
| 38 | „Wkz-Bruch beim Schlichten, Teil Ausschuss. Neues Wkz, Maschine wieder an. AL quittiert." | cnc / spindle | frueh | C | – |
| 39 | „Lager fest, Spindel blockiert beim Anlauf. Anlage steht. Instandhaltung + Frau Wagner verständigt." | cnc / bearing | frueh | A | **ja** |
| 40 | „Starkes Mahlen + Rauch aus Sp., sofort Notaus. Nix mehr anfassen bis Wartung da war." | cnc / bearing | spaet | A | – |
| 41 | „Temp + Vib beide kritisch, Lager hin. Genau das Geräusch von letzter Woche, hätt man früher sehen können." | cnc / bearing | nacht | B | – |
| 42 | „Antriebsmotor durchgebrannt riecht's, Sicherung raus. Anlage aus, Elektriker Nguyen kommt." | cnc / motor | nacht | A | **ja** |

---

## 5. „Symptom zwei Schichten vor dem Ausfall" — Erzähl-Set

Für die „hatten wir das schon mal"-Story in den Drift-Szenarien gehören Notizen **paarweise** über die Zeit gesetzt: eine frühe, beiläufige Auffälligkeit und der spätere kritische Vorfall, der auf sie zurückverweist.

- **Früh (auffaellig, ~2 Schichten vorher):** Nr. 15 („mahlendes Geräusch … beobachten") oder Nr. 26 („Temp … Trend nach oben").
- **Spät (kritisch):** Nr. 37 oder Nr. 41 („genau das Geräusch von letzter Woche, hätt man früher sehen können").

Genau diese Paarung macht den Frühwarn-Mehrwert des Drift-Reasoners erzählbar: das Signal war im Bericht, nur niemand hat es verbunden.

---

## 6. NER-Maskierung — Vorher/Nachher

Die namenshaltigen Notizen (Spalte „Name? = ja") sind die NER-Testfälle. Erwartung: nach Maskierung bleibt der Satz **lesbar und fachlich sinnvoll**, nur der Name ist ersetzt.

| Vorher | Nachher (erwartet) |
|---|---|
| „Müller meint das Lager hinten läuft heiß …" | „[PERSON] meint das Lager hinten läuft heiß …" |
| „Mit Schmidt getauscht wer drauf schaut." | „Mit [PERSON] getauscht wer drauf schaut." |
| „… Instandhaltung + Frau Wagner verständigt." | „… Instandhaltung + Frau [PERSON] verständigt." |
| „… Elektriker Nguyen kommt." | „… Elektriker [PERSON] kommt." |

Restrisiko bleibt (NER-Recall < 100 %, vgl. Anonymisierungs-Doc) — deshalb nie als „anonym" deklarieren. Die Beispiele decken bewusst verschiedene Namensformen ab: Nachname allein, Vorname-Kontext, mit Anrede („Frau"), mit Rollen-Präfix („Elektriker", „Kollege").

---

## 7. Realismus-Kriterien-Checkliste

Woran erkennt man, ob eine generierte Notiz echt klingt? (Grundlage für Patrics finale Validierung — 17 Jahre Industrie.)

- [ ] **Länge:** kurz. Routine oft < 10 Wörter; selbst kritische Vorfälle selten > 2 Sätze. Lange, glatte Absätze sind ein Alarmzeichen für „KI-generiert".
- [ ] **Jargon-Dichte:** mindestens ein Kürzel/Fachwort aus der Referenztabelle (Sp., Lg., Vib, io/nio, Drz …). Keine Notiz im reinen Hochdeutsch ohne Werkstattbegriff.
- [ ] **Satzzeichen/Grammatik:** unvollständig erlaubt und erwünscht — fehlende Verben, kein Punkt am Ende, Stichworte. Perfekte Grammatik wirkt unecht.
- [ ] **Messwerte realistisch & einheitennah:** Werte plausibel zur Größe (Vib 1–8 mm/s, Lagertemp 45–85 °C), Einheit direkt am Wert, Komma als Dezimaltrenner (`3,2 mm/s`).
- [ ] **Symptom passt zur Maschinen-/Komponentenart:** Lager → Geräusch/Temperatur/Vibration; Werkzeug → Oberfläche/Späne/Last/Standzeit; Motor → Geruch/Strom/klacken. Ein „mahlendes Lagergeräusch" an einem reinen Setpoint-Datenpunkt ist unplausibel.
- [ ] **Plausible Eskalation:** Routine → Auffälligkeit → kritisch über die Zeit; kritische Vorfälle nennen meist eine Maßnahme (gestoppt, quittiert, gerufen).
- [ ] **Schreiber-Konsistenz:** derselbe Autor-Token tendenziell gleiche Voice.
- [ ] **Weitergabe-/Sozial-Marker** kommen vor: „der Spätschicht gesagt", „mit X getauscht" — echte Berichte sind in den Schichtbetrieb eingebettet.
- [ ] **Keine Marketing-/Akademiker-Floskeln:** kein „optimieren", „signifikant", „proaktiv". Werkstatt redet anders.
- [ ] **Dialekt sparsam:** ein regionaler Einschlag pro Notiz reicht; nicht jede Notiz dialektal.

Faustregel: Würde ein Werkstattmeister die Notiz beim Überfliegen für die eines Kollegen halten — oder stutzt er, weil sie „zu rund" ist?

---

## 8. Offene Punkte

- **Klassifikations-Enum:** `routine`/`auffaellig`/`kritisch` mit dem finalen `worker_notes.classification`-Wertebereich abgleichen (GROUND_TRUTH §5; Feld in F2 noch nullable).
- **Mehr Themenbreite:** bei Bedarf Notizen für weitere Maschinenklassen (Pressen, Fördertechnik) ergänzen, sobald Szenarien dafür entstehen.
- **Abkürzungs-Mapping:** Abschnitt 2 als Startliste an die semantische Suche übergeben (Synonym-/Thesaurus-Pflege, `vektor-suche-pgvector.md` §6).
- **Finale Validierung durch Patric:** Checkliste (§7) anwenden; als unecht markierte Beispiele austauschen.

> Hinweis: Alle Namen in der Beispiel-Bibliothek sind frei erfunden und dienen ausschließlich dem NER-Test. Die Notizen sind synthetisch und beschreiben keine reale Anlage oder Person.
