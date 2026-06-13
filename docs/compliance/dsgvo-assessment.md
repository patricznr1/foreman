# DSGVO-Datenschutz-Assessment: FOREMAN

> Datenschutz-Selbsteinschätzung · Stand Juni 2026 · außentauglich (öffentliches Repo, Mentor-/Kunden-Vorlage)
> Gegenstand: Datenschutzkonformität von FOREMAN nach Verordnung (EU) 2016/679 (DSGVO), Schwerpunkt **werkerbezogene Daten** im **Default-Betrieb (alles lokal, keine Datenweitergabe)**.
> **Abgrenzung:** Hier geht es um das rechtliche **Ob, Warum und Wieweit**. Das technische **Wie** der Anonymisierung/Pseudonymisierung (HMAC-Tokenisierung, NER, Salt/Key-Rotation, Mapping-Trennung) ist Gegenstand von [`../research/anonymisierung-werkerdaten.md`](../research/anonymisierung-werkerdaten.md) — dieses Dokument verweist darauf, statt zu doppeln.
> **Rechtlicher Vorbehalt:** Fundierte Selbsteinschätzung zur internen Orientierung und zur Außendarstellung des methodischen Vorgehens — **keine Rechtsberatung** (siehe Abschluss).
> **Hinweis zur Architektur (IP):** Das Langzeitgedächtnis ist ein **externer Dienst hinter einer HTTP-API**, der wie eine Datenbank konsumiert wird. Über dessen Interna werden keine Aussagen getroffen; für die datenschutzrechtliche Bewertung von FOREMAN sind sie nicht erforderlich.

---

## 1. Systembeschreibung der Datenverarbeitung

FOREMAN verarbeitet überwiegend **maschinenbezogene** Daten (Sensorwerte, SPS-Signale, Wartungs-/Alarm-Ereignisse). Datenschutzrelevant ist allein der **werkerbezogene** Teilbestand:

