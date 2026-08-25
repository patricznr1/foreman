# Aussagen-Register — foreman

Generiert von claims-tool 1.0.0 aus `claims/claims.yaml` — nicht von Hand bearbeiten.

Stand: 2026-08-25

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
| C-009 | Die Abweichungserkennung meldete den Verschleiss 1,3 bis 16,0 Tage vor der ersten menschlichen Reaktion. | gemessen | Vorlauf 2,7 Tage (Lagerschaden), 1,3 Tage (Werkzeugverschleiss), 16,0 Tage (Schmierstoff-Fehlwahl) | 2026-08-10 | gueltig | intern, fach |
| C-010 | Der Erkennungszeitpunkt liegt bei zwei der drei Verläufe ausserhalb des im Szenario erwarteten Fensters. | gemessen | Lagerschaden: erwartet 7 bis 10 Tage, gemessen rund 13,9 Tage nach Beginn | 2026-08-10 | gueltig | intern, fach |
| C-011 | Der Arbeitspunkt der Abweichungserkennung wurde durch einen Durchlauf über drei Schwellenkandidaten bestimmt. | gemessen | Gewählt: Schwelle 3,0 bei einer Persistenz von 12 Intervallen; verworfen 2,5 und 3,5 | 2026-06-14 | gueltig | intern |
| C-012 | Die Ausfalleinschätzung ist auf Simulationsdaten trainiert und gegen reale Ausfälle nicht überprüft. | gemessen | Der Vorbehalt ist an drei Stellen erzwungen: Datenobjekt, Kennzahlen-Label, Datenbankspalte | 2026-06-15 | gueltig | intern, fach, kunde |
| C-013 | Die Ausfalleinschätzung trennt die Prüfdaten des Simulators nahezu vollständig. | gemessen | Präzisions-Ausbeute-Fläche 0,998; Rangordnungsgüte 0,998; Kalibrierungsmass 0,025 | 2026-06-15 | gueltig | intern |
| C-014 | Das Trainingsmaterial der Ausfalleinschätzung umfasst weniger als fünfhundert bewertete Zeitfenster. | gemessen | 369 Trainings-Fenster (222 mit Ausfall, 147 ohne), 123 Prüf-Fenster | 2026-06-15 | gueltig | intern |
| C-015 | Die Ausfalleinschätzung entscheidet erst ab einer sehr hohen Modellsicherheit auf Ausfall. | gemessen | Entscheidungsschwelle 0,997 | 2026-06-15 | gueltig | intern |
| C-016 | Die Ausfalleinschätzung ist auf einen Vorhersagehorizont von zwei Wochen ausgelegt. | konzipiert | — | 2026-06-15 | gueltig | intern, fach |
| C-017 | Zahlen in einer Werker-Empfehlung stammen ausschliesslich aus dem Rechenmodell, nie aus dem Sprachmodell. | gemessen | Unbelegte Zahlen führen zur Ablehnung der Empfehlung, nicht zu einer Markierung | 2026-07-31 | gueltig | intern, fach, kunde |
| C-018 | Die Prüfsuite des Backends läuft vollständig grün. | gemessen | 1083 bestanden, 2 übersprungen, 4 abgewählt | 2026-08-24 | gueltig | intern, fach |
| C-019 | Die Prüfabdeckung des Backends liegt über der im Manifest erzwungenen Untergrenze. | gemessen | 94,33 Prozent Zweigabdeckung, Untergrenze 85 Prozent | 2026-08-22 | gueltig | intern, fach |
| C-020 | Die Prüfabdeckung wird im Manifest erzwungen und lässt den Bau unterhalb der Grenze scheitern. | geplant | — | 2026-07-31 | gueltig | intern, fach |
| C-021 | Die Prüfsuite des Oberflächen-Teils läuft vollständig grün. | gemessen | 754 bestanden in 147 Prüfdateien | 2026-08-24 | gueltig | intern, fach |
| C-022 | Typprüfung und Stilprüfung laufen über den gesamten Quelltext ohne Befund durch. | gemessen | 0 Typfehler über 150 Dateien im Backend, 0 im Oberflächen-Teil; Stilprüfung und Formatprüfung über 316 Dateien ohne Befund | 2026-08-24 | gueltig | intern, fach |
| C-023 | Die Prüfläufe laufen gegen eine echte Zeitreihen-Datenbank statt gegen Attrappen. | gemessen | Ein Dienst-Container mit der produktiv eingesetzten Datenbankfassung wird für jeden Lauf gestartet | 2026-07-31 | gueltig | intern, fach |
| C-024 | Der Freitext-Pfad des erklärenden Sprachmodells wird mit gezielten Angriffsmustern geprüft. | gemessen | Ein fester Angriffssatz läuft bei jedem Prüflauf durch die vollständige Erklär-Kette | 2026-07-31 | gueltig | intern, fach, kunde |
| C-025 | Die Plattform ist als KI-System mit begrenztem Risiko eingestuft, mit Transparenzpflichten. | konzipiert | — | 2026-06-30 | gueltig | intern, fach, kunde |
| C-026 | Die Einstufung als begrenztes Risiko kippt, sobald ein Betreiber die Ausgaben automatisch schalten lässt. | konzipiert | — | 2026-06-30 | gueltig | intern, fach, kunde |
| C-027 | Personenbezogene Felder werden vor der Speicherung durch ein nicht rückrechenbares Kürzel ersetzt. | gemessen | Verfasser und Ausführende werden tokenisiert; Werker-Freitext wird zusätzlich auf Namen geschwärzt | 2026-07-31 | gueltig | intern, fach, kunde |
| C-028 | Wartungs- und Alarmtexte werden nicht auf Personennamen geschwärzt und im Archiv unverändert ausgeliefert. | gemessen | 2 von 3 Freitextfeldern ohne Namensschwärzung | 2026-07-31 | gueltig | intern |
| C-029 | Konten und Rollen entstehen ausschliesslich über den Betreiber-Weg, nicht über die Schnittstelle. | gemessen | Drei serverseitig durchgesetzte Striche: keine Selbstanlage, Rollenprüfung auf den schreibenden Wegen, Identität aus dem Zugangsnachweis | 2026-07-31 | gueltig | intern, fach, kunde |
| C-031 | Die Plattform schaltet nichts; sie erklärt und empfiehlt, entschieden wird von einem Menschen. | gemessen | Keine schreibende oder auslösende Schnittstelle nach aussen; sicherheitsrelevante Meldungen gelten erst nach Quittierung als erledigt | 2026-07-31 | gueltig | intern, fach, kunde |
| C-032 | Jede KI-erzeugte Ausgabe an Drittsysteme trägt eine Kennzeichnung ihrer Herkunft und ihres Prüfbedarfs. | gemessen | Vier Pflichtangaben je Ausgabe, bei Einschätzungen drei weitere zum Validierungsstand | 2026-07-31 | gueltig | intern, fach, kunde |
| C-033 | Das Langzeitgedächtnis ist ein eigenständiger Dienst ausserhalb dieses Systems und austauschbar angebunden. | gemessen | Kein Code des Gedächtnis-Dienstes in diesem Bestand; Anbindung ausschliesslich über eine Netzschnittstelle | 2026-07-31 | gueltig | intern, fach, kunde |
| C-034 | Die Erklärungen des Systems trennen sichtbar zwischen belegten Ereignissen und erzähltem Zusammenhang. | gemessen | Zitierte Quellen werden gegen eine Positivliste geprüft; erfundene Quellen und unbelegte Zahlen werden gekennzeichnet gespeichert | 2026-07-31 | gueltig | intern, fach, kunde |
| C-035 | Der Zugriff auf ein Sprachmodell läuft bevorzugt über ein lokal betriebenes Modell. | gemessen | Vier wählbare Betriebsarten, lokal zuerst als Grundeinstellung | 2026-07-31 | gueltig | intern, fach, kunde |
| C-036 | Der Zugriff auf das Sprachmodell ist nach oben begrenzt, damit ein Fehllauf keine offenen Kosten erzeugt. | geplant | — | 2026-07-31 | gueltig | intern |
| C-037 | Die Kostenschätzung für den Cloud-Zugriff rechnet bewusst mit dem Listenpreis statt mit dem Einführungspreis. | geschaetzt | ca. 3 US-Dollar je Million Eingabe-Zeichenblöcke, ca. 15 je Million Ausgabe-Zeichenblöcke | 2026-07-30 | gueltig | intern |
| C-038 | Die Antwortzeit der Plattform ist nicht erhoben; es liegen ausschliesslich Messpunkte des Gedächtnis-Dienstes vor. | gemessen | 0 erhobene Antwortzeit-Verteilungen für die Plattform selbst | 2026-08-10 | gueltig | intern |
| C-039 | Der vierte Auswerte-Baustein zu Wartungszyklen ist nicht gebaut und hängt an einer echten Wartungshistorie. | geplant | — | 2026-07-31 | gueltig | intern |
| C-042 | Beim Nachtrag der Spiegelung fielen sechs Alarmpaare zusammen, weil ihr Text sie nicht unterscheidbar machte. | gemessen | aus 65 nachgetragenen Ereignissen wurden 59 Erinnerungen; 6 Alarme gingen als vermeintliche Dublette verloren | 2026-08-20 | gueltig | intern |
| C-043 | Die Antwortform der Gedächtnis-Schnittstelle ist gegen die betriebene Instanz abgenommen, nicht nur gegen Annahmen. | gemessen | 7 zurückgegebene Felder und 7 Metadatenfelder, gegen 6 gesendete Feldern geprüft | 2026-08-20 | gueltig | intern |
| C-044 | Der Text einer Schichtnotiz verlässt die Anlage und wird im Gedächtnis abgelegt. | gemessen | 1 von 7 gespiegelten Ereignisarten trägt Freitext; die übrigen sechs nur Kennungen, Typen und Zeitpunkte | 2026-08-24 | gueltig | intern |
| C-045 | Ein Löschverlangen für eine gespiegelte Erinnerung ist von der Plattform aus erfüllbar. | gemessen | 1 Löschweg, der bei Fehlschlag wirft statt ihn zu verschlucken | 2026-08-24 | gueltig | intern |
| C-046 | Den Validierungs-Vorbehalt formuliert das System, nicht das Sprachmodell. | gemessen | 2 von 2 heiklen Angaben einer Empfehlung kommen deterministisch: Zahlen und Vorbehalt | 2026-08-24 | gueltig | intern, fach, kunde |
| C-047 | Für die Archiv-Suche existiert ein Bewertungssatz, dessen Relevanzurteile von drei voneinander unabhängigen Beurteilern getragen werden. | gemessen | 18 Anfragen, 79 Relevanz-Zuordnungen, 86,6 % Übereinstimmung aller drei Beurteiler | 2026-08-24 | gueltig | intern, fach |
| C-048 | Die Ähnlichkeitsschwelle der Archiv-Suche war nie an echten Daten justiert; nach der Justierung findet die Suche deutlich mehr. | gemessen | Schwelle 0,55 → 0,60: Trefferquote 0,185 → 0,256 (+38 %), Ranggüte 0,306 → 0,372 (+22 %) | 2026-08-24 | gueltig | intern, fach |
| C-049 | Die Güte der quellenübergreifenden Archiv-Suche ist erstmals beziffert. | gemessen | Trefferquote 0,256 · Genauigkeit 0,415 · Ranggüte 0,372 (k=10, drei Quellen, Schwelle 0,60) | 2026-08-24 | gueltig | intern, fach |
| C-050 | Das Gedächtnis als vierte Archiv-Quelle erfüllt seine Freigabe-Bedingung im gegenwärtigen Zustand nicht. | gemessen | 0 % der Anfragen mit zusätzlichem zutreffendem Treffer (gefordert: mindestens 30 %); auf 11 von 18 Anfragen verschlechterte Reihenfolge | 2026-08-24 | gueltig | intern, fach |
| C-051 | Der Rückweg für ein Löschverlangen war über die Betriebskonfiguration nicht erreichbar; er ist es seit dem 25.08.2026. | gemessen | Aufruf schlug im Betrieb fehl, während alle Tests bestanden — 22 von 22 Versuchen | 2026-08-25 | gueltig | intern |
| C-052 | Ein Löschverlangen für die ins Gedächtnis gespiegelten Inhalte ist derzeit nicht erfüllbar. | gemessen | Die Schnittstelle der Gegenstelle bietet keinen Löschweg — 6 Wege vorhanden, keiner davon löschend | 2026-08-25 | gueltig | intern |
| C-053 | Die Verdichtung des Gedächtnisses wird von der Plattform nicht angestossen. | gemessen | 62 von 63 Erinnerungen auf der mittleren Ebene, 1 auf der gefestigten; 1 von 63 im Wissensnetz verarbeitet | 2026-08-25 | gueltig | intern |
| C-054 | Im Gedächtnis liegen Erinnerungen zu Vorgängen, die es in der Datenbank nicht mehr gibt. | gemessen | 22 von 44 Spiegelungen ohne zugehörige Quellzeile | 2026-08-25 | gueltig | intern |
| C-055 | Die Plattform kann das Entfernen einer einzelnen gespiegelten Erinnerung bei der Gegenstelle anfordern. | gemessen | Anforderung nach dem vereinbarten Muster, mit unterscheidbarer Antwort auf einen nicht vorhandenen Eintrag | 2026-08-25 | gueltig | intern |
| C-056 | Für die Plattform liegt keine Einstufung nach den einschlägigen Regelwerken vor. | gemessen | Kein Verzeichnis für die Einstufung, keine Sektion in der Wahrheitsdatei — 4 Regelwerke offen | 2026-08-25 | gueltig | intern |
| C-057 | Die Zugriffskontrolle der Schnittstelle wirkt auf der Ebene der Anmeldung, nicht auf der Ebene der einzelnen Ressource. | gemessen | 31 von 47 geprüften Routen ohne Feststellung des Aufrufers an der Route selbst | 2026-08-25 | gueltig | intern |
| C-060 | Die Freigabe-Bedingung für das Gedächtnis als vierte Archiv-Quelle ist mit der heutigen Antwortform nicht messbar. | gemessen | 0 von 77 ausgelieferten Erinnerungs-Treffern konnte einer Quellzeile zugeordnet werden | 2026-08-25 | gueltig | intern |
| C-061 | Werden die Erinnerungs-Treffer ihrer Quellzeile zugeordnet, verbessert die vierte Quelle die Archiv-Suche deutlich. | gemessen | Trefferquote 0,256 auf 0,558; Ranggüte 0,372 auf 0,619; 70,6 % der Anfragen mit zusätzlichem zutreffendem Treffer, keine mit verlorenem | 2026-08-25 | gueltig | intern |
| C-062 | Ein Treffer aus dem Gedächtnis lässt sich seiner Quellzeile zuordnen. | gemessen | Herkunftsangabe im Treffer, sobald die Erinnerung sie trägt; sonst kein Eintrag statt einer geratenen Zuordnung | 2026-08-25 | gueltig | intern |

