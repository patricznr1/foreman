# Datenschutz-Folgenabschätzung (DSFA) — FOREMAN · vorläufig, konzeptbasiert

> Vorläufige DSFA nach Art. 35 DSGVO · Stand Juni 2026 · außentauglich (öffentliches Repo, Mentor-/Kunden-Vorlage)
> **Status:** *konzeptbasiert und vorläufig.* FOREMAN ist im Capstone-/MVP-Stadium; es findet **kein** Produktivbetrieb mit echten Beschäftigtendaten statt. Diese DSFA bewertet das **geplante Verarbeitungskonzept** und ist vor Produktiveinsatz mit realen Daten, konkreten Löschfristen und Betreiber-Kontext zu **finalisieren**.
> **Grundlage:** baut auf [`dsgvo-assessment.md`](./dsgvo-assessment.md) (rechtliche Einordnung) und [`../research/anonymisierung-werkerdaten.md`](../research/anonymisierung-werkerdaten.md) (technisches Wie) auf. Methodik: Art. 35(7) DSGVO, orientiert an der CNIL-PIA-Methode und dem Standard-Datenschutzmodell (SDM) der DSK; Risikoeinstufung nach Schwere × Eintrittswahrscheinlichkeit.
> **Architektur (IP):** Das Langzeitgedächtnis ist ein **externer Dienst hinter einer HTTP-API**; über dessen Interna werden keine Aussagen getroffen.
> **Rechtlicher Vorbehalt:** fundierte Selbsteinschätzung, **keine Rechtsberatung** — vgl. Abschluss.

---

## 1. Anlass und Schwellwertanalyse (warum diese DSFA?)

Eine DSFA ist nach Art. 35(1) bei **voraussichtlich hohem Risiko** für die Rechte und Freiheiten natürlicher Personen durchzuführen. Die Schwellwertanalyse anhand der WP248-Kriterien (vgl. `dsgvo-assessment.md` §8) ergibt **zwei** plausibel erfüllte Kriterien:

- **Innovative Technologie** — Einsatz von KI/LLM und einer neuartigen Gedächtnisarchitektur;
- **Schutzbedürftige Betroffene** — Beschäftigte stehen im Machtungleichgewicht zum Arbeitgeber.

Der klassische Hochrisiko-Auslöser **systematische Leistungs-/Verhaltensüberwachung liegt nicht vor** (FOREMAN überwacht Maschinen, nicht Arbeitsleistung). Da die Zwei-Kriterien-Schwelle dennoch erreicht ist und der Beschäftigtenkontext sensibel ist, wird eine DSFA **vorsorglich** durchgeführt — auch als Nachweis der Rechenschaftspflicht (Art. 5(2)).

---

## 2. Systematische Beschreibung der Verarbeitung (Art. 35(7)(a))

**Verantwortlicher (im Produktivfall):** der Anlagenbetreiber, der FOREMAN einsetzt. Im Capstone-Stadium: Projektträger zu Entwicklungszwecken, ohne echte Beschäftigtendaten.

