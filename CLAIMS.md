# Aussagen-Register — foreman

Generiert von claims-tool 1.0.0 aus `claims/claims.yaml` — nicht von Hand bearbeiten.

Stand: 2026-08-10

## FOREMAN

| ID | Aussage | Status | Wert | Datum | Geltung | Freigabe |
|---|---|---|---|---|---|---|
| C-001 | Von den vier vorgesehenen Auswerte-Bausteinen der Plattform sind drei gebaut, der vierte ist noch offen. | gemessen | 3 von 4 — Ereignisketten, Abweichungserkennung und Ausfalleinschätzung gebaut; Wartungszyklen offen | 2026-07-31 | gueltig | intern, fach |
| C-002 | Die Plattform stellt Drittsystemen elf nur lesende Abfragen über eine offene Schnittstelle bereit. | gemessen | 11 Werkzeuge, alle als nur lesend gekennzeichnet | 2026-07-31 | gueltig | intern, fach, kunde |
| C-003 | Acht der zehn geplanten Bedienoberflächen-Bereiche sind gebaut, zwei stehen als gekennzeichnete Platzhalter. | gemessen | 8 von 10 gebaut; Wartung und Belastung sind Platzhalter | 2026-07-31 | gueltig | intern, fach |
| C-004 | Die Datenhaltung umfasst sechzehn Tabellen, aufgebaut über dreizehn aufeinander aufbauende Schemaschritte. | gemessen | 16 Tabellen, 13 Migrationsschritte (0001 bis 0013) | 2026-07-31 | gueltig | intern |
| C-005 | Die Anbindung an echte Anlagen-Protokolle ist noch nicht gebaut; Datenquelle ist bislang ausschliesslich ein Simulator. | gemessen | 0 von 3 Protokoll-Anbindungen installiert; ein Simulations-Adapter vorhanden | 2026-07-31 | gueltig | intern |
| C-006 | Die Abweichungserkennung meldet alle drei Verschleiss-Verläufe des Prüfsatzes vor dem ersten Anlagen-Alarm. | gemessen | 3 von 3 Verläufen mit nutzbarem Vorlauf erkannt | 2026-06-14 | gueltig | intern, fach |
| C-007 | Auf der gesunden Vergleichsmaschine erzeugt die Abweichungserkennung über den ganzen Prüfzeitraum keine Meldung. | gemessen | 0 Meldungen im Szenario der gesunden Maschine; 0 Meldungen am Kontroll-Lager des Schmierstoff-Szenarios | 2026-06-14 | gueltig | intern, fach |
| C-008 | Die Abweichungserkennung meldete einen Verschleissverlauf zwischen 1,9 und 6,9 Tagen nach dessen Beginn. | gemessen | Verzug 6,9 Tage (Lagerschaden), 5,0 Tage (Werkzeugverschleiss), 1,9 Tage (Schmierstoff-Fehlwahl) | 2026-08-10 | gueltig | intern, fach |
| C-009 | Die Abweichungserkennung meldete den Verschleiss zwischen 2,5 und 19,3 Tage vor dem ersten Anlagen-Alarm. | gemessen | Vorlauf rund 3,4 Tage (Lagerschaden), 2,5 Tage (Werkzeugverschleiss), 19,3 Tage (Schmierstoff-Fehlwahl) | 2026-08-10 | gueltig | intern, fach |
| C-011 | Der Arbeitspunkt der Abweichungserkennung wurde durch einen Durchlauf über drei Schwellenkandidaten bestimmt. | gemessen | Gewählt: Schwelle 3,0 bei einer Persistenz von 12 Intervallen; verworfen 2,5 und 3,5 | 2026-06-14 | gueltig | intern |
| C-012 | Die Ausfalleinschätzung ist auf Simulationsdaten trainiert und gegen reale Ausfälle nicht überprüft. | gemessen | Der Vorbehalt ist an drei Stellen erzwungen: Datenobjekt, Kennzahlen-Label, Datenbankspalte | 2026-06-15 | gueltig | intern, fach, kunde |
| C-013 | Die Ausfalleinschätzung trennt die Prüfdaten des Simulators nahezu vollständig. | gemessen | Präzisions-Ausbeute-Fläche 0,998; Rangordnungsgüte 0,998; Kalibrierungsmass 0,025 | 2026-06-15 | gueltig | intern |
| C-014 | Das Trainingsmaterial der Ausfalleinschätzung umfasst weniger als fünfhundert bewertete Zeitfenster. | gemessen | 369 Trainings-Fenster (222 mit Ausfall, 147 ohne), 123 Prüf-Fenster | 2026-06-15 | gueltig | intern |
| C-015 | Die Ausfalleinschätzung entscheidet erst ab einer sehr hohen Modellsicherheit auf Ausfall. | gemessen | Entscheidungsschwelle 0,997 | 2026-06-15 | gueltig | intern |
| C-016 | Die Ausfalleinschätzung ist auf einen Vorhersagehorizont von zwei Wochen ausgelegt. | konzipiert | — | 2026-06-15 | gueltig | intern, fach |
| C-017 | Zahlen in einer Werker-Empfehlung stammen ausschliesslich aus dem Rechenmodell, nie aus dem Sprachmodell. | gemessen | Unbelegte Zahlen führen zur Ablehnung der Empfehlung, nicht zu einer Markierung | 2026-07-31 | gueltig | intern, fach, kunde |
| C-018 | Die Prüfsuite des Backends läuft vollständig grün. | gemessen | 977 bestanden, 2 übersprungen, 2 abgewählt | 2026-08-10 | gueltig | intern, fach |
| C-019 | Die Prüfabdeckung des Backends liegt über der im Manifest erzwungenen Untergrenze. | gemessen | 94,45 Prozent Zweigabdeckung, Untergrenze 85 Prozent | 2026-08-10 | gueltig | intern, fach |
| C-020 | Die Prüfabdeckung wird im Manifest erzwungen und lässt den Bau unterhalb der Grenze scheitern. | geplant | — | 2026-07-31 | gueltig | intern, fach |
| C-021 | Die Prüfsuite des Oberflächen-Teils läuft vollständig grün. | gemessen | 733 bestanden in 144 Prüfdateien | 2026-08-10 | gueltig | intern, fach |
| C-022 | Typprüfung und Stilprüfung laufen über den gesamten Quelltext ohne Befund durch. | gemessen | 0 Typfehler über 148 Dateien im Backend, 0 im Oberflächen-Teil; Stilprüfung und Formatprüfung über 305 Dateien ohne Befund | 2026-08-10 | gueltig | intern, fach |
| C-023 | Die Prüfläufe laufen gegen eine echte Zeitreihen-Datenbank statt gegen Attrappen. | gemessen | Ein Dienst-Container mit der produktiv eingesetzten Datenbankfassung wird für jeden Lauf gestartet | 2026-07-31 | gueltig | intern, fach |
| C-024 | Der Freitext-Pfad des erklärenden Sprachmodells wird mit gezielten Angriffsmustern geprüft. | gemessen | Ein fester Angriffssatz läuft bei jedem Prüflauf durch die vollständige Erklär-Kette | 2026-07-31 | gueltig | intern, fach, kunde |
| C-025 | Die Plattform ist als KI-System mit begrenztem Risiko eingestuft, mit Transparenzpflichten. | konzipiert | — | 2026-06-30 | gueltig | intern, fach, kunde |
| C-026 | Die Einstufung als begrenztes Risiko kippt, sobald ein Betreiber die Ausgaben automatisch schalten lässt. | konzipiert | — | 2026-06-30 | gueltig | intern, fach, kunde |
| C-027 | Personenbezogene Felder werden vor der Speicherung durch ein nicht rückrechenbares Kürzel ersetzt. | gemessen | Verfasser und Ausführende werden tokenisiert; Werker-Freitext wird zusätzlich auf Namen geschwärzt | 2026-07-31 | gueltig | intern, fach, kunde |
| C-028 | Wartungs- und Alarmtexte werden nicht auf Personennamen geschwärzt und im Archiv unverändert ausgeliefert. | gemessen | 2 von 3 Freitextfeldern ohne Namensschwärzung | 2026-07-31 | gueltig | intern |
| C-029 | Konten und Rollen entstehen ausschliesslich über den Betreiber-Weg, nicht über die Schnittstelle. | gemessen | Drei serverseitig durchgesetzte Striche: keine Selbstanlage, Rollenprüfung auf den schreibenden Wegen, Identität aus dem Zugangsnachweis | 2026-07-31 | gueltig | intern, fach, kunde |
| C-030 | Die lesenden Listen sind nicht nach Zuständigkeit gefiltert; die Rollensicht ist dort nur eine Anzeigehilfe. | gemessen | 3 Listen ohne serverseitige Zuständigkeitsprüfung | 2026-07-31 | gueltig | intern |
| C-031 | Die Plattform schaltet nichts; sie erklärt und empfiehlt, entschieden wird von einem Menschen. | gemessen | Keine schreibende oder auslösende Schnittstelle nach aussen; sicherheitsrelevante Meldungen gelten erst nach Quittierung als erledigt | 2026-07-31 | gueltig | intern, fach, kunde |
| C-032 | Jede KI-erzeugte Ausgabe an Drittsysteme trägt eine Kennzeichnung ihrer Herkunft und ihres Prüfbedarfs. | gemessen | Vier Pflichtangaben je Ausgabe, bei Einschätzungen drei weitere zum Validierungsstand | 2026-07-31 | gueltig | intern, fach, kunde |
| C-033 | Das Langzeitgedächtnis ist ein eigenständiger Dienst ausserhalb dieses Systems und austauschbar angebunden. | gemessen | Kein Code des Gedächtnis-Dienstes in diesem Bestand; Anbindung ausschliesslich über eine Netzschnittstelle | 2026-07-31 | gueltig | intern, fach, kunde |
| C-034 | Die Erklärungen des Systems trennen sichtbar zwischen belegten Ereignissen und erzähltem Zusammenhang. | gemessen | Zitierte Quellen werden gegen eine Positivliste geprüft; erfundene Quellen und unbelegte Zahlen werden gekennzeichnet gespeichert | 2026-07-31 | gueltig | intern, fach, kunde |
| C-035 | Der Zugriff auf ein Sprachmodell läuft bevorzugt über ein lokal betriebenes Modell. | gemessen | Vier wählbare Betriebsarten, lokal zuerst als Grundeinstellung | 2026-07-31 | gueltig | intern, fach, kunde |
| C-036 | Der Zugriff auf das Sprachmodell ist nach oben begrenzt, damit ein Fehllauf keine offenen Kosten erzeugt. | geplant | — | 2026-07-31 | gueltig | intern |
| C-037 | Die Kostenschätzung für den Cloud-Zugriff rechnet bewusst mit dem Listenpreis statt mit dem Einführungspreis. | geschaetzt | ca. 3 US-Dollar je Million Eingabe-Zeichenblöcke, ca. 15 je Million Ausgabe-Zeichenblöcke | 2026-07-30 | gueltig | intern |
| C-038 | Die Antwortzeit der Plattform ist nicht erhoben; es liegen ausschliesslich Messpunkte des Gedächtnis-Dienstes vor. | gemessen | 0 erhobene Antwortzeit-Verteilungen für die Plattform selbst | 2026-08-10 | gueltig | intern |
| C-039 | Der vierte Auswerte-Baustein zu Wartungszyklen ist nicht gebaut und hängt an einer echten Wartungshistorie. | geplant | — | 2026-07-31 | gueltig | intern |
| C-040 | Die öffentlich ausgelieferte Projektseite trägt einen eingefrorenen, überholten Spezifikationsstand. | gemessen | Stand vom 12.06.2026; nennt einen Zugangsweg als geltend, der seit dem 31.07.2026 entfernt ist | 2026-07-31 | gueltig | intern |