## Nicht verwendbar

Diese Einträge tragen heute nicht. Sie bleiben stehen und werden nie gelöscht.

| ID | Produkt | Aussage | Geltung | Grund |
|---|---|---|---|---|
| C-030 | FOREMAN | Die lesenden Listen sind nicht nach Zuständigkeit gefiltert; die Rollensicht ist dort nur eine Anzeigehilfe. | ueberholt | Am 25.08.2026 durch C-057 im Umfang widerlegt: Die Zahl 3 war aus der Beschreibung im Repository abgelesen, nicht an der Anwendung erhoben. Gegen die real gebaute Anwendung sind es 31 von 47 Routen. |
| C-040 | FOREMAN | Die öffentlich ausgelieferte Projektseite trägt einen eingefrorenen, überholten Spezifikationsstand. | ueberholt | BEHOBEN AM 10.08.2026, Commit 59af0aa auf dem Auslieferungszweig. Die Kopien von Spezifikation, Projekttext und Konfigurationsvorlage sind entfernt statt aktualisiert — die Projektseite braucht keine davon, belegt: ihre Startdatei referenziert ausschliesslich eingebettete Inhalte und externe Adressen, keine einzige lokale Datei. Eine zweite Kopie zu pflegen war genau der Mechanismus, der den Auseinanderlauf erzeugt hat. Nachgeprüft nach dem Seitenaufbau: Startseite liefert weiterhin 200, die vier entfernten Adressen liefern 404. |
| C-041 | FOREMAN | Fünfundsechzig gespiegelte Ereignisse trugen eine Kennung, unter der im Gedächtnis nichts lag. | ueberholt | Am selben Tag behoben: Die betroffenen Kennungen wurden zurückgesetzt und der Nachtrag ist gelaufen — sein Ergebnis steht als C-042. Der Eintrag bleibt stehen, weil er erklärt, warum eine Zeile mit gesetzter Kennung nicht ohne Weiteres als gespiegelt gelten darf. |

## Zählung

Einträge gesamt: 60

Nach Status:

- gemessen: 53
- geschaetzt: 1
- geplant: 3
- konzipiert: 3

Nach Geltung:

- gueltig: 57
- ueberholt: 3
- ungeprueft: 0