**Zweck:** Nachvollziehbarkeit sicherheits-/qualitätsrelevanter Handlungen (Quittierung, Wartung) und betriebliche Wissensorganisation („hatten wir das schon mal"). **Kein** Zweck der Personalbewertung.

**Betroffene Personengruppen:** Werker/Beschäftigte (Autoren, Quittierende, Ausführende); mittelbar in Schichtbericht-Freitext genannte Dritte.

**Datenarten (personenbezogener Teilbestand):**

| Datenfeld | Inhalt | Rechtsgrundlage |
|---|---|---|
| `worker_notes.author` | Urheber Schichtbericht (pseudonym) | Art. 6(1)(f) |
| `alarms.acknowledged_by` | Quittierer sicherheitskritischer Alarme (pseudonym) | Art. 6(1)(c) + (f) |
| `maintenance_events.performed_by` | Ausführender Wartung (pseudonym) | Art. 6(1)(c) |
| `worker_notes.text` | Freitext, kann Personennamen enthalten | Art. 6(1)(f) |

Keine besonderen Kategorien (Art. 9). Maschinen-/Sensordaten sind nicht personenbezogen.

**Datenfluss:** Eingabe (Werker/Quittierung/Wartung) → **Adapter-Layer: Pseudonymisierung am frühestmöglichen Punkt** (Klartext-Identität nur in `users`), **NER-Maskierung** des Freitexts → Ablage in PostgreSQL/TimescaleDB und — als semantische Events — im **externen Gedächtnis-Dienst** (nur Token/maskierter Inhalt) → Auswertung durch Reasoner → KI-Erklärung (lokal Qwen3) → Werker-Dashboard / MCP-Schnittstelle.

**Empfänger:** intern (Operatoren, berechtigte Auswertung). Standardbetrieb **lokal**, keine externe Datenweitergabe. (Optionaler Cloud-Fallback: §6 dieser DSFA.)

**Speicherdauer:** Personenbezug mit definierter Löschfrist je Feld (Nachweis-Felder an gesetzliche Aufbewahrung gekoppelt, Notizen kürzer); Sach-/Maschinendaten langlebig (kein Personenbezug). Konkrete Fristen: offen, mit DSB/Betreiber festzulegen.

**Eingesetzte Technik (rechtlich relevant, Details im Research-Doc):** deterministische Token-Pseudonymisierung, NER-Maskierung, getrennte Identitäts-Haltung, Crypto-Shredding als Löschpfad, Human-in-the-Loop ohne Aktorik.

---

## 3. Notwendigkeit und Verhältnismäßigkeit (Art. 35(7)(b))

- **Erforderlichkeit:** Die Nachweis-Felder (`performed_by`, `acknowledged_by`) sind zur Erfüllung gesetzlicher Pflichten (Arbeitssicherheit/Prüfnachweis) **erforderlich** — eine Anonymisierung wäre hier rechtswidrig. Die f-Felder dienen der Wissensorganisation; der Personenbezug ist dafür **minimal** nötig (Konsistenz „derselbe Werker", nicht der Name).
- **Datenminimierung:** erreicht durch Pseudonymisierung am Adapter-Layer, NER-Maskierung des Freitexts, keine PII in Logs, lokalen Default. Der Reasoning-Pfad sieht **keine Klarnamen**.
- **Zweckbindung:** klar umrissen, keine Leistungsbewertung; Function Creep ist organisatorisch (Betriebsvereinbarung) und technisch (kein Scoring-Feld) ausgeschlossen.
- **Verhältnismäßigkeit:** Der Eingriff in die Rechte der Beschäftigten ist gering (pseudonym, minimal, kein Monitoring) und steht in angemessenem Verhältnis zum legitimen Zweck (Anlagensicherheit, Verfügbarkeit, gesetzliche Nachweise). Mildere gleich wirksame Mittel sind nicht ersichtlich (die Nachweis-Attributierbarkeit ist gesetzlich gefordert).

Ergebnis: Die Verarbeitung ist **erforderlich und verhältnismäßig**.

---

## 4. Risikoanalyse (Art. 35(7)(c))

Bewertung des **Risikos vor Maßnahmen** (Schwere × Eintrittswahrscheinlichkeit; Skala gering/mittel/hoch). Betrachtete Schäden für Betroffene: unbefugte Aufdeckung der Identität, zweckwidrige Bewertung, Reputations-/arbeitsrechtliche Nachteile, Kontrollverlust über Daten.

| ID | Risiko für Betroffene | Schwere | Wahrscheinlichkeit | Risiko (vor Maßnahmen) |
|---|---|---|---|---|
| R1 | **Re-Identifikation** pseudonymisierter Werker über Schichtmuster/Zeitstempel/Maschinenzuordnung | mittel | mittel | **mittel** |
| R2 | **Unbefugter Zugriff auf das Identitäts-Mapping** (Token→Person) → Aufdeckung aller Pseudonyme | hoch | mittel | **hoch** |
| R3 | **Zweckentfremdung** als Leistungs-/Verhaltenskontrolle (Function Creep) | hoch | mittel | **hoch** |
| R4 | **Personennamen im Freitext** ungeschützt gespeichert (NER-Recall < 100 %) | mittel | mittel | **mittel** |
| R5 | **Falsche personenbezogene Aussage** durch Prompt-Injection/Halluzination im LLM-Output | mittel | mittel | **mittel** |
| R6 | **Unvollständige Löschung** über DB + externen Dienst hinweg | mittel | mittel | **mittel** |
| R7 | **Kontrollverlust/Drittlandtransfer** bei Cloud-Fallback | hoch | (nur falls Cloud aktiviert) | **bedingt hoch** |
| R8 | **PII in Logs** / unbeabsichtigte Offenlegung | mittel | niedrig | **gering–mittel** |
| R9 | **Verletzung von Transparenz/Betroffenenrechten** (keine Kenntnis, erschwerte Auskunft) | mittel | niedrig–mittel | **gering–mittel** |

---

## 5. Abhilfemaßnahmen und Restrisiko (Art. 35(7)(d))

| ID | Abhilfemaßnahme(n) | Restrisiko (nach Maßnahmen) |
|---|---|---|
| R1 | Trennung Identität ↔ Verhalten; Reasoning nur auf Token; Aggregation/Suppression unter k bei Auswertungen/Exporten; relativer Personenbezug erst beim Export (Research-Doc §2.2) | **gering** |
| R2 | Mapping in getrenntem, stärker geschütztem Speicher; RBAC, Verschlüsselung, Audit-Log auf jeden Lesezugriff; kein Default-Join; Least-Privilege | **gering** |
| R3 | Strikte Zweckbindung; **kein** Scoring-/Bewertungsfeld by design; Betriebsvereinbarung (Art. 88) + Betriebsrat; Transparenz; HITL ohne Aktorik | **gering** |
| R4 | NER-Maskierung **vor** Speicherung (recall-orientiert), zweiter Pass für kritische Berichte; Löschfrist + Zugriffsschutz auf Rohtext; org. Regel „keine vollen Namen"; Freitext **nie** als anonym deklariert | **gering–mittel** (offen benannt) |
| R5 | Prompt-Injection-Schutz-Stack (Least-Privilege, Spotlighting, Schema, Grounding, Safety-Agent-Quorum); KI-Kennzeichnung; HITL — vgl. `../research/prompt-injection-schutz.md` | **gering** |
| R6 | **Crypto-Shredding** des Personenschlüssels kappt den Bezug in DB **und** externem Dienst zugleich; ergänzend Lösch-Request an den Dienst; dokumentierter Lösch-Workflow | **gering** |
| R7 | **Lokaler Default ⇒ Risiko entfällt.** Falls Cloud: AVV (Art. 28) + Transfergrundlage (Art. 44 ff.) + Maskierung vor Versand (§6) | lokal **entfällt** / bei Cloud **gering–mittel** (gesondert) |
| R8 | „Keine PII in Logs"-Policy; strukturierte Logs ohne Klartext; Review | **gering** |
| R9 | Informationspflichten (Art. 13/14) + Betriebsvereinbarung; Auskunfts-/Löschprozess über `users`-Mapping; KI-Kennzeichnung (Art. 50 AI Act) | **gering** |

---

## 6. Cloud-Fallback (fokussierter Wegweiser)

Der **Default-Betrieb ist lokal** (Qwen3/Ollama) — kein personenbezogenes Datum verlässt die Anlage, R7 entfällt. **Falls** der Cloud-LLM-Fallback aktiviert wird, ist ergänzend erforderlich: Auftragsverarbeitungsvertrag (Art. 28), Transfergrundlage für Drittland (Art. 44 ff.; EU-US Data Privacy Framework sofern zertifiziert, sonst SCC + Transfer-Impact-Assessment), und Pseudonymisierung/NER-Maskierung **vor** dem Versand. Dieser Fall ist vor Aktivierung in einer eigenen DSFA-Ergänzung zu bewerten.

---

## 7. Ergebnis und Konsultationsbedarf (Art. 36)

Nach Umsetzung der Maßnahmen aus §5 ist das **Restrisiko durchgängig gering** (für R4 verbleibt ein offen benanntes, aber begrenztes Restrisiko im Freitext-Pfad). Damit verbleibt **kein hohes Restrisiko**, das trotz Maßnahmen bestehen bleibt.

**→ Eine vorherige Konsultation der Aufsichtsbehörde nach Art. 36 DSGVO ist nicht erforderlich**, solange das Konzept (insb. Human-in-the-Loop ohne Aktorik, lokaler Default, Pseudonymisierung am frühestmöglichen Punkt) eingehalten wird. Diese Einschätzung ist im Produktivfall mit echten Daten zu bestätigen.

---

## 8. Beteiligte und Verfahren (Art. 35(2), (9))

- **Datenschutzbeauftragter:** im Produktivfall einzubinden (Beratung nach Art. 35(2)); in dieser vorläufigen Fassung noch nicht erfolgt.
- **Betriebsrat / Beschäftigtenvertretung:** wegen des Beschäftigtenkontexts vor Produktiveinsatz einzubinden (Mitbestimmung; Betriebsvereinbarung als Rechtsgrundlage Art. 88).
- **Standpunkt der Betroffenen (Art. 35(9)):** im Produktivfall einzuholen, soweit angemessen.
- **Review-Trigger:** Neubewertung bei Architektur-Änderung (Aktorik, neue Datenarten, echter Personenbezug), Cloud-Aktivierung, Einsatz in kritischer Infrastruktur, Inkrafttreten des Beschäftigtendatengesetzes oder neuem Betreiber-Kontext.

---

## 9. Fazit und To-dos

**Ergebnis:** Das Verarbeitungskonzept von FOREMAN ist datenschutzrechtlich **tragfähig**; das Restrisiko ist nach Umsetzung der Maßnahmen **gering**, eine Aufsichtsbehörden-Konsultation (Art. 36) ist **nicht** erforderlich. Tragende Bedingungen sind Human-in-the-Loop ohne Aktorik, Pseudonymisierung am Adapter-Layer und lokaler Default.

**To-dos zur Finalisierung (vor Produktiveinsatz):**

1. **Konkrete Löschfristen** je Feld festlegen (mit DSB/Betreiber) und im Löschkonzept verankern.
2. **DSB** zur Beratung einbinden (Art. 35(2)); DSFA-Ergebnis gegenzeichnen.
3. **Betriebsrat** einbinden, **Betriebsvereinbarung** (Art. 88) abschließen.
4. **R4 (Freitext) messen:** NER-Recall an realen Berichten quantifizieren; Zweitpass-Politik festlegen; Restrisiko dokumentieren.
5. **Lösch-Workflow** technisch verproben (Crypto-Shredding + Lösch-Request an den externen Dienst end-to-end).
6. **Verarbeitungsverzeichnis (Art. 30)** und Informationspflichten (Art. 13/14) erstellen.
7. **Cloud-Ergänzung** nur bei Aktivierung; bis dahin beim lokalen Default bleiben.
8. **Versionierung:** diese DSFA bei jedem Review-Trigger (§8) aktualisieren.

---

## Quellen

- DSGVO (VO (EU) 2016/679): Art. 5(2), 6, 13/14, 24, 25, 28, 30, 32, 35, 36, 44 ff., 88; Erwägungsgründe 75, 76, 84, 90–92.
- Art.-29-Datenschutzgruppe, **WP248 rev.01** — Leitlinien zur DSFA und Kriterien für „hohes Risiko".
- **DSK** — Kurzpapier Nr. 5 (DSFA) und „Muss-Listen" nach Art. 35(4) DSGVO; **Standard-Datenschutzmodell (SDM)** als Methodik.
- **CNIL** — PIA-Methodik (Privacy Impact Assessment) als anerkanntes Vorgehen.
- § 26 BDSG (entfallen: EuGH C-34/21; BAG 8 AZR 209/21, 08.05.2025) — vgl. `dsgvo-assessment.md`.
- Querverweise: [`dsgvo-assessment.md`](./dsgvo-assessment.md), [`../research/anonymisierung-werkerdaten.md`](../research/anonymisierung-werkerdaten.md), [`../research/prompt-injection-schutz.md`](../research/prompt-injection-schutz.md), [`eu-ai-act-assessment.md`](./eu-ai-act-assessment.md).

> **Rechtlicher Vorbehalt:** Diese vorläufige, konzeptbasierte DSFA dient der internen Orientierung und der Außendarstellung des methodischen Vorgehens. Sie ist keine Rechtsberatung und ersetzt keine vom Datenschutzbeauftragten begleitete, finale DSFA. Vor einem echten Produktiveinsatz mit Beschäftigtendaten sind DSB und ggf. Betriebsrat einzubinden; maßgeblich ist der konkrete Betreiber-Kontext.