## Nicht verwendbar

Diese Einträge tragen heute nicht. Sie bleiben stehen und werden nie gelöscht.

| ID | Produkt | Aussage | Geltung | Grund |
|---|---|---|---|---|
| C-010 | FOREMAN | Der Erkennungszeitpunkt liegt bei zwei der drei Verläufe ausserhalb des im Szenario erwarteten Fensters. | ungeprueft | ZWEI DOKUMENTE, ZWEI MASSSTÄBE, KEINE ENTSCHEIDUNG. Die Zahl selbst ist seit dem 10.08.2026 gemessen und im Test festgehalten — offen ist nicht der Wert, sondern der Massstab: Die Szenario-Beschreibung führt das enge Fenster weiterhin als Validierungserwartung, die Kalibrierung erklärt es für ungeeignet und führt die Abnahme über den Vorlauf. Beide Dokumente stehen unverändert nebeneinander im Repo. Solange das nicht entschieden ist, lässt sich nicht sagen, ob die Erkennung fristgerecht war — und damit taugt der Eintrag für keine Unterlage. |

## Zählung

Einträge gesamt: 40

Nach Status:

- gemessen: 33
- geschaetzt: 1
- geplant: 3
- konzipiert: 3

Nach Geltung:

- gueltig: 39
- ueberholt: 0
- ungeprueft: 1
