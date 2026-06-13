# Anonymisierung und Pseudonymisierung werkerbezogener Daten im FOREMAN-Adapter-Layer

> Technisches Research-Dokument · Stand Juni 2026
> Scope: DSGVO-konforme Behandlung werkerbezogener Felder in der FOREMAN-Datenpipeline (SPS/OPC UA, MQTT, Modbus → Normalisierung → PostgreSQL/TimescaleDB).
> Betroffene Felder: `worker_notes.author`, `worker_notes.text`, `alarms.acknowledged_by`, `maintenance_events.performed_by`.
> Hinweis zur Architektur: Das semantische Gedächtnis-Substrat wird in diesem Dokument ausschließlich als **externer Dienst hinter einer HTTP-API** behandelt. Über dessen interne Funktionsweise werden keine Annahmen getroffen; alle Schutzmaßnahmen greifen im FOREMAN-Adapter-Layer, *bevor* Daten den Dienst erreichen.

---

## 1. Fragestellung

FOREMAN ist eine Reasoning-Plattform für Produktionsumgebungen. Der Adapter-Layer liest Daten aus industriellen Protokollen ein, normalisiert sie und schreibt sie in eine relationale Zeitreihen-Datenbank. Ein Teil dieser Daten ist personenbezogen: Werker quittieren Alarme, dokumentieren Wartungen und schreiben Schichtberichte im Freitext. Sobald ein Name, eine Personalnummer oder ein eindeutiger Bezug zu einer natürlichen Person verarbeitet wird, gilt die DSGVO.

Privacy by Design (Art. 25 DSGVO) verlangt, dass der Schutz personenbezogener Daten nicht nachträglich aufgesetzt, sondern in die Architektur eingebaut wird — und zwar an der frühestmöglichen Stelle. Im FOREMAN-Datenfluss ist das der Adapter-Layer: Hier wird entschieden, in welcher Form werkerbezogene Felder überhaupt persistiert werden.

Das Dokument beantwortet sechs Forschungsfragen:

1. Wo verläuft rechtlich die Grenze zwischen Anonymisierung und Pseudonymisierung (DSGVO, Art.-29-Gruppe, EDSA, aktuelle Rechtsprechung)?
2. Wie groß ist das Re-Identifikationsrisiko bei Zeitreihen- und Schichtdaten, und welche Gegenmaßnahmen sind praktikabel?
3. Welche konkreten technischen Pseudonymisierungsverfahren eignen sich für den Adapter-Layer?
4. Wie geht man mit Personennamen im Freitext um (NER vor Speicherung, Restrisiko)?
5. Wie verträgt sich Anonymisierung mit dem Ziel eines Langzeitgedächtnisses über Jahre — und wann ist Pseudonymisierung mit Löschfrist der ehrlichere Weg?
6. Welche Strategie ist pro betroffenem Feld zu wählen?