- **`worker_notes.author`** — Urheber eines Schichtberichts.
- **`alarms.acknowledged_by`** — Person, die einen (sicherheitskritischen) Alarm quittiert hat.
- **`maintenance_events.performed_by`** — Person, die eine Wartung/Reparatur ausgeführt hat.
- **`worker_notes.text`** — Freitext, der **Personennamen enthalten kann** (auch Dritter, z. B. „mit Schmidt getauscht").

Speicherorte: eine relationale Zeitreihen-Datenbank (PostgreSQL/TimescaleDB) sowie — als semantische Ereignisse — ein **externer Gedächtnis-Dienst** (HTTP-API). Verarbeitungslogik: Die werkerbezogenen Felder werden **im Adapter-Layer am frühestmöglichen Punkt pseudonymisiert** (Klartext-Identität nur in `users`); Freitext wird **vor** der Speicherung per NER auf Personennamen maskiert. Das LLM (lokal Qwen3) sieht maskierten/pseudonymisierten Inhalt. FOREMAN trifft **keine** Personal- oder Leistungsbewertung; werkerbezogene Felder dienen der **Nachvollziehbarkeit** (Quittierung, Wartungsnachweis) und der betrieblichen Wissensorganisation, nicht der Überwachung.

---

## 2. Personenbezogene Daten im Detail (Art. 4 DSGVO)

Personenbezogen ist jede Information über eine **identifizierte oder identifizierbare** natürliche Person (Art. 4 Nr. 1). **Pseudonymisierung** (Art. 4 Nr. 5) ändert daran nichts: Solange die Zuordnung mit Zusatzwissen (hier: `users`-Mapping) möglich ist, bleiben die Daten **personenbezogen** und voll DSGVO-pflichtig.

**Ab wann nicht mehr personenbezogen?** Maßstab ist Erwägungsgrund 26: Es kommt auf **alle Mittel an, die nach allgemeinem Ermessen wahrscheinlich genutzt werden** (Aufwand, Kosten, Technik, Zeit). Echte **Anonymität** liegt erst vor, wenn die Re-Identifikation irreversibel ausgeschlossen ist. Für FOREMAN folgt daraus:

- **Innerhalb der Plattform** (FOREMAN hält Nutzdaten *und* Mapping) bleiben die pseudonymisierten Felder **personenbezogen** — die sichere Arbeitsannahme.
- Die jüngere EuGH-Rechtsprechung zum **relativen** Personenbezug (EuGH, EDPS/SRB, C-413/23 P, 04.09.2025) greift erst für **Empfänger ohne Re-Identifikationsmittel** (z. B. ein aggregierter Export) — innerhalb FOREMAN nicht. Details zur technischen Schwelle: Research-Doku.
- **Maschinen-/Sensordaten** sind **nicht** personenbezogen. Vorsicht nur bei indirekter Re-Identifikation über Schichtmuster/Zeitstempel + seltene Besetzung (behandelt im Research-Doc); im Reasoning-Pfad durch Trennung von Identität und Verhalten entschärft.

### 2.1 Feld-Übersicht

| Datenfeld | Personenbezogen? | Rechtsgrundlage (Art. 6) | Schutzmaßnahme (Verweis: Research-Doc) | Löschkonzept |
|---|---|---|---|---|
| `worker_notes.author` | ja (pseudonym) | Art. 6(1)(f) berechtigtes Interesse (betriebl. Wissensorganisation); ergänzend Betriebsvereinbarung (Art. 88) | HMAC-Token über `users.id`; Klartext nur in `users` | Crypto-Shredding des Personenschlüssels; kürzere Frist (kein Nachweiszweck) |
| `alarms.acknowledged_by` | ja (pseudonym) | Art. 6(1)(c) rechtliche Verpflichtung (Arbeitssicherheit/HITL-Nachweis) + (f) | HMAC-Token; auditiert re-identifizierbar | an gesetzliche Aufbewahrungs-/Nachweisfrist gekoppelt (länger) |
| `maintenance_events.performed_by` | ja (pseudonym) | Art. 6(1)(c) (Prüf-/Wartungsnachweis, BetrSichV) + (b)/(f) | HMAC-Token; auditiert re-identifizierbar | an gesetzliche Aufbewahrungsfrist gekoppelt |
| `worker_notes.text` (Freitext) | ja, solange Namen enthalten | Art. 6(1)(f) | **NER-Maskierung vor Speicherung**; Restrisiko, nie als anonym deklariert | definierte Freitext-Löschfrist + Zugriffsbeschränkung |
| Sensordaten / `readings` / Maschinen-Metadaten | nein (Maschinenbezug) | — (DSGVO nicht anwendbar) | Trennung Identität/Verhalten; Aggregation/Suppression bei Exporten | regul. nach Betriebsbedarf (kein Personenbezug) |
| `semantic_events` (externer Dienst) | ja, soweit pseudonyme Werkerbezüge enthalten | wie Quellfeld | nur Token/maskierter Inhalt verlässt FOREMAN | Personenbezug entfällt mit Crypto-Shredding; ergänzend Lösch-Request an den Dienst |

---

## 3. Rechtsgrundlage (Art. 6 DSGVO) und Beschäftigtenkontext

**Wichtige Vorfrage — § 26 BDSG ist keine tragfähige Grundlage mehr.** Der EuGH (C-34/21, 30.03.2023) und ihm folgend das **BAG (8 AZR 209/21, 08.05.2025)** haben § 26 Abs. 1 S. 1 BDSG als nationale Generalklausel für **unanwendbar** erklärt (Verstoß gegen die Öffnungsklausel Art. 88 DSGVO). Ein angekündigtes **Beschäftigtendatengesetz** liegt nur als Referentenentwurf (Nov. 2024) vor und ist nicht in Kraft. **Konsequenz:** Die Verarbeitung stützt sich **unmittelbar auf Art. 6(1) DSGVO**; eine **Betriebsvereinbarung** bleibt als eigenständige Rechtsgrundlage nach Art. 88 Abs. 1 DSGVO möglich und ist im Beschäftigtenkontext zu empfehlen.

Konkrete Grundlagen je nach Feldzweck:

- **Art. 6(1)(c) — rechtliche Verpflichtung:** für `maintenance_events.performed_by` (Prüf-/Wartungsnachweis nach BetrSichV/Arbeitsschutz) und `alarms.acknowledged_by` (Nachweis der menschlichen Quittierung sicherheitskritischer Ereignisse). Hier ist Attributierbarkeit **gesetzlich gewollt** — Anonymisierung wäre rechtlich falsch.
- **Art. 6(1)(f) — berechtigtes Interesse:** für `worker_notes.author` und den Freitext (betriebliche Wissensorganisation, Anlagenverfügbarkeit, „hatten wir das schon mal"). Interessenabwägung: Das berechtigte Interesse des Betreibers an Produktions-Wissen überwiegt, **weil** der Eingriff durch Pseudonymisierung am frühestmöglichen Punkt und Datensparsamkeit minimiert ist und **keine Leistungs-/Verhaltenskontrolle** stattfindet. Genau diese Minimierung trägt die Abwägung.
- **Art. 6(1)(b) — Vertragserfüllung:** nachrangig denkbar, soweit die Dokumentation Teil arbeitsvertraglicher Pflichten ist.
- **Betriebsvereinbarung (Art. 88):** empfohlene zusätzliche Absicherung im Beschäftigtenkontext; bindet den Betriebsrat ein und schafft Transparenz.

**Besonderheit Beschäftigtendaten:** das **Machtungleichgewicht** Arbeitgeber–Beschäftigte. Einwilligung (Art. 6(1)(a)) ist als Grundlage hier i. d. R. **ungeeignet** (Freiwilligkeit zweifelhaft). Tragend sind daher (c)/(f) plus Betriebsvereinbarung, flankiert von Transparenz und der Minimierung durch Pseudonymisierung.

---

## 4. Zweckbindung & Speicherbegrenzung (Art. 5)

**Zweckbindung (Art. 5(1)(b)):** Die werkerbezogenen Daten werden für klar umrissene Zwecke verarbeitet — Nachvollziehbarkeit sicherheits-/qualitätsrelevanter Handlungen (c-Felder) und betriebliche Wissensorganisation (f-Felder). Eine zweckfremde Weiterverarbeitung (z. B. Leistungsbewertung) findet **nicht** statt und ist auszuschließen.

**Spannungsfeld „Langzeitgedächtnis über Jahre" vs. Speicherbegrenzung (Art. 5(1)(e)):** Auflösung durch **Trennung von Personenbezug und Sachdaten**. Das langlebige Gedächtnis bezieht sich auf **Maschinen und Vorfälle** (nicht personenbezogen) — dieses darf zeitlich unbegrenzt bestehen. Der **Personenbezug** (das Token→Person-Mapping) unterliegt dagegen einer **definierten Löschfrist** je Feldzweck. So bleibt das Produktversprechen erhalten, ohne die Speicherbegrenzung für personenbezogene Daten zu verletzen.

**Datensparsamkeit (Art. 5(1)(c)):** erfüllt durch Pseudonymisierung am frühestmöglichen Punkt, NER-Maskierung des Freitexts, keine PII in Logs, und den **lokalen** Default-Betrieb (Qwen3/Ollama) ohne jede Datenweitergabe — die datensparsamste Variante.

**Rechenschaftspflicht (Art. 5(2)):** dieses Assessment, die Research-Doku und das Verarbeitungsverzeichnis dokumentieren die Maßnahmen.

---

## 5. Betroffenenrechte (Art. 15–21)

Herausforderung: Daten liegen in der Zeitreihen-DB **und** als semantische Events im externen Dienst. Umsetzung:

- **Auskunft (Art. 15):** Über das `users`-Mapping wird die Pseudo-ID (Token) einer Person ermittelt; darüber lassen sich ihre Einträge in DB und (über die Token) im externen Dienst zusammenstellen.
- **Berichtigung (Art. 16):** Korrektur in der Quelle (`users`/Notiz); abgeleitete Events werden nachgezogen.
- **Löschung (Art. 17):** umgesetzt per **Crypto-Shredding** — Vernichtung des personenbezogenen Schlüssels. Da Nutzdatenbank und externer Dienst nur **Token/maskierten Inhalt** halten, wird mit dem Schlüssel der Personenbezug **überall zugleich irreversibel** gekappt; ergänzend kann ein Lösch-Request an den externen Dienst gestellt werden. Maschinen-/Verhaltensdaten bleiben erhalten (kein Personenbezug). **→ Löschanspruch und Langzeitgedächtnis kollidieren nicht.** (Technik: Research-Doc.)
- **Widerspruch (Art. 21):** gegen auf Art. 6(1)(f) gestützte Verarbeitung möglich; greift nicht gegen die auf (c) gestützten gesetzlichen Nachweispflichten.
- **Einschränkung (Art. 18) / Datenübertragbarkeit (Art. 20):** Art. 20 nur eingeschränkt einschlägig (keine auf Einwilligung/Vertrag gestützte, bereitgestellte Daten im engeren Sinne); im Einzelfall zu prüfen.

---

## 6. Privacy by Design / by Default (Art. 25)

Auf konzeptioneller Ebene erfüllt:

- **Anonymisierung/Pseudonymisierung am frühestmöglichen Punkt** (Adapter-Layer), nicht nachgelagert.
- **Trennung von Identität und Nutzdaten:** Klartext nur in `users`; überall sonst nur Token (System-of-Record-Trennung, vgl. Research-Doc).
- **NER-Maskierung des Freitexts vor Speicherung.**
- **Keine PII in Logs**, Datensparsamkeit als Default, **lokale Verarbeitung** als datenschutzfreundlichste Voreinstellung.
- **Abschaltbarer Personenbezug** (Crypto-Shredding) als eingebaute Löschfähigkeit.

Diese Maßnahmen sind die Antwort auf Art. 25 — Datenschutz ist in die Architektur eingebaut, nicht aufgesetzt.

---

## 7. Auftragsverarbeitung & Drittland — nur Cloud-Fall (Wegweiser)

**Default (lokal, Qwen3/Ollama):** Es verlässt **kein** personenbezogenes Datum die Anlage. Es entsteht **keine** Auftragsverarbeitung nach außen, **kein** Drittlandtransfer. Dies ist der datenschutzrechtlich klar vorzugswürdige Normalbetrieb.

**Falls der Cloud-LLM-Fallback aktiviert wird, gilt zusätzlich:**

- **Auftragsverarbeitung (Art. 28):** Der Cloud-Anbieter wird Auftragsverarbeiter → **Auftragsverarbeitungsvertrag (AVV) erforderlich**, mit Weisungsbindung, TOM und Unterauftragsregelung.
- **Drittlandtransfer (Art. 44 ff.):** Bei einem US-Anbieter ist eine Transfergrundlage nötig — derzeit der **Angemessenheitsbeschluss EU-US Data Privacy Framework** (sofern der Anbieter zertifiziert ist), dessen Bestand politisch zu beobachten ist; andernfalls **Standardvertragsklauseln (SCC)** + Transfer-Impact-Assessment.
- **Datenminimierung vor Versand:** Werker-Freitext ist **vor** dem Cloud-Versand NER-maskiert/pseudonymisiert; idealerweise verlassen nur strukturierte, pseudonyme Reasoner-Daten die Anlage.

Dieser Abschnitt ist ein Wegweiser, keine Vollanalyse — bei tatsächlicher Cloud-Nutzung gesondert auszuarbeiten.

---

## 8. DSFA-Prüfung (Art. 35)

Eine Datenschutz-Folgenabschätzung ist erforderlich bei **voraussichtlich hohem Risiko**. Indikator sind die WP248-Kriterien der (vormaligen) Art.-29-Gruppe / die „Muss-Listen" der Aufsichtsbehörden; ab **zwei** erfüllten Kriterien ist eine DSFA regelmäßig angezeigt. Prüfung für FOREMAN:

| Kriterium (WP248) | FOREMAN |
|---|---|
| Bewertung/Scoring von Personen | nein (keine Leistungsbewertung) |
| Automatisierte Entscheidung mit Rechtswirkung | nein (HITL, keine Personalentscheidung) |
| **Systematische Überwachung** | **grenzwertig** — Quittierungen/Wartungen werden protokolliert, aber zur **Nachweis**-, nicht zur **Verhaltens-/Leistungskontrolle**; klassische Beschäftigtenüberwachung liegt **nicht** vor |
| Besondere Datenkategorien (Art. 9) | nein |
| Große Datenmengen | nein (kleiner Personenkreis je Standort) |
| **Schutzbedürftige Betroffene (Beschäftigte, Machtgefälle)** | **ja** |
| **Innovative Technologie** (KI/LLM + neuartige Gedächtnisarchitektur) | **ja** |
| Verknüpfung von Datensätzen | gering (Token-Mapping, minimiert) |
| Ausschluss von Rechteausübung | nein |

Zwei Kriterien sind plausibel erfüllt (**schutzbedürftige Betroffene** + **innovative Technologie**). Der klassische Hochrisiko-Auslöser **systematische Leistungsüberwachung liegt gerade nicht vor**, und die Pseudonymisierung senkt das Restrisiko erheblich.

**Einschätzung: Ja — eine DSFA ist durchzuführen** (vorsorglich geboten). Tragend sind der innovative Technologieeinsatz und der Beschäftigtenkontext, nicht eine Überwachungsabsicht. Die DSFA wird voraussichtlich ein **geringes Restrisiko** bescheinigen (dank Pseudonymisierung, fehlender Leistungskontrolle, lokalem Betrieb), ist aber als **Nachweis der Rechenschaftspflicht** (Art. 5(2)) und wegen des Neuheitscharakters zu erstellen — schlank, mit dokumentiertem Ergebnis.

---

## 9. Fazit & Maßnahmenliste

**Gesamteinschätzung:** FOREMAN ist im Default-Betrieb (lokal) **datenschutzrechtlich beherrschbar**. Der personenbezogene Anteil ist klein, klar abgrenzbar und durch Pseudonymisierung am frühestmöglichen Punkt minimiert. § 26 BDSG ist als Grundlage entfallen; die Verarbeitung stützt sich tragfähig auf **Art. 6(1)(c)** (Nachweis-Felder) bzw. **Art. 6(1)(f)** (Wissensorganisation), abgesichert durch eine **Betriebsvereinbarung**.

**Maßnahmenliste (umsetzbar, pro Feld in §2.1 verankert):**

1. **Rechtsgrundlagen festschreiben:** `maintenance_events.performed_by` + `alarms.acknowledged_by` → Art. 6(1)(c); `worker_notes.author` + `.text` → Art. 6(1)(f) mit dokumentierter Interessenabwägung. § 26 BDSG **nicht** mehr als Grundlage führen.
2. **Betriebsvereinbarung** zum FOREMAN-Einsatz anstreben (Art. 88), Betriebsrat einbinden.
3. **Löschkonzept implementieren:** Crypto-Shredding des Personenschlüssels als technischer Löschpfad (Art. 17); Löschfristen je Feld — Nachweis-Felder an gesetzliche Aufbewahrung gekoppelt, `worker_notes` kürzer, Freitext mit eigener Frist. (Technik: Research-Doc.)
4. **Betroffenenrechte-Prozess:** Auskunft/Berichtigung/Löschung über das `users`-Mapping bedienbar machen; Lösch-Request-Schnittstelle zum externen Dienst vorsehen.
5. **Privacy by Design dokumentieren:** Pseudonymisierung am Adapter-Layer, NER vor Speicherung, keine PII in Logs, lokaler Default — im Verarbeitungsverzeichnis festhalten.
6. **DSFA: ja, durchführen** — schlanke Folgenabschätzung mit erwartet geringem Restrisiko; Ergebnis dokumentieren (Rechenschaftspflicht).
7. **Verarbeitungsverzeichnis (Art. 30)** für den werkerbezogenen Teil anlegen.
8. **Cloud-Fall nur mit Zusatzpaket:** AVV (Art. 28) + Transfergrundlage (Art. 44 ff.) + Maskierung vor Versand; sonst beim lokalen Default bleiben.
9. **Vor Produktiveinsatz:** betrieblichen/externen Datenschutzbeauftragten und ggf. Betriebsrat einbinden.

**Offene Punkte:**

- **Beschäftigtendatengesetz:** Entwicklung beobachten; bei Inkrafttreten Rechtsgrundlagen-Teil aktualisieren.
- **Konkrete Löschfristen:** pro Feld in Tagen/Jahren festlegen — abhängig von den am Standort geltenden Aufbewahrungspflichten (mit DSB/Betreiber).
- **Re-Identifikations-Restrisiko über Schichtmuster:** für Exporte gesondert bewerten (Research-Doc).
- **DSFA-Detailtiefe:** Umfang mit dem DSB abstimmen.

---

## Quellen

- **DSGVO (VO (EU) 2016/679):** Art. 4 Nr. 1/5 (personenbezogene Daten/Pseudonymisierung), Art. 5 (Grundsätze), Art. 6 (Rechtmäßigkeit), Art. 9 (besondere Kategorien), Art. 15–21 (Betroffenenrechte), Art. 25 (Privacy by Design), Art. 28 (Auftragsverarbeitung), Art. 30 (Verzeichnis), Art. 35 (DSFA), Art. 44 ff. (Drittland), Art. 88 (Beschäftigtenkontext), Erwägungsgrund 26. https://eur-lex.europa.eu/eli/reg/2016/679/oj
- **§ 26 BDSG** und seine Unanwendbarkeit: EuGH, C-34/21 (30.03.2023); BAG, 8 AZR 209/21 (08.05.2025); Referentenentwurf Beschäftigtendatengesetz (Nov. 2024).
- **EuGH, EDPS/SRB, C-413/23 P** (04.09.2025) — relativer/kontextueller Personenbezug pseudonymisierter Daten.
- **Art.-29-Datenschutzgruppe, WP248** (DSFA-Kriterien) sowie DSK-„Muss-Listen" der Aufsichtsbehörden zu Art. 35 Abs. 4 DSGVO.
- EDSA-Leitlinien zur Pseudonymisierung (01/2025) und zum Recht auf Vergessenwerden (5/2019, analog zu Crypto-Shredding) — vgl. Research-Doc.
- Drittland: Angemessenheitsbeschluss **EU-US Data Privacy Framework** (2023) bzw. Standardvertragsklauseln.
- Querverweis (technisches Wie): [`../research/anonymisierung-werkerdaten.md`](../research/anonymisierung-werkerdaten.md).

> **Rechtlicher Vorbehalt (Wiederholung):** Diese Selbsteinschätzung dient der internen Orientierung und der Außendarstellung des methodischen Vorgehens. Sie ist keine Rechtsberatung. Vor einem echten Produktiveinsatz mit Beschäftigtendaten sind der betriebliche bzw. externe **Datenschutzbeauftragte** und — wegen des Beschäftigtenkontexts — ggf. der **Betriebsrat** einzubinden; die verbindliche Bewertung erfolgt durch fachkundige Stellen unter Berücksichtigung des konkreten Betreiber-Kontexts.
