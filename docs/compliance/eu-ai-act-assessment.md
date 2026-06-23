# EU-AI-Act-Compliance-Assessment: FOREMAN

> Compliance-Selbsteinschätzung · Stand Juni 2026 · außentauglich (öffentliches Repo, Mentor-/Kunden-Vorlage)
> Gegenstand: Einordnung der FOREMAN-Plattform unter die Verordnung (EU) 2024/1689 (KI-Verordnung / „AI Act").
> **Rechtlicher Vorbehalt:** Dieses Dokument ist eine fundierte Selbsteinschätzung zur internen Orientierung und zur Darstellung des methodischen Vorgehens nach außen. Es ist **keine Rechtsberatung**. Die verbindliche Einstufung ist vor einem echten Produktiveinsatz juristisch (Fachanwalt / Konformitätsbewertungsstelle) abzusichern (siehe Abschluss).
> **Hinweis zur Architektur (IP):** Das Langzeitgedächtnis ist ein **externer Dienst hinter einer HTTP-API** — eine biologisch inspirierte Gedächtnisarchitektur, die wie eine Datenbank konsumiert wird. Über dessen interne Verfahren werden in diesem Dokument bewusst keine Aussagen getroffen; sie sind für die regulatorische Einordnung von FOREMAN nicht erforderlich.

---

## 1. Systembeschreibung

FOREMAN ist eine Reasoning-Plattform für industrielle Produktionsumgebungen. Vier Reasoner (Ereignisketten-Rekonstruktion, Drift-Erkennung, Ausfallvorhersage, Wartungszyklen-Analyse) werten **Maschinen-Sensordaten, SPS-Daten und Werker-Notizen** aus und erzeugen daraus **Empfehlungen, Warnungen und Erklärungen**. Diese werden (a) in einem **Werker-Dashboard** dargestellt und (b) als aggregierte Erkenntnisse über eine **MCP-Schnittstelle** an Drittsysteme (z. B. Wartungsplanung, ERP) ausgegeben. Beobachtete Lastdaten (historische Lastprofile/Grenzwerte) werden — sofern künftig exponiert — als **reine Messdaten** read-only über dieselbe MCP-Schnittstelle bereitgestellt (**kein KI-Output**); eine eigentliche Belastungs-Simulation führt FOREMAN nicht selbst durch, die fährt extern bei einem Drittsystem.

Architektonisch entscheidend für die regulatorische Einordnung:

- **Keine automatische Aktorik.** FOREMAN steuert keine Maschine, löst keinen Schaltvorgang aus, greift in keinen Steuerungs-Loop ein. Es **empfiehlt**; die Entscheidung trifft der Mensch (**Human-in-the-Loop**).
- **Operator-Quittierung für sicherheitskritische Alarme.** Safety-relevante Meldungen gelten erst nach expliziter Quittierung durch den Operator als erledigt (`alarms.acknowledged_at`/`acknowledged_by`).
- **Erklärender LLM-Layer.** Ein vortrainiertes Sprachmodell (lokal Qwen3 über Ollama; optionaler Cloud-Fallback) formuliert aus strukturierten Reasoner-Ergebnissen Klartext-Erklärungen. Es hat keine Aktorik und keinen privilegierten Datenzugriff.
- **Werkerbezug minimiert.** Personenbezogene Felder werden pseudonymisiert; FOREMAN trifft **keine** Personal-/Bewertungsentscheidungen über Beschäftigte (Details: `docs/research/anonymisierung-werkerdaten.md`).

Diese vier Eigenschaften sind keine kosmetischen Details, sondern die tragenden Argumente der nachstehenden Klassifizierung.

---

## 2. Klassifizierungs-Logik (Entscheidungsbaum)

Der AI Act kennt vier Stufen: **Prohibited** (Art. 5), **High Risk** (Art. 6 i. V. m. Anhang I/III), **Limited Risk / Transparenz** (Art. 50) und **Minimal Risk** (Rest). Die Prüfung läuft von oben:

| # | Kriterium (AI Act) | Trifft auf FOREMAN zu? | Konsequenz |
|---|---|---|---|
| 1 | **Verbotene Praktik** nach Art. 5 (Social Scoring, manipulatives Beeinflussen, biometrische Echtzeit-Fernidentifizierung, Emotionserkennung am Arbeitsplatz zu Bewertungszwecken etc.) | **Nein** — nichts davon. Maschinen-Monitoring, keine Personenbewertung. | nicht verboten → weiter |
| 2 | **High-Risk via Art. 6(1) / Anhang I:** KI ist **Sicherheitsbauteil** eines Produkts (z. B. Maschine nach VO 2023/1230), das eine **Drittkonformitätsbewertung** durchlaufen muss | **Nein** (im definierten Einsatz) — FOREMAN ist beratend, übernimmt **keine Sicherheitsfunktion** einer Maschine; sein Ausfall löst keinen gefährlichen Maschinenzustand aus. | kein Anhang-I-Hochrisiko → weiter (Grenzfall s. §3) |
| 3 | **High-Risk via Art. 6(2) / Anhang III:** KI ist **Sicherheitsbauteil** kritischer Infrastruktur (Strom/Wasser/Gas/Verkehr/digitale Infrastruktur) **oder** fällt in einen anderen Anhang-III-Bereich (Beschäftigung, Bildung, essenzielle Dienste, Strafverfolgung …) | **Nein** — industrielle Produktion ist keine kritische Infrastruktur i. S. d. Anhang III(2); kein Beschäftigungs-/HR-Anwendungsfall (kein Personal-Scoring). | kein Anhang-III-Hochrisiko → weiter |
| 4 | (falls Anhang III je einschlägig wäre) **Art. 6(3)-Ausnahme:** nur vorbereitende/unterstützende Tätigkeit, ersetzt menschliche Bewertung nicht, kein Profiling | greift **zusätzlich absichernd** (HITL, kein Profiling) — ist hier aber nachrangig, da bereits Schritt 3 verneint | verstärkt „kein Hochrisiko" |
| 5 | **Transparenz-Tatbestand Art. 50:** System interagiert mit Menschen / erzeugt KI-generierte Inhalte (Texte, Empfehlungen) | **Ja** — der LLM-Layer erzeugt für Menschen bestimmte Erklärungen/Empfehlungen. | **Limited Risk → Transparenzpflichten Art. 50** |
| 6 | Rest | — | Minimal Risk für nicht von Art. 50 erfasste Funktionen |

**Ergebnis des Entscheidungsbaums: FOREMAN ist als KI-System mit begrenztem Risiko (Limited Risk) einzustufen, mit Transparenzpflichten nach Art. 50 und der Querschnittspflicht zur KI-Kompetenz (Art. 4).** Voraussetzung dieser Einstufung ist, dass FOREMAN beratend bleibt (HITL) und nicht als Sicherheitsfunktion in eine Maschinen-/Infrastruktursteuerung integriert wird (Grenzfälle: §3, §9).

---

## 3. Anhang-III-Prüfung und Wechselwirkung mit der Maschinenverordnung

### 3.1 Anhang III(2) — kritische Infrastruktur

Anhang III Nr. 2 erfasst KI als **Sicherheitsbauteil** „bei der Verwaltung und dem Betrieb kritischer digitaler Infrastruktur, des Straßenverkehrs oder der Versorgung mit Wasser, Gas, Wärme und Strom". Ein **Sicherheitsbauteil** ist eine Komponente, deren Ausfall/Fehlfunktion die Sicherheit von Personen oder Sachen unmittelbar gefährdet.

FOREMAN in der definierten Produktionsumgebung erfüllt das **nicht**: Eine Fertigungsanlage ist keine kritische Infrastruktur im Sinne dieser Vorschrift, und FOREMAN ist kein Sicherheitsbauteil — es übernimmt keine sicherheitsgerichtete Funktion, sondern liefert beratende Hinweise, deren Ausfall die Anlagensicherheit nicht aufhebt (die bestehenden SPS-/Not-Halt-Sicherheitsfunktionen laufen unabhängig weiter). **→ Anhang III(2) nicht einschlägig.**

### 3.2 Andere Anhang-III-Bereiche

Beschäftigung/Personalmanagement (Anhang III Nr. 4) würde KI erfassen, die über Einstellung, Beförderung, Kündigung oder Leistungsbewertung von Beschäftigten (mit)entscheidet. FOREMAN überwacht **Maschinen**, nicht die Arbeitsleistung von Personen; werkerbezogene Felder sind pseudonymisiert und dienen der Nachvollziehbarkeit (Quittierung/Wartung), nicht der Personalbewertung. Die übrigen Anhang-III-Bereiche (Biometrie, Bildung, essenzielle private/öffentliche Dienste, Strafverfolgung, Migration, Justiz/Wahlen) sind erkennbar nicht berührt. **→ kein Anhang-III-Bereich einschlägig.**

### 3.3 Maschinenverordnung (EU) 2023/1230 — Annex-I-Route (Art. 6(1))

Die Maschinenverordnung 2023/1230 (ab 20.01.2027 anwendbar) ist Teil der in **Anhang I** des AI Act gelisteten Harmonisierungsrechtsakte. Sie führt KI ausdrücklich als sicherheitsrelevante Technologie und kennt die Kategorie **„Sicherheitsbauteile mit vollständig oder teilweise selbst-entwickelndem Verhalten unter Einsatz von Machine-Learning"**, die einer **Drittkonformitätsbewertung** (Notified Body) bedürfen. Wäre FOREMAN ein solches, in eine Maschine eingebettetes Sicherheitsbauteil, das eine Sicherheitsfunktion ausführt, **würde** Art. 6(1) AI Act greifen und FOREMAN als Hochrisiko-System einstufen.

Im hier definierten Einsatz ist das **nicht** der Fall: FOREMAN ist ein **eigenständiges, beratendes Analyse-System neben** der Maschine, kein in die Maschine integriertes, sicherheitsgerichtetes Bauteil. Es führt keine Sicherheitsfunktion aus, und sein Versagen versetzt die Maschine nicht in einen gefährlichen Zustand.

**Kritischer Grenzfall (ausdrücklich markiert):** Würde ein Kunde FOREMANs Ausgabe in eine **automatische** Sicherheitsreaktion einbinden (z. B. automatische Abschaltung ohne menschliche Quittierung) oder FOREMAN als ML-Sicherheitsbauteil in eine konformitätspflichtige Maschine integrieren, kippt die Einstufung in **High Risk** (Art. 6(1) + MaschinenVO-Drittbewertung). Die Human-in-the-Loop-Architektur und das Verbot automatischer Aktorik sind damit nicht nur Design-Präferenz, sondern die **tragende Grenze der Limited-Risk-Einstufung** und müssen vertraglich/dokumentarisch abgesichert werden (siehe §9).

---

## 4. Art. 6(3) — Ausnahme-Tatbestände (absichernd)

Selbst wenn man — entgegen §3 — einen Anhang-III-Bezug unterstellte, sieht Art. 6(3) eine Ausnahme von der Hochrisiko-Einstufung vor, wenn das System das Ergebnis menschlicher Tätigkeit lediglich **unterstützt/verbessert**, eine **enge verfahrenstechnische** oder **vorbereitende** Aufgabe erfüllt bzw. Entscheidungsmuster erkennt, **ohne die menschliche Bewertung zu ersetzen**, und **kein Profiling** natürlicher Personen vornimmt.

FOREMAN passt in dieses Muster: Es bereitet Entscheidungen des Operators vor und erkennt Abweichungs-/Verschleißmuster, **ersetzt** die menschliche Bewertung aber nicht (HITL, Quittierungspflicht), und es **profiliert keine natürlichen Personen** (Maschinen-Analyse, pseudonymisierte Werkerfelder).

**Wichtige Einschränkung (Stand der Leitlinien 2025):** Menschliche Aufsicht **allein** begründet die Ausnahme **nicht** — sie ändert nicht Zweck und Einsatzbereich eines Systems. Art. 6(3) trägt nur, wenn die Tätigkeit tatsächlich vorbereitend/eng ist. Für FOREMAN ist der primäre Befund daher **nicht** „Annex III + 6(3)-Ausnahme", sondern „**fällt bereits nicht in Annex III**" (§3); Art. 6(3) ist die nachgelagerte zweite Verteidigungslinie, nicht das Haupt-Argument.

---

## 5. Transparenzpflichten (Art. 50)

Da der LLM-Layer für Menschen bestimmte Erklärungen/Empfehlungen erzeugt, greift Art. 50:

- **Art. 50(1):** Wer mit einem KI-System interagiert, muss dies erkennen können. → Im Dashboard ist erkennbar zu machen, dass Empfehlungen/Erklärungen **KI-generiert** sind.
- **Art. 50(2):** KI-generierte Inhalte sind als künstlich erzeugt **kenntlich** zu machen (für synthetische Medien zusätzlich maschinenlesbar). FOREMAN erzeugt Text, keine synthetischen Medien; die Kennzeichnungspflicht erfüllt FOREMAN durch klare Auszeichnung der KI-Herkunft.

**Konkrete Umsetzung in FOREMAN:**

- **Dashboard:** Jede vom LLM erzeugte Empfehlung/Erklärung trägt eine sichtbare Kennzeichnung („**KI-Empfehlung – vom Operator zu prüfen**") und, wo sinnvoll, einen Konfidenz-/Quellenhinweis (Grounding-Faktoren). Sicherheitskritische Hinweise bleiben quittierungspflichtig.
- **MCP-Schnittstelle (✅ gebaut, F7):** Aggregierte Erkenntnisse werden read-only mit einem maschinenlesbaren Herkunfts-Flag ausgeliefert (`"generated_by": "foreman-ai", "ai_generated": true, "requires_human_review": true, "model_version": …`), damit Drittsysteme die KI-Herkunft erkennen und nicht als verifizierte Wahrheit weiterverarbeiten. Ausfall-Einschätzungen und Empfehlungen führen zusätzlich ihren Validierungs-Vorbehalt mit; Stammdaten/Sensortrends/Alarme werden ehrlich **nicht** als KI gekennzeichnet. Keine Aktorik über die Schnittstelle (read-only) — die tragende Limited-Risk-Bedingung bleibt gewahrt.
- **Logging:** Ausgaben werden mit Modell-/Versionskennung und Zeitstempel protokolliert (Nachvollziehbarkeit, Observability §11).

Zusätzlich gilt die **KI-Kompetenz-Pflicht (Art. 4)**: Personen, die FOREMAN betreiben/bedienen, müssen über ausreichendes Verständnis der Möglichkeiten und Grenzen verfügen (kurze Nutzer-Einweisung / Doku).

---

## 6. GPAI-Bezug: Provider- vs. Deployer-Pflichten

FOREMAN nutzt ein vortrainiertes **General-Purpose-AI-Modell** (Qwen3, lokal über Ollama; optionaler Cloud-Fallback). Abgrenzung:

- **Provider eines GPAI-Modells** (hier: der Modell-Anbieter, z. B. das Qwen-Team) trägt die GPAI-spezifischen Pflichten nach Art. 53/55: technische Dokumentation des Modells, Zusammenfassung der Trainingsdaten, Urheberrechts-Policy, bei systemischem Risiko zusätzliche Bewertungs-/Meldepflichten.
- **Deployer** (hier: FOREMAN) ist, wer das Modell **betreibt/einsetzt**. FOREMAN trifft **nicht** die GPAI-Provider-Pflichten, sondern die Deployer-/System-Pflichten: insbesondere die Transparenzpflichten aus Art. 50 und die KI-Kompetenz aus Art. 4 (oben).

**FOREMAN wird nur dann selbst zum Provider**, wenn es das Modell **wesentlich verändert/feintunt** und unter eigenem Namen in Verkehr bringt. Der reine Betrieb eines unveränderten Qwen3 über Ollama macht FOREMAN **nicht** zum GPAI-Provider. (Open-Source-Lizenzierung des Modells ändert nichts an den Transparenzpflichten des Art. 50, die unberührt bleiben.)

**Wegweiser Betriebsvariante (kurz):**
- **Lokal (Qwen3/Ollama, Default):** Deployer-Rolle, keine Datenweitergabe an Dritte; AI-Act-seitig wie oben.
- **Cloud-Fallback:** FOREMAN bleibt Deployer; der Cloud-Anbieter ist GPAI-Provider/Auftragsverarbeiter. **Falls Cloud genutzt wird, ändert sich:** (a) Daten verlassen die Anlage → DSGVO-Auftragsverarbeitungsvertrag (Art. 28 DSGVO) und ggf. Drittlandtransfer-Prüfung nötig; (b) vertragliche Zusicherung der Transparenz-/Kennzeichnungs-Unterstützung durch den Anbieter; (c) Werker-Freitext muss **vor** dem Cloud-Versand pseudonymisiert/NER-maskiert sein (siehe Anonymisierungs-Doku). Dies ist ein Wegweiser, keine Vollanalyse.

---

## 7. Pflichten je nach Einstufung

| | **Limited Risk (getroffene Einstufung)** | **High Risk (hypothetisch, falls Grenzfall §3 eintritt)** |
|---|---|---|
| Kennzeichnung | Art. 50: KI-Output sichtbar/maschinenlesbar als KI markieren | zusätzlich, plus volle Pflichten unten |
| Risikomanagement | nicht verpflichtend (freiwillig empfohlen) | **Art. 9:** dokumentiertes Risikomanagementsystem über den Lebenszyklus |
| Daten-Governance | gute Praxis | **Art. 10:** Daten-Governance, Repräsentativität, Bias-Kontrolle |
| Technische Doku | gute Praxis (GROUND_TRUTH/WALKTHROUGH) | **Art. 11 + Anhang IV:** formale technische Dokumentation |
| Logging | Observability (§11) | **Art. 12:** automatische Ereignis-Protokollierung (Rückverfolgbarkeit) |
| Menschliche Aufsicht | HITL als Design | **Art. 14:** nachweisbare menschliche Aufsicht, Eingriffs-/Override-Fähigkeit |
| Transparenz ggü. Nutzern | Art. 50 | **Art. 13:** detaillierte Betriebsanleitung |
| Konformitätsbewertung | keine | **Art. 43:** Konformitätsbewertung + CE-Kennzeichnung + EU-Datenbank-Registrierung |
| Qualitätsmanagement | — | **Art. 17:** QMS beim Anbieter |

**Für FOREMAN umzusetzen (Limited Risk):** die Transparenz-/Kennzeichnungs-, Logging- und KI-Kompetenz-Punkte aus §5 — schlank, in den bestehenden Quality-Gates verankerbar. Die High-Risk-Spalte ist **Vorsorge-Wissen** für den Fall, dass ein Kunde FOREMAN in einen sicherheitsgerichteten/automatischen Kontext zieht (dann ist vor Einsatz neu zu bewerten).

---

## 8. Zeitschiene (Verordnung (EU) 2024/1689)

| Datum | Wirksam | Relevanz für FOREMAN |
|---|---|---|
| 01.08.2024 | Inkrafttreten der Verordnung | Rahmen gesetzt |
| **02.02.2025** | **Verbote (Art. 5) + KI-Kompetenz (Art. 4)** | Art. 4 **bereits relevant** — Nutzer-Einweisung sicherstellen |
| **02.08.2025** | **GPAI-Pflichten (Art. 51–56), Governance, Sanktionen** | betrifft den **Modell-Provider**; FOREMAN als Deployer mittelbar |
| **02.08.2026** | **Hochrisiko nach Anhang III** voll anwendbar | für FOREMAN **nicht** einschlägig (Limited Risk); relevant nur im Grenzfall |
| **02.08.2027** | Hochrisiko nach **Anhang I** (Produktsicherheit, inkl. Maschinen-VO-Pfad) + Alt-GPAI-Compliance | Grenzfall-Datum, falls FOREMAN je als Maschinen-Sicherheitsbauteil integriert würde; MaschinenVO 2023/1230 ohnehin ab 20.01.2027 |

**Für ein Capstone-Projekt mit Freelance-Folgenutzung** heißt das: Die für FOREMAN tatsächlich tragenden Pflichten (Art. 50 Transparenz, Art. 4 KI-Kompetenz) sind **bereits jetzt** adressierbar und kostengünstig umzusetzen. Die schweren Hochrisiko-Pflichten greifen für die definierte Architektur nicht — werden aber zum Thema, sobald die Nutzung Richtung automatische Sicherheitsfunktion driftet.

---

## 9. Fazit & offene Punkte

**Einstufung (eindeutig): FOREMAN ist ein KI-System mit begrenztem Risiko (Limited Risk) nach der Verordnung (EU) 2024/1689.** Es ist weder verboten (Art. 5) noch hochriskant (Art. 6 i. V. m. Anhang I/III): Es ist kein Sicherheitsbauteil kritischer Infrastruktur, kein in eine konformitätspflichtige Maschine integriertes ML-Sicherheitsbauteil, und es fällt in keinen Anhang-III-Anwendungsfall. Es treffen FOREMAN die **Transparenzpflichten des Art. 50** und die **KI-Kompetenz-Pflicht des Art. 4**; gegenüber dem GPAI-Modell ist FOREMAN **Deployer**, nicht Provider. Diese Einstufung steht und fällt mit der **Human-in-the-Loop-Architektur ohne automatische Aktorik** — sie ist die tragende Bedingung, nicht eine Option.

**Maßnahmenliste (direkt in GROUND_TRUTH §10.5 + Code übernehmbar):**

1. **KI-Kennzeichnung Dashboard (Art. 50(1)):** Jede LLM-Empfehlung/-Erklärung sichtbar als „KI-Empfehlung – vom Operator zu prüfen" auszeichnen.
2. **KI-Kennzeichnung MCP (Art. 50(2)) — ✅ gebaut (F7):** Maschinenlesbares Herkunfts-Flag im Output-Schema: `ai_generated: true`, `generated_by: "foreman-ai"`, `requires_human_review: true`, `model_version`. Umgesetzt im read-only MCP-Server (`src/foreman/mcp/`): ein gemeinsamer Transparenz-Wrapper hüllt jeden KI-stämmigen Output (Vorhersage/Empfehlung zusätzlich `validation_status`/`data_regime`/`validation_caveat`); ein Validator erzwingt die Ehrlichkeit strukturell, Nicht-KI-Daten tragen keine KI-Flags. Vertrag: GROUND_TRUTH §17.
3. **Human-in-the-Loop hart verankern:** keine automatische Aktorik; sicherheitskritische Alarme nur über Operator-Quittierung (`alarms.acknowledged_at/_by`) als erledigt — bereits in §8 GROUND_TRUTH, hier als AI-Act-Pflicht bekräftigt.
4. **Logging/Nachvollziehbarkeit:** KI-Ausgaben mit `model_version`, Zeitstempel, Reasoner-Quelle protokollieren (Observability §11).
5. **KI-Kompetenz (Art. 4):** kurze Nutzer-Einweisung/Doku zu Möglichkeiten und Grenzen der Reasoner (z. B. Abschnitt in WALKTHROUGH/README).
6. **Grenzfall-Klausel dokumentieren:** In Doku/Vertrag festhalten, dass FOREMAN ausschließlich beratend ist; jede Integration in automatische Sicherheitsfunktionen oder konformitätspflichtige Maschinen erfordert eine **Neubewertung** (potenziell High Risk, Art. 6(1)).
7. **Cloud-Wegweiser:** Bei Nutzung des Cloud-Fallbacks AVV (Art. 28 DSGVO) + Pseudonymisierung/NER vor Versand sicherstellen (Querverweis Anonymisierungs-Doku).
8. **Versionierung dieses Assessments:** bei Architektur-Änderung (Aktorik, neue Datenarten, Personenbezug, Einsatz in kritischer Infrastruktur) neu bewerten.

**Offene Punkte:**

- **Finale Leitlinien-Lage:** Die Kommissions-Leitlinien zur Hochrisiko-Klassifizierung (Anhang I/III) liegen in Entwurfs-/Konsolidierungsfassung vor — bei Finalisierung gegenprüfen.
- **Kundenspezifischer Einsatzkontext:** Pro Kunde verifizieren, dass die Anlage **keine** kritische Infrastruktur i. S. d. Anhang III(2) ist und FOREMAN nicht als Sicherheitsbauteil eingebunden wird.
- **MaschinenVO-Schnittstelle:** Bei Einbindung in Maschinen, die nach 2023/1230 (ab 20.01.2027) zu bewerten sind, frühzeitig klären, ob FOREMAN als Sicherheitsbauteil gilt.
- **Verbindliche Absicherung:** Vor echtem Produktiveinsatz ist die Einstufung anwaltlich / durch eine Konformitätsbewertungsstelle zu bestätigen.

---

## Quellen

- **Verordnung (EU) 2024/1689** (KI-Verordnung): Art. 4 (KI-Kompetenz), Art. 5 (verbotene Praktiken), Art. 6(1)/(2)/(3) + Anhang I/III (Hochrisiko-Klassifizierung), Art. 9–14, 17, 43 (Hochrisiko-Pflichten), Art. 50 (Transparenz), Art. 51–56 (GPAI). https://eur-lex.europa.eu/eli/reg/2024/1689/oj
- Europäische Kommission / AI Office: Leitlinien zur Klassifizierung von Hochrisiko-KI-Systemen (Entwurf/Stand 2025/2026); Leitlinien zur Definition eines KI-Systems und zu verbotenen Praktiken (Feb. 2025). https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai
- AI Act — Anhang III (Hochrisiko-Anwendungsfälle), insb. Nr. 2 (kritische Infrastruktur). https://artificialintelligenceact.eu/annex/3/ · Art. 6. https://artificialintelligenceact.eu/article/6/
- Art. 50 — Transparenzpflichten für Anbieter und Betreiber. https://artificialintelligenceact.eu/article/50/
- **Verordnung (EU) 2023/1230** (Maschinenverordnung; anwendbar ab 20.01.2027), inkl. Drittkonformitätsbewertung für ML-basierte Sicherheitsbauteile. https://eur-lex.europa.eu/eli/reg/2023/1230/oj
- Umsetzungs-Zeitschiene des AI Act (gestaffelte Geltung 02/2025, 08/2025, 08/2026, 08/2027). EU-Kommission, „AI Act | Shaping Europe's digital future".

> **Rechtlicher Vorbehalt (Wiederholung):** Diese Selbsteinschätzung dient der internen Orientierung und der Darstellung des methodischen Vorgehens nach außen. Sie ersetzt keine Rechtsberatung. Die verbindliche Einstufung und etwaige Konformitätspflichten sind vor einem echten Produktiveinsatz durch einen Fachanwalt für IT-/Produktrecht bzw. eine Konformitätsbewertungsstelle abzusichern. Maßgeblich ist der konkrete Einsatzkontext beim jeweiligen Betreiber.