**Klarstellung zur Zielrichtung (wichtig).** Anonymisierung ist im Industrieumfeld **nicht vorgeschrieben** und auch nicht das Ziel dieses Dokuments. Die DSGVO verlangt Datenminimierung (Art. 5 Abs. 1 lit. c), nicht Anonymisierung — Letztere ist nur *ein mögliches Mittel*. Dem steht eine starke, oft **gesetzlich/normativ vorgeschriebene Gegenanforderung** gegenüber: die **Attributierbarkeit** sicherheits- und qualitätsrelevanter Tätigkeiten (wer hat wann was geprüft, quittiert, instand gesetzt). Für solche Records wäre Anonymisierung sogar rechtswidrig. Das auflösende Prinzip — entfaltet in Abschnitt 2.6 und der Empfehlung — ist deshalb **Pseudonymisierung mit kontrollierter Re-Identifikation und Trennung von System of Record und Reasoning-Schicht**, nicht Anonymisierung. (Begriffliche Korrektur ggü. einer früheren Fassung, die Felder pauschal als „anonymisiert" rahmte.)

Der Abschluss (Abschnitt 6) benennt eine eindeutige, baubare Empfehlung. Tradeoffs werden vorher (Abschnitt 4) abgehandelt, nicht im Schluss.

---

## 2. Stand des Rechts und der Technik

### 2.1 Anonymisierung vs. Pseudonymisierung

**Pseudonymisierung** ist in Art. 4 Nr. 5 DSGVO legaldefiniert: die Verarbeitung personenbezogener Daten so, dass sie ohne Hinzuziehung *zusätzlicher Informationen* nicht mehr einer Person zugeordnet werden können, wobei diese Zusatzinformationen gesondert aufzubewahren und durch technisch-organisatorische Maßnahmen (TOM) zu schützen sind. Entscheidend: Pseudonymisierte Daten bleiben **personenbezogen** und damit voll im Anwendungsbereich der DSGVO. Pseudonymisierung ist eine Sicherungsmaßnahme (Art. 32), keine Befreiung von der DSGVO. Sie wird in Art. 25 DSGVO ausdrücklich als Beispiel für Privacy by Design genannt.

**Anonymisierung** ist nicht im verfügenden Teil der DSGVO definiert, sondern in Erwägungsgrund 26: Die Verordnung gilt nicht für „anonyme Informationen, … die sich nicht auf eine identifizierte oder identifizierbare natürliche Person beziehen". Maßstab für „identifizierbar" sind „alle Mittel …, die … nach allgemeinem Ermessen wahrscheinlich genutzt werden" (*means reasonably likely to be used*) — unter Berücksichtigung von Kosten, Zeitaufwand, verfügbarer Technik und deren Entwicklung. Echte Anonymisierung ist **irreversibel** und nimmt die Daten dauerhaft aus dem DSGVO-Regime.

Die **Art.-29-Datenschutzgruppe** hat in der *Opinion 05/2014 on Anonymisation Techniques (WP216)* den bis heute maßgeblichen Prüfrahmen gesetzt. Anonymisierung gilt nur dann als gelungen, wenn drei Re-Identifikationsvektoren ausgeschlossen sind:

- **Singling out** — ein einzelner Datensatz lässt sich isolieren und damit eine Person herausgreifen;
- **Linkability** — Datensätze über eine Person lassen sich über eine oder mehrere Datenbanken hinweg verknüpfen;
- **Inference** — Attribute einer Person lassen sich aus anderen Werten mit hoher Wahrscheinlichkeit ableiten.

Die Gruppe stellt ausdrücklich fest, dass es keine „one-size-fits-all"-Lösung gibt und jede Technik ein Restrisiko trägt. Insbesondere: Pseudonymisierung ist **keine** Anonymisierung — ein häufiger und folgenreicher Irrtum.

**EDSA-Leitlinien 01/2025 zur Pseudonymisierung** (am 16.01.2025 zur Konsultation angenommen) präzisieren den aktuellen Stand. Kernaussagen:

- Pseudonymisierte Daten, die sich mit Zusatzinformation einer Person zuordnen lassen, sind personenbezogene Daten — *auch dann, wenn Pseudonym und Zusatzinformation nicht bei derselben Stelle liegen.*
- Eingeführt wird der Begriff der **„pseudonymisation domain"**: eine Umgebung, in der ausschließlich pseudonymisierte Daten verarbeitet werden und niemand Zugriff auf die zur Re-Identifikation nötige Zusatzinformation hat. Innerhalb dieser Domäne sinkt das Risiko, der Personenbezug verschwindet aber nicht automatisch.
- Pseudonymisierung wird als wirksames Mittel für Datenminimierung, Zweckbindung und die Absicherung von Verarbeitung auf Grundlage berechtigter Interessen bzw. Weiterverarbeitung anerkannt.

**Aktuelle Rechtsprechung — EuGH, EDPS ./. SRB, C-413/23 P (Urteil vom 04.09.2025).** Der EuGH bestätigt einen **kontextuellen, relativen** Begriff des Personenbezugs: Hinreichend stark pseudonymisierte Daten können für den ursprünglichen Verantwortlichen personenbezogen sein, für einen **Empfänger**, der die Pseudonymisierung nicht umkehren und die Personen auch nicht anderweitig identifizieren kann, jedoch *nicht*-personenbezogen. Ob Daten personenbezogen sind, ist also aus der Perspektive der jeweiligen Stelle und der ihr „nach allgemeinem Ermessen wahrscheinlich zur Verfügung stehenden Mittel" zu beurteilen. Das ist eine Abkehr von der lange vertretenen Auffassung der Aufsichtsbehörden, pseudonymisierte Daten seien *stets* personenbezogen.

**Konsequenz für FOREMAN.** Die relative Betrachtung hilft nur einem Empfänger ohne Re-Identifikationsmittel. FOREMAN selbst hält die Nutzdaten *und* (potenziell) die Mapping-Information — innerhalb der Plattform bleiben pseudonymisierte Werkerdaten daher personenbezogen. Der relative Ansatz wird erst relevant, wenn Daten die Plattform verlassen (Export, externer Dienst, Mandantentrennung). Für den internen Datenfluss ist die sichere Annahme: **pseudonymisiert = personenbezogen = DSGVO gilt voll.**

### 2.2 Re-Identifikationsrisiko bei Zeitreihen- und Schichtdaten

Das Kernproblem werkerbezogener Industriedaten ist nicht der Name — den kann man ersetzen — sondern das **Verhaltensmuster**. Ein pseudonymisierter Werker bleibt über folgende Quasi-Identifikatoren angreifbar:

- **Schichtmuster:** Wer in einem 3-Schicht-Betrieb regelmäßig Nachtschicht an Linie 4 fährt, ist in einem kleinen Team oft eindeutig. Der Dienstplan ist die Zusatzinformation.
- **Zeitstempel:** `acknowledged_at`, `performed_at`, `created_at` korrelieren mit Anwesenheitszeiten. Die zeitliche Abfolge von Ereignissen ist selbst ein Quasi-Identifikator — die *Sequenz* trägt mehr Identifikationskraft als jeder Einzelwert.
- **Maschinenzuordnung:** `machine_id`/`component_id` plus Qualifikationsprofil grenzt den Personenkreis stark ein. Nur wenige Werker sind für eine bestimmte Anlage zertifiziert.
- **Stilometrie im Freitext:** Schreibstil, wiederkehrende Formulierungen und Tippfehler in Schichtberichten erlauben Autorschafts-Zuordnung selbst ohne Namensnennung.

Verschärfend wirkt der **Fluch der Dimensionalität**: Je mehr Merkmale ein Datensatz trägt, desto eindeutiger wird jede Kombination. In hochdimensionalen Schicht-/Ereignisdaten ist faktisch jeder Datensatz ein Unikat — klassische Anonymisierung scheitert dann an akzeptablem Informationsverlust. Genau das ist der Grund, warum echte Anonymisierung von granularen Zeitreihen mit Personenbezug in der Praxis selten gelingt.

**Formale Schutzmodelle** (Microdata-Privacy):

- **k-Anonymität** (Sweeney, 2002): Jede Kombination von Quasi-Identifikatoren kommt mindestens *k*-mal vor; ein Datensatz ist nicht von mindestens *k*−1 anderen zu unterscheiden. Schützt gegen *singling out*, nicht gegen Inferenz.
- **l-Diversität** (Machanavajjhala et al., 2007): Zusätzlich müssen in jeder Äquivalenzklasse mindestens *l* „gut repräsentierte" Werte des sensiblen Attributs vorkommen. Schützt gegen Attribut-Inferenz bei homogenen Klassen.
- **t-Closeness** (Li et al., 2007): Die Verteilung des sensiblen Attributs in jeder Äquivalenzklasse darf höchstens um den Schwellwert *t* (Earth-Mover-Distanz) von der Gesamtverteilung abweichen. Schützt gegen Verteilungs-/Skewness-Angriffe.

Diese Modelle stammen aus der **Veröffentlichung statischer Mikrodatensätze**. Auf eine *kontinuierlich wachsende, granular zeitgestempelte* Betriebsdatenbank sind sie nur eingeschränkt anwendbar: k-Anonymität auf einem fortlaufenden Stream zu garantieren erfordert Generalisierung/Aggregation, die die Zeitauflösung zerstört — und damit genau die Signale, die FOREMANs Reasoner (Ereignisketten, Drift, Ausfallvorhersage) brauchen. Sie sind als **Audit-/Freigabe-Werkzeug für Exporte** wertvoll, nicht als Speicherformat der Live-Pipeline.

Praktikable Gegenmaßnahmen für die Pipeline sind daher abgestuft:

- **Trennung von Identität und Verhalten:** Wer (`author`/`acknowledged_by`/`performed_by`) wird tokenisiert; was/wann/wo bleibt erhalten. Das senkt *singling out* über den Namen, lässt das Reasoning aber unangetastet.
- **Generalisierung von Zeit für Exporte/Reports:** Zeitstempel auf Schicht- oder Tagesebene gröbern (Datums-Jittering / Bucketing), wenn Daten aggregiert nach außen gehen.
- **Aggregation/Suppression seltener Klassen** in jeder Auswertung, die einen Personenbezug herstellen könnte (z. B. „Wartungen pro Werker" nie unter k anzeigen).
- **Zugriffstrennung** statt Datenlöschung: Re-Identifikation technisch und organisatorisch auf einen kleinen, protokollierten Kreis beschränken (Mapping-Tabelle, RBAC, Audit-Log).

### 2.3 Verfahren der Pseudonymisierung im Adapter-Layer

ENISA (*Pseudonymisation techniques and best practices*) und die einschlägige Praxis unterscheiden:

**Deterministisch vs. randomisiert.**

- *Deterministisch:* Gleicher Klartext → gleiches Pseudonym. Erhält die referenzielle Integrität (derselbe Werker ist über Jahre als dieselbe Pseudo-ID erkennbar) — Voraussetzung für jede Längsschnitt-Analyse („hatten wir das schon mal mit diesem Werker?"). Preis: anfällig für Wörterbuch-/Korrelationsangriffe, wenn das Verfahren ungeschützt ist.
- *Randomisiert:* Gleicher Klartext → unterschiedliche Pseudonyme (z. B. Zufalls-Token pro Ereignis). Höchster Schutz, aber zerstört die Verknüpfbarkeit über Ereignisse — für FOREMANs Gedächtnis-Anspruch unbrauchbar bei Feldern, die einen Werker über Zeit identifizieren sollen.

Für FOREMAN ist **deterministische Pseudonymisierung mit kryptographischem Schlüssel** der relevante Pfad, weil die Plattform Werker-Bezüge über die Zeit konsistent halten muss, ohne den Klartext-Namen zu speichern.

**HMAC-basierte Tokenisierung.** Ein HMAC (z. B. HMAC-SHA-256) ist ein *keyed hash*: Pseudonym = HMAC(secret_key, identifier). ENISA bewertet HMAC als robuste Pseudonymisierungstechnik — ohne Kenntnis des Schlüssels ist die Umkehrung praktisch unmöglich. Der **kritische Fehler**, den ENISA explizit nennt, ist die Verwendung eines *ungekeyten* Hashes (z. B. nacktes SHA-256 über den Namen): Bei kleinem Wertebereich (eine Handvoll Werkernamen, Personalnummern als fortlaufende Zahlen) ist ein solcher Hash in Sekunden per Brute-Force/Rainbow-Table umkehrbar. Der geheime Schlüssel ist das, was den Angriff verhindert.

**Salt und Pepper.**

- *Pepper* = ein geheimer, systemweiter Schlüssel (der HMAC-Key), getrennt von der Datenbank gespeichert. Schützt den gesamten Bestand, wenn die DB kompromittiert wird.
- *Salt* = ein pro-Eintrag- oder pro-Kontext-Wert. Beim deterministischen Bedarf darf der Salt **nicht** pro Datensatz zufällig sein (sonst keine Konsistenz). Sinnvoll ist ein *kontextgebundener* Salt (z. B. pro Mandant/Standort), um identische Namen über Mandantengrenzen hinweg auf verschiedene Token abzubilden und mandantenübergreifende Linkability zu verhindern.

**Key-Rotation.** Schlüssel sind regelmäßig zu wechseln, um den Schaden einer Kompromittierung zu begrenzen. Das kollidiert mit der deterministischen Langzeit-Konsistenz: Nach einem Schlüsselwechsel ergibt derselbe Name ein neues Token. Auflösungen:

- **Versionierte Schlüssel:** Jedes Token trägt eine Key-Version (`v2:ab12…`). Alte Token bleiben lesbar, neue Ereignisse nutzen den neuen Schlüssel. Längsschnitt-Analysen, die über eine Rotation hinausgehen, brauchen eine Mapping-Tabelle als Brücke (siehe unten).
- **Re-Tokenisierung** des Bestands bei Rotation (teuer, nur bei Schlüsselkompromittierung) — setzt eine Mapping-Tabelle voraus.

**Trennung von Mapping-Tabelle und Nutzdaten.** Sobald Re-Identifikation jemals nötig ist (rechtlich: Auskunfts-/Löschverlangen nach Art. 15/17; betrieblich: Human-in-the-Loop-Nachvollzug, wer einen Sicherheitsalarm quittiert hat), darf der Bezug nicht verloren gehen. Architektur:

- Nutzdatenbank speichert **nur** das Token.
- Eine **getrennte, stärker geschützte** Mapping-Tabelle hält `token ↔ user_id` (bzw. `user_id ↔ Klartext` in der `users`-Tabelle). Anderes Schema/anderer Datenbank-Account, eigene Zugriffskontrolle, Audit-Log auf jeden Lesezugriff, kein Default-Join.
- Damit entsteht faktisch eine **„pseudonymisation domain"** im Sinne der EDSA-Leitlinien: Die Reasoning-Pipeline arbeitet ausschließlich auf Token; die Zusatzinformation liegt isoliert.

Reine HMAC-Tokenisierung *ohne* Mapping ist genau genommen eine Einwegfunktion mit der `users`-Tabelle als impliziter „Mapping-Tabelle" (man kann ein bekanntes `user_id`-Set durchrechnen und vergleichen). Das ist gewollt: Es erlaubt gezielte Re-Identifikation für berechtigte Zwecke, ohne eine separate Token-Tabelle zu pflegen — solange der Klartext-Bestand der Werker (die `users`-Tabelle) endlich und kontrolliert ist.

### 2.4 Sonderfall Freitext: Schichtberichte (`worker_notes.text`)

Der Freitext ist der gefährlichste Pfad, weil Personennamen *unstrukturiert* auftauchen („Hab mit Schmidt aus der Frühschicht getauscht", „Müller meint, das Lager läuft heiß"). Tokenisierung greift hier nicht — man muss die Namen erst **finden**, bevor man sie ersetzen kann. Werkzeug der Wahl ist **Named-Entity-Recognition (NER)** mit Fokus auf die Entität `PER` (Person), vorgelagert vor der Speicherung.

**Deutsche NER-Modelle im Vergleich (Stand Mitte 2026, Versionen vor Einsatz prüfen):**

| Modell / Framework | Typ | PER-Güte (Anhalt) | Latenz/Footprint | Eignung FOREMAN |
|---|---|---|---|---|
| spaCy `de_core_news_lg` (3.8.x) | CNN-Pipeline | F1 ≈ 85 (Self-Report, CoNLL-ähnl.) | sehr schnell, CPU, ~560 MB | Default-Pfad, gut integrierbar |
| Flair `ner-german-large` (0.15.x) | Transformer (XLM-R) | F1 ≈ 92 (CoNLL-03 de, revised) | langsamer, GPU empfohlen | höchste Trefferquote, höhere Kosten |
| Transformer-Encoder direkt (XLM-RoBERTa / GBERT, fine-tuned) | Transformer | je nach Fine-Tuning ≥ Flair | GPU | wenn eigene Annotation vorhanden |
| Microsoft **Presidio** (Analyzer 2.2.x) als Orchestrator | NER + Regex + Checks | hängt vom NLP-Engine ab | mittel | empfohlen als Rahmen, kapselt spaCy/Flair |
| LLM-basierte NER (lokales Qwen3 via Gateway) | generativ | in 2025er-Studien 7–22 % über spaCy/Flair auf schwierigen Texten | hoch (Tokenkosten/Latenz) | Fallback/Review, nicht im heißen Pfad |

**Tradeoffs.** spaCy ist schnell und billig, übersieht aber mehr (niedrigere Recall) — gefährlich, weil ein *übersehener* Name ungeschützt in die DB läuft. Flair/Transformer fangen mehr, kosten Latenz und (bei GPU) Hardware. LLM-NER ist am stärksten auf „schmutzigen" Texten (Industrie-Jargon, Tippfehler, gemischte Sprache), aber zu teuer/langsam für jeden eingehenden Bericht und bringt eigene Risiken (Prompt-Injection über den Freitext-Pfad — bereits als Red-Teaming-Punkt LLM01 in den Quality Gates verankert).

**Restrisiko — der entscheidende Punkt.** NER hat **keinen** Recall von 100 %. Jeder übersehene Name ist ein ungeschützter Personenbezug. Daraus folgen zwei nicht verhandelbare Konsequenzen:

1. NER ist eine **Risikominderung, keine Garantie.** Der Freitext bleibt auch nach NER potenziell personenbezogen und muss entsprechend behandelt werden (Zugriffskontrolle, Löschfrist), darf also nicht als „anonym" deklariert werden.
2. **Defense in depth:** NER (Recall-orientiert konfiguriert) + organisatorische Regel („keine vollen Namen in Schichtberichte") + Löschfrist auf dem Rohtext + Zugriffsbeschränkung. Optional ein zweiter, strengerer Pass (Flair oder LLM) als Review für als `kritisch` klassifizierte Berichte.

### 2.5 Aufbewahrung, Löschung und das Langzeitgedächtnis-Ziel

Hier liegt der eigentliche Zielkonflikt. FOREMANs Wert ist das **Gedächtnis über Jahre** — „hatten wir das schon mal?" über die ganze Maschinenklasse. Die DSGVO verlangt aber **Speicherbegrenzung** (Art. 5 Abs. 1 lit. e): Personenbezogene Daten dürfen nur so lange in identifizierbarer Form vorgehalten werden, wie für den Zweck nötig. Dazu kommt das **Recht auf Löschung** (Art. 17).

Zwei ehrliche Wege, einer unehrlicher:

- **Echte Anonymisierung** nimmt Daten dauerhaft aus dem DSGVO-Regime — *wenn* sie irreversibel ist und singling out/linkability/inference ausschließt. Bei granularen, zeitgestempelten Werker-Verhaltensdaten ist das (siehe 2.2) praktisch kaum erreichbar, ohne genau die Signale zu zerstören, die FOREMAN braucht. Anonymisierung der **Verhaltensschicht** (Zeitreihen, Alarme, Wartungen *ohne* Personenfeld) ist dagegen meist unproblematisch, weil dort gar kein Personenbezug entsteht.
- **Pseudonymisierung mit definierter Löschfrist** ist der *ehrliche* Weg für das Personenfeld: Der Werker-Bezug bleibt so lange erhalten, wie er einen legitimen Zweck erfüllt (z. B. Audit-Pflicht, HITL-Nachvollzug), und wird danach gezielt aufgelöst. Die Verhaltensdaten bleiben — nur die Brücke zur Person verschwindet.
- **„Pseudo-Anonymisierung"** — Daten als „anonym" zu deklarieren, die über Schichtmuster/Zeitstempel re-identifizierbar bleiben — ist der unehrliche Weg. Er erzeugt Scheinsicherheit, hält einer WP216-Prüfung nicht stand und ist bei öffentlichem Repo und externer Vorführung ein Reputations- und Haftungsrisiko.

**Crypto-Shredding als Brücke.** Statt Zeilen zu löschen (was Zeitreihen-Integrität und referenzielle Bezüge zerstört), verschlüsselt man die Mapping-/Personeninformation pro Person mit einem eigenen Schlüssel und **vernichtet bei Löschverlangen nur den Schlüssel**. Die Verhaltensdaten bleiben intakt, der Personenbezug ist irreversibel weg. EDSA (Leitlinien 5/2019 zum Recht auf Vergessenwerden in Suchmaschinen — analog herangezogen), ICO und CNIL erkennen Schlüsselvernichtung als wirksame Löschung an, sofern starke Verschlüsselung (AES-256), irreversible und **auditierbare** Schlüsselvernichtung sowie **pro-Entität-Schlüsselisolation** vorliegen. Das ist die technisch sauberste Auflösung des Konflikts „Langzeitgedächtnis vs. Löschpflicht": Das Gedächtnis über *Maschinen und Vorfälle* bleibt vollständig; das Gedächtnis über *die Person* ist abschaltbar.

### 2.6 Attributierbarkeit als gesetzliche Gegenanforderung im Industrieumfeld

Bisher betrachtet dieser Abschnitt nur die Schutz-Richtung. Im Industrieumfeld existiert die **entgegengesetzte, häufig zwingende Anforderung**: Bestimmte Tätigkeiten müssen **eindeutig einer identifizierbaren Person zugeordnet** bleiben — wer hat geprüft, quittiert, instand gesetzt. Das ist keine schlechte Gewohnheit, sondern geltendes Recht und Normwerk:

- **Betriebssicherheitsverordnung (BetrSichV) §14 i. V. m. TRBS 1203:** Prüfpflichtige Arbeitsmittel werden durch eine *befähigte Person* geprüft, die ein **Prüfprotokoll mit Name, Unterschrift und Prüfdatum** erstellt. Es dient als Nachweis gegenüber Berufsgenossenschaft, Behörden und Versicherern. Anonym ist dieser Nachweis wertlos.
- **Arbeitsschutzgesetz (ArbSchG) §6:** Dokumentationspflicht für Gefährdungsbeurteilungen und Maßnahmen.
- **DGUV-Vorschriften** (z. B. DGUV V3 für elektrische Betriebsmittel): wiederkehrende Prüfungen mit dokumentiertem, zurechenbarem Prüfer; ebenso die Dokumentation von Erste-Hilfe-Leistungen (Verbandbuch) — selbst personenbezogen und mit eigenen Aufbewahrungs-/Schutzregeln.
- **Qualitätsmanagement (ISO 9001) und regulierte Branchen** (Pharma/GMP, Automotive IATF 16949, Luftfahrt AS9100): Rückverfolgbarkeit „wer hat was getan" ist Pflicht.

**Daraus folgt zweierlei.** Erstens: Anonymisierung ist für solche Records nicht nur unnötig, sondern **rechtlich falsch** — sie zerstört einen vorgeschriebenen Nachweis. Die passende Rechtsgrundlage ist hier **Art. 6 Abs. 1 lit. c DSGVO** (Erfüllung einer rechtlichen Verpflichtung), ergänzend lit. f (berechtigtes Interesse an Betriebssicherheit/Qualität). Zweitens: Beschäftigten-Spezifika sind in Bewegung — §26 BDSG wurde durch die EuGH-Rechtsprechung (C-34/21) angezählt, eine Neuregelung (Beschäftigtendatengesetz) ist in Arbeit; die hier genutzten Fachgesetz-Grundlagen (BetrSichV, ArbSchG) sind davon unberührt.

**Auflösung — Trennung von System of Record und Reasoning-Schicht.** Der Widerspruch „Unterschriftspflicht vs. Datenschutz" löst sich, sobald man zwei Rollen trennt:

1. **System of Record (attributierbar, gesetzlich gefordert):** das unterschriebene Prüf-/Wartungsprotokoll bzw. der namentliche Eintrag im QM-System, in der `users`-Tabelle und im `audit_logs`. Hier bleibt der Klartext-Personenbezug erhalten, unter Art. 6 Abs. 1 lit. c, mit gesetzlicher Aufbewahrungsfrist, Zugriffskontrolle und Protokollierung. **FOREMAN ist nicht dieses System of Record für die Signatur** — die rechtsverbindliche Zuordnung lebt dort, wo sie hingehört.
2. **Reasoning-/Analytics-Schicht (pseudonymisiert):** FOREMANs Reasoner brauchen für „hatten wir das schon mal" nicht den *Namen*, sondern eine **stabile Identität**. Sie sehen nur das Token. Die kontrollierte, auditierte Rück-Auflösung Token→Person steht nur für die Fälle bereit, in denen Attributierbarkeit rechtlich angefordert wird (Auskunft, behördlicher Nachweis, HITL-Quittierungs-Audit).

Damit ist Datenminimierung (Reasoning-Schicht sieht keine Klarnamen) **und** Attributierbarkeit (System of Record + kontrollierte Rück-Auflösung) gleichzeitig erfüllt — ohne Anonymisierung, die beides verfehlen würde.

---

## 3. Verfahren im Vergleich

| Verfahren | Reversibel? | Konsistenz über Zeit | Schutz gegen Re-ID (Name) | DSGVO-Status der Ausgabe |
|---|---|---|---|---|
| Klartext speichern | — | ja | keiner | personenbezogen, nicht zulässig |
| Ungekeytes SHA-256 | nein (theoret.) | ja | **schwach** (Brute-Force bei kleinem Raum) | personenbezogen |
| **HMAC-SHA-256 (keyed)** | nein, ohne Key | ja (deterministisch) | stark, solange Key geheim | pseudonymisiert (personenbezogen) |
| Zufalls-Token + Mapping-Tabelle | ja, via Mapping | ja | stark | pseudonymisiert (personenbezogen) |
| Zufalls-Token ohne Mapping | nein | **nein** (Verknüpfung weg) | sehr stark | Richtung anonym, aber Längsschnitt verloren |
| k-Anonymität/Generalisierung | nein | nein (Auflösung zerstört) | stark gegen singling out | je nach Restrisiko |
| Crypto-Shredding (Schlüssel je Person) | bis Vernichtung | ja | stark; nach Shred irreversibel | pseudonym → nach Shred anonym/gelöscht |
| NER-Maskierung im Freitext | nein | n/a | **unvollständig** (Recall < 100 %) | personenbezogen (Restrisiko) |

---

## 4. Tradeoff-Analyse

Vier Achsen sind gegeneinander abzuwägen: **Schutzniveau**, **Implementierungsaufwand**, **Auswirkung auf die Reasoning-Qualität** und **Reversibilität** (für Rechte-Wahrnehmung und HITL).

| Verfahren | Schutzniveau | Impl.-Aufwand | Reasoning-Qualität | Rev. für Rechte/HITL |
|---|---|---|---|---|
| HMAC-SHA-256, versionierter Key | hoch | niedrig | unverändert (Token ist stabile ID) | nur über `users`-Abgleich |
| Zufalls-Token + getrennte Mapping-Tabelle | hoch | mittel | unverändert | ja, sauber |
| Zufalls-Token ohne Mapping | sehr hoch | niedrig | **degradiert** (kein Werker-Längsschnitt) | nein |
| k-Anonymität/Aggregation auf Live-Daten | hoch | hoch | **stark degradiert** (Zeitauflösung weg) | nein |
| Crypto-Shredding (zusätzlich) | hoch→vollständig | mittel-hoch | unverändert bis Shred | ja (gezielt abschaltbar) |
| spaCy-NER Freitext | mittel | niedrig | n/a (nur Freitext) | nein |
| Flair/Transformer-NER Freitext | hoch | mittel | n/a | nein |
| LLM-NER Freitext | sehr hoch | hoch (Latenz/Kosten) | n/a | nein |

Lesart für FOREMAN: Für die strukturierten Personenfelder kostet starke Pseudonymisierung **nichts** an Reasoning-Qualität, solange die Werker-ID stabil bleibt — der Reasoner braucht „derselbe Werker", nicht „Werker heißt Müller". Damit fällt die Abwägung leicht zugunsten deterministischer Pseudonymisierung. Verfahren, die die Verknüpfbarkeit zerstören (Zufalls-Token ohne Mapping, k-Anonymität auf Live-Daten), opfern genau den Kern des Produkts und sind nur für **Exporte/Reports** sinnvoll, nicht für die Live-Pipeline. Beim Freitext ist der Tradeoff Recall vs. Kosten: Ein verpasster Name wiegt schwerer als CPU-Zeit, also Recall priorisieren — aber nicht den teuersten Pfad (LLM) in den heißen Aufnahmepfad legen.

---

## 5. Empfehlung für FOREMAN

Leitprinzip: **Trenne Identität von Verhalten am Adapter-Layer und trenne System of Record von Reasoning-Schicht. Die rechtsverbindliche, attributierbare Zuordnung (unterschriebenes Protokoll, QM-System, `users`-Tabelle, `audit_logs`) bleibt namentlich unter Art. 6 Abs. 1 lit. c — FOREMAN ist nicht das System of Record für die Signatur. In der Reasoning-/Nutzdatenbank dagegen niemals Klartext-Personenbezug: dort steht nur ein deterministisches, geschütztes Token. Die Werker-Identität lebt allein in `users`; die Rück-Auflösung Token→Person ist kontrolliert, auditiert und nur für rechtlich/betrieblich berechtigte Zwecke verfügbar. Der Personenbezug ist pro Person abschaltbar (Crypto-Shredding). Ziel ist Pseudonymisierung mit kontrollierter Re-Identifikation, nicht Anonymisierung.**

### 5.1 Strategie pro Feld

Alle drei Felder werden **pseudonymisiert (Token), nicht anonymisiert.** Sie unterscheiden sich nur im Grad der geforderten Attributierbarkeit und damit in Löschfrist und Rechtsgrundlage.

**`maintenance_events.performed_by`, `alarms.acknowledged_by`** — **Accountability-Felder mit (potenzieller) gesetzlicher Nachweispflicht.** Wer eine prüfpflichtige Wartung durchführt (BetrSichV §14/TRBS 1203, DGUV) bzw. einen Safety-Alarm quittiert (Human-in-the-Loop, BSI, Quality Gates), muss zurechenbar bleiben. Das ist der **natürliche Gegenspieler von Anonymisierung** — echte Anonymisierung wäre hier rechtlich falsch.
→ **Deterministische HMAC-SHA-256-Tokenisierung** über `users.id` (versionierter Schlüssel) in der Nutzdatenbank, mit **verlässlicher, auditierter Re-Identifizierbarkeit** über den `users`-Abgleich. Rechtsgrundlage Art. 6 Abs. 1 lit. c; Löschfrist an die jeweilige gesetzliche Aufbewahrungs-/Nachweispflicht gekoppelt (länger als bei Notizen). Der **rechtsverbindliche, namentliche Nachweis** lebt nicht in FOREMAN, sondern im Prüf-/Wartungsprotokoll bzw. QM-System (System of Record); FOREMAN hält das Token plus die kontrollierte Brücke dorthin.

**`worker_notes.author`** — weicher: betrieblich nützlich (Längsschnitt, „wer hat hier schon gearbeitet"), in der Regel ohne eigene gesetzliche Attributierungspflicht.
→ Gleiche **HMAC-Tokenisierung** über `users.id`; Klartext nur in `users`; Re-Identifikation für Auskunfts-/Löschverlangen (Art. 15/17) über kontrollierten `users`-Abgleich. Kürzere Löschfrist als bei den Accountability-Feldern.

**`worker_notes.text`** (Freitext) — höchstes Restrisiko.
→ **NER-Maskierung vor der Speicherung** über **Presidio als Orchestrator** mit **spaCy `de_core_news_lg` im heißen Pfad** (Recall-orientiert konfiguriert), Ersetzung erkannter `PER`-Entitäten durch ein **stabiles Token** (so dass „Schmidt" im Text auf dasselbe Token abbildet wie `users`-Werker Schmidt, wenn zuordenbar — sonst auf ein generisches `[PERSON_n]`). Für als `kritisch` klassifizierte Berichte optional ein zweiter, strengerer Pass (Flair `ner-german-large` oder lokales LLM via Gateway). Rohtext mit definierter Löschfrist, Zugriffsbeschränkung, und organisatorische Regel „keine vollen Namen". Der Freitext wird **nie als anonym deklariert.**

**Verhaltensschicht** (`readings`, `alarms` außer `acknowledged_by`, `production_runs`, Maschinenbezug) — kein Personenfeld, daher kein Personenbezug, keine Sondermaßnahme nötig. **Vorsicht** bei Auswertungen/Exporten, die über `machine_id` + Zeit + seltene Schichtbesetzung indirekt re-identifizieren: dort Aggregation und Suppression unter k.

**Übergreifend — Löschpfad:** `users`-Datensatz (Klartext + ggf. pro-Werker-Schlüssel) per **Crypto-Shredding** abschaltbar. Wird ein Werker gelöscht, verschwindet der Personenbezug aller Token irreversibel; Verhaltensdaten und das Maschinen-Gedächtnis bleiben vollständig.

### 5.2 Konkrete Bausteine (Version vor Einsatz prüfen, Stand Mitte 2026)

- Tokenisierung: Python-Standardbibliothek `hmac` + `hashlib` (SHA-256). Schlüsselverwaltung über die `cryptography`-Bibliothek (≥ 43.x) bzw. ein KMS/Vault. Kein Fremd-Dependency für den Kern nötig.
- Freitext-NER: `presidio-analyzer` (2.2.x) als Rahmen, NLP-Engine `spacy` (3.8.x) mit `de_core_news_lg` (3.8.0). Zweitpass optional `flair` (0.15.x), Modell `flair/ner-german-large`.
- Schlüssel liegen in Umgebungsvariablen/Secret-Store (`.env`, niemals im Repo — das ist öffentlich). Key-Version als Präfix im Token.

### 5.3 Kopierbare Konfiguration und Code

**(a) HMAC-Tokenisierung im Adapter-Layer**

```python
# foreman/adapters/pseudonymize.py
import hmac
import hashlib
import os

# Pepper (systemweiter Geheimschlüssel) NICHT im Repo. Aus Secret-Store laden.
# Format erlaubt Key-Rotation: aktive Version + Historie.
_ACTIVE_KEY_VERSION = os.environ["FOREMAN_PSEUDO_KEY_VERSION"]            # z.B. "v2"
_KEYS: dict[str, bytes] = {
    # Version -> 32-Byte-Key (hex in der Env, hier dekodiert)
    v: bytes.fromhex(os.environ[f"FOREMAN_PSEUDO_KEY_{v}"])
    for v in os.environ["FOREMAN_PSEUDO_KEY_VERSIONS"].split(",")          # z.B. "v1,v2"
}


def tokenize_worker(user_id: str, *, tenant: str = "default") -> str:
    """Deterministisches, schlüsselgebundenes Pseudonym für eine Werker-ID.

    - Gebunden an user_id (nicht an den Klartext-Namen): stabil über Namensänderungen.
    - tenant als kontextgebundener Salt: gleiche ID -> je Mandant anderes Token
      (verhindert mandantenuebergreifende Verknuepfung).
    - Key-Version im Praefix: erlaubt Rotation ohne Verlust der Lesbarkeit alter Token.
    """
    key = _KEYS[_ACTIVE_KEY_VERSION]
    msg = f"{tenant}:{user_id}".encode("utf-8")
    digest = hmac.new(key, msg, hashlib.sha256).hexdigest()
    return f"{_ACTIVE_KEY_VERSION}:{digest}"


def verify_token(user_id: str, token: str, *, tenant: str = "default") -> bool:
    """Prueft ein bekanntes user_id gegen ein Token (gezielte Re-ID fuer berechtigte Zwecke).

    Nutzt die im Token kodierte Key-Version, damit auch vor einer Rotation
    erzeugte Token weiterhin verifizierbar bleiben.
    """
    try:
        version, _ = token.split(":", 1)
        key = _KEYS[version]
    except (ValueError, KeyError):
        return False
    msg = f"{tenant}:{user_id}".encode("utf-8")
    expected = f"{version}:{hmac.new(key, msg, hashlib.sha256).hexdigest()}"
    return hmac.compare_digest(expected, token)   # zeitkonstanter Vergleich
```

**(b) Freitext-Maskierung mit Presidio + spaCy (de)**

```python
# foreman/adapters/redact_freetext.py
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

# spaCy de_core_news_lg als NLP-Engine. Vorher:
#   python -m spacy download de_core_news_lg
_provider = NlpEngineProvider(nlp_configuration={
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "de", "model_name": "de_core_news_lg"}],
})
_analyzer = AnalyzerEngine(nlp_engine=_provider.create_engine(), supported_languages=["de"])
_anonymizer = AnonymizerEngine()


def redact_person_names(text: str) -> str:
    """Maskiert Personennamen (PER) im Schichtbericht VOR der Speicherung.

    Recall-orientiert (score_threshold niedrig): lieber zu viel maskieren.
    Restrisiko bleibt (NER-Recall < 100 %) -> Rohtext mit Loeschfrist + Zugriffsschutz,
    Freitext wird NIE als anonym deklariert.
    """
    results = _analyzer.analyze(
        text=text, language="de", entities=["PERSON"], score_threshold=0.35,
    )
    return _anonymizer.anonymize(
        text=text, analyzer_results=results,
        operators={"PERSON": OperatorConfig("replace", {"new_value": "[PERSON]"})},
    ).text
```

**(c) Empfohlene Schema-Notiz (GROUND_TRUTH §5)**

```
worker_notes.author          : TEXT  -- HMAC-Token "v{n}:{64-hex}", nie Klartext
maintenance_events.performed_by : TEXT  -- HMAC-Token (s.o.)
alarms.acknowledged_by       : TEXT  -- HMAC-Token; re-identifizierbar fuer HITL-Audit
worker_notes.text            : TEXT  -- NER-maskiert vor Insert; Loeschfrist; Zugriffsschutz
-- Klartext-Identitaet ausschliesslich in users (id, email, name, ...).
-- Optional: users.crypto_key fuer pro-Werker Crypto-Shredding bei Art.-17-Loeschung.
-- BEGRIFFS-KORREKTUR: GROUND_TRUTH §5 bezeichnet diese Felder bislang als
-- "(anonymisiert)". Das ist falsch -> auf "(pseudonymisiert, HMAC-Token)" aendern.
-- maintenance_events.performed_by / alarms.acknowledged_by zusaetzlich kommentieren:
-- "Nachweis-Bezug; rechtsverbindlicher namentlicher Record im Pruef-/Wartungsprotokoll
--  bzw. QM-System (System of Record), nicht in FOREMAN".
```

**(d) Schlüssel/Env (öffentliches Repo: nur Beispiel in `.env.example`, echte Werte im Secret-Store)**

```dotenv
# .env.example  -- NIEMALS echte Schluessel committen
FOREMAN_PSEUDO_KEY_VERSION=v2
FOREMAN_PSEUDO_KEY_VERSIONS=v1,v2
FOREMAN_PSEUDO_KEY_v1=<32-byte-hex>   # alter Key, nur noch zum Lesen
FOREMAN_PSEUDO_KEY_v2=<32-byte-hex>   # aktiver Key; mit: openssl rand -hex 32
```

---

## 6. Offene Punkte

- **AI-Act-Wechselwirkung:** Falls Werker-bezogene Empfehlungen je Arbeitsschutz-Kontext berühren, ist die Hochrisiko-Frage neu zu prüfen; die Pseudonymisierungsstrategie ändert sich dadurch nicht, die Dokumentationspflichten schon.
- **Löschfristen konkretisieren:** Pro Feld eine begründete Frist festlegen (`worker_notes` kürzer; `maintenance_events.performed_by`/`alarms.acknowledged_by` an die jeweilige gesetzliche Nachweis-/Aufbewahrungspflicht koppeln, z. B. BetrSichV-Prüfnachweise). Erfordert Klärung mit dem Pilotkunden, welche Vorschriften (BetrSichV, DGUV, QM-Norm, Branchenrecht) konkret greifen.
- **Abgrenzung System of Record klären:** Pro Pilotkunde festhalten, *welches* System der rechtsverbindliche, namentliche Nachweis ist (Papier-Protokoll, QM-/CMMS-System) und wie FOREMANs Token-Brücke dorthin (für berechtigte Re-ID) konkret aussieht. FOREMAN darf diese Rolle nicht versehentlich übernehmen.
- **Pro-Werker-Crypto-Shredding vs. globaler Key:** Pro-Entität-Schlüssel sind sauberer für Art. 17, erhöhen aber die Schlüsselverwaltungs-Komplexität. Entscheidung an erwartetes Löschvolumen koppeln.
- **NER-Recall messen:** Vor Produktivsetzung an realen (anonymisierten) Schichtberichten Recall/Precision von spaCy vs. Flair bestimmen; Schwellwert und Zweitpass-Politik daran festmachen.
- **Stilometrie-Restrisiko:** Bislang nur benannt, nicht adressiert. Für den MVP akzeptabel (kleiner, interner Empfängerkreis), für externe Exporte erneut bewerten.
- **Export-Pfad:** Sobald aggregierte Daten die Plattform verlassen, greifen k-Anonymität/Suppression und der relative Personenbezug (C-413/23 P) — eigener Freigabe-Check nötig, der hier nur skizziert ist.

---

## Quellen

- DSGVO (Verordnung (EU) 2016/679): Art. 4 Nr. 5 (Pseudonymisierung), Art. 5 Abs. 1 lit. e (Speicherbegrenzung), Art. 17 (Recht auf Löschung), Art. 25 (Datenschutz durch Technikgestaltung), Art. 32 (Sicherheit der Verarbeitung), Erwägungsgrund 26 (Identifizierbarkeit, „means reasonably likely to be used").
- Art.-29-Datenschutzgruppe, *Opinion 05/2014 on Anonymisation Techniques (WP216)*, 10.04.2014. https://ec.europa.eu/justice/article-29/documentation/opinion-recommendation/files/2014/wp216_en.pdf
- EDSA (EDPB), *Guidelines 01/2025 on Pseudonymisation*, angenommen 16.01.2025 (Konsultationsfassung). https://www.edpb.europa.eu/system/files/2025-01/edpb_guidelines_202501_pseudonymisation_en.pdf
- EuGH, *EDPS ./. SRB*, C-413/23 P, Urteil vom 04.09.2025 (relativer/kontextueller Personenbezug pseudonymisierter Daten). Analysen: FPF, Goodwin, Jones Day, Bird & Bird, Skadden (Sept.–Nov. 2025).
- P. Sweeney, *k-anonymity: a model for protecting privacy*, IJUFKS, 2002.
- A. Machanavajjhala et al., *l-diversity: Privacy beyond k-anonymity*, ICDE/TKDD, 2006/2007.
- N. Li, T. Li, S. Venkatasubramanian, *t-Closeness: Privacy Beyond k-Anonymity and l-Diversity*, ICDE 2007. https://www.cs.purdue.edu/homes/ninghui/papers/t_closeness_icde07.pdf
- ENISA, *Pseudonymisation techniques and best practices* (HMAC als robuste Technik; ungekeyter Hash als Fehler; Key-Rotation). https://www.enisa.europa.eu/publications
- Future of Privacy Forum, *The Curse of Dimensionality: De-identification Challenges in the Sharing of Highly Dimensional Datasets*. https://fpf.org/blog/the-curse-of-dimensionality-de-identification-challenges-in-the-sharing-of-highly-dimensional-datasets/
- Crypto-Shredding als Art.-17-Löschung (Anerkennung durch EDPB-Leitlinien, ICO, CNIL; AES-256, irreversibel, auditierbar, pro-Entität-Schlüssel): Branchen-Praxisquellen 2025/2026.
- spaCy German models (`de_core_news_lg`). https://spacy.io/models/de · Flair `ner-german-large` (CoNLL-03 de). · Microsoft Presidio. https://microsoft.github.io/presidio/
- NER4all / *Context is All You Need* (LLM-NER vs. spaCy/Flair, 2025). https://arxiv.org/abs/2502.04351
- Attributierbarkeits-/Nachweispflichten Industrie: Betriebssicherheitsverordnung (BetrSichV) §14 i. V. m. TRBS 1203 (Prüfprotokoll der befähigten Person mit Name/Unterschrift/Datum); Arbeitsschutzgesetz (ArbSchG) §6 (Dokumentationspflicht); DGUV-Vorschriften (z. B. DGUV V3); Qualitätsmanagement ISO 9001 (Rückverfolgbarkeit). Rechtsgrundlage Art. 6 Abs. 1 lit. c DSGVO.
- Beschäftigtendatenschutz im Umbruch: §26 BDSG; EuGH C-34/21 (Hessen, 30.03.2023) zur Unanwendbarkeit; geplantes Beschäftigtendatengesetz.

> Rechtlicher Hinweis: Dieses Dokument ist eine technische Analyse, keine Rechtsberatung. Verbindliche Bewertungen (insb. Löschfristen, AI-Act-Einstufung, Auftragsverarbeitung) gehören mit einem Datenschutzbeauftragten/Fachjuristen abgestimmt.
