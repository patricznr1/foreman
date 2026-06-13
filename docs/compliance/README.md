# Compliance

Regulatorische Einordnung und Datenschutz von FOREMAN — EU AI Act und DSGVO. Alle Dokumente hier sind **fundierte Selbsteinschätzungen zur internen Orientierung und Außendarstellung des methodischen Vorgehens**, keine Rechtsberatung; die verbindliche Bewertung erfolgt vor Produktiveinsatz juristisch.

## Inhalt

- [`eu-ai-act-assessment.md`](./eu-ai-act-assessment.md) — Einordnung von FOREMAN unter die Verordnung (EU) 2024/1689 (KI-Verordnung). Ergebnis: **Limited Risk** (Transparenzpflichten Art. 50, KI-Kompetenz Art. 4), Deployer eines GPAI-Modells, kein Hochrisiko — bedingt durch die Human-in-the-Loop-Architektur ohne automatische Aktorik. Enthält Entscheidungsbaum, Anhang-III- und Maschinenverordnungs-Prüfung sowie eine Maßnahmenliste für GROUND_TRUTH §10.5.
- [`dsgvo-assessment.md`](./dsgvo-assessment.md) — Datenschutzkonformität von FOREMAN nach DSGVO (Default: lokaler Betrieb). Behandelt das rechtliche **Ob/Warum/Wieweit**: Personenbezug, Rechtsgrundlagen (Art. 6(1)(c)/(f), § 26 BDSG entfallen, Betriebsvereinbarung), Zweckbindung, Betroffenenrechte, Privacy by Design, Cloud-Auftragsverarbeitung als Wegweiser. Ergebnis u. a.: **DSFA ja** (vorsorglich, erwartet geringes Restrisiko). Feld-Tabelle + Maßnahmenliste + Löschkonzept.
- [`dsfa-foreman-vorlaeufig.md`](./dsfa-foreman-vorlaeufig.md) — **vorläufige, konzeptbasierte Datenschutz-Folgenabschätzung** nach Art. 35(7) DSGVO (Schwellwert, Beschreibung, Notwendigkeit/Verhältnismäßigkeit, Risikomatrix R1–R9, Abhilfemaßnahmen + Restrisiko, Ergebnis). Ergebnis: Restrisiko nach Maßnahmen **gering**, **keine Art.-36-Konsultation** nötig. Vor Produktiveinsatz mit DSB/Betriebsrat zu finalisieren.

## Querverweis (technisches Wie, in `../research/`)

- [`../research/anonymisierung-werkerdaten.md`](../research/anonymisierung-werkerdaten.md) — das **technische Wie** der Pseudonymisierung (HMAC-Tokenisierung, NER, Salt/Key-Rotation, Crypto-Shredding, Mapping-Trennung). Bleibt im Research-Ordner; das **rechtliche Ob/Warum** steht in `dsgvo-assessment.md`. Klare Arbeitsteilung: hier Recht, dort Technik.

## Pflege

Jedes Compliance-Dokument wird neu bewertet bei: Architektur-Änderung (Aktorik, neue Datenarten, Personenbezug), Einsatz in kritischer Infrastruktur, Finalisierung der EU-Leitlinien, oder neuem Betreiber-Kontext.
