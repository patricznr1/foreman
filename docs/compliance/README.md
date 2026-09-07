# Compliance

Regulatorische Einordnung und Datenschutz von FOREMAN — EU AI Act und DSGVO. Alle Dokumente hier sind **fundierte Selbsteinschätzungen zur internen Orientierung und Außendarstellung des methodischen Vorgehens**, keine Rechtsberatung; die verbindliche Bewertung erfolgt vor Produktiveinsatz juristisch.

## Inhalt

- [`eu-ai-act-assessment.md`](./eu-ai-act-assessment.md) — Einordnung von FOREMAN unter die Verordnung (EU) 2024/1689 (KI-Verordnung). Ergebnis: **Limited Risk** (Transparenzpflichten Art. 50, KI-Kompetenz Art. 4), Deployer eines GPAI-Modells, kein Hochrisiko — bedingt durch die Human-in-the-Loop-Architektur ohne automatische Aktorik. Enthält Entscheidungsbaum, Anhang-III- und Maschinenverordnungs-Prüfung sowie eine Maßnahmenliste für GROUND_TRUTH §10.5.
- [`dsgvo-assessment.md`](./dsgvo-assessment.md) — Datenschutzkonformität von FOREMAN nach DSGVO (Default: lokaler Betrieb). Behandelt das rechtliche **Ob/Warum/Wieweit**: Personenbezug, Rechtsgrundlagen (Art. 6(1)(c)/(f), § 26 BDSG entfallen, Betriebsvereinbarung), Zweckbindung, Betroffenenrechte, Privacy by Design, Cloud-Auftragsverarbeitung als Wegweiser. Ergebnis u. a.: **DSFA ja** (vorsorglich, erwartet geringes Restrisiko). Feld-Tabelle + Maßnahmenliste + Löschkonzept.
- [`dsfa-foreman-vorlaeufig.md`](./dsfa-foreman-vorlaeufig.md) — **vorläufige, konzeptbasierte Datenschutz-Folgenabschätzung** nach Art. 35(7) DSGVO (Schwellwert, Beschreibung, Notwendigkeit/Verhältnismäßigkeit, Risikomatrix R1–R9, Abhilfemaßnahmen + Restrisiko, Ergebnis). Ergebnis: Restrisiko nach Maßnahmen **gering**, **keine Art.-36-Konsultation** nötig. Vor Produktiveinsatz mit DSB/Betriebsrat zu finalisieren.

## Querverweis (technisches Wie, in `../research/`)

- [`../research/anonymisierung-werkerdaten.md`](../research/anonymisierung-werkerdaten.md) — das **technische Wie** der Pseudonymisierung (HMAC-Tokenisierung, NER, Salt/Key-Rotation, Crypto-Shredding, Mapping-Trennung). Bleibt im Research-Ordner; das **rechtliche Ob/Warum** steht in `dsgvo-assessment.md`. Klare Arbeitsteilung: hier Recht, dort Technik.

## Maschinenprüfbare Fassung (seit 26.08.2026)

Die Einstufungen dieser Dokumente liegen zusätzlich als YAML unter [`../../compliance/`](../../compliance/):

- `scope.yaml` — alle **vier** hausüblich geprüften Regelwerke ausdrücklich eingestuft: KI-VO greift (Anbieter, Transparenzpflicht Art. 50), DSGVO greift (Verantwortlicher ist der Betreiber), ISO/IEC 27001 und 21 CFR Part 11 greifen **nicht** — je mit Begründung, tragender Bedingung, Belegstatus und Prüftermin (2027-02-26). Register: C-126.
- `retention-policy.yaml` — Frist je Datenklasse mal Rechtsgrundlage; `soa.yaml` — Anwendbarkeitserklärung als freiwillige Bauordnung; `traceability.yaml` — Anforderung → Nachweis.

Prüfbefehl: `python scripts/check_compliance.py` (läuft in der CI). Die YAML-Dateien übertragen, sie entscheiden nicht neu — eine Abweichung zwischen ihnen und den Fließtext-Dokumenten ist ein Befund. Was offen ist, steht dort ausdrücklich als offen (Verarbeitungsverzeichnis, abschließende Folgenabschätzung, AVV und Transfergrundlage für die Cloud-Pfade, Fristen der Nachweis-Felder).

Nachträge in den Dokumenten: `dsgvo-assessment.md` (August 2026: Zugriffsbegrenzung; September 2026: Spiegelung ins Gedächtnis, Löschweg), `dsfa-foreman-vorlaeufig.md` (September 2026: Review-Trigger „neue Datenarten"), `eu-ai-act-assessment.md` (September 2026: Bau-Stand, Anbieter-Rolle, Fristenvorbehalt).

## Pflege

Jedes Compliance-Dokument wird neu bewertet bei: Architektur-Änderung (Aktorik, neue Datenarten, Personenbezug), Einsatz in kritischer Infrastruktur, Finalisierung der EU-Leitlinien, oder neuem Betreiber-Kontext. Kippt eine tragende Bedingung aus `compliance/scope.yaml`, ist die Datei neu zu bewerten, nicht fortzuschreiben.
