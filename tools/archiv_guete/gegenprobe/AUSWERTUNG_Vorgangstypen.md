# Auswertungsnotiz: wiederkehrende Vorgangstypen

**Montagelinie 1, Halle West — Material vom 02.02.2026 bis 31.08.2026**

Diese Notiz ist die Wahrheitsgrundlage zum gelieferten Material und gehört nicht in den Bestand, der durchsucht wird. Sie nennt für jeden der zwanzig wiederkehrenden Vorgangstypen den Fehlertyp, die betroffenen Maschinen, die Zeitpunkte, die zugehörigen Eintrags-Kennungen und die dazu geschriebenen Ablenker.

Die Kennungen (`SN-…` Schichtnotiz, `WA-…` Wartungseintrag, `AL-…` Alarm) sind die in den JSON-Dateien vergebenen Werte. Sie werden chronologisch über den gesamten Bestand vergeben, sind also innerhalb eines Vorgangs nicht fortlaufend.

---

## V1 — Lagerschaden am Linearführungslager einer Handling-Achse

**Maschinenklasse** `servo_axis` · **Komponente** `bearing`

Die Wälzkörper bzw. die Laufbahn eines Führungswagens laufen an. Zuerst hört man es, dann steigt die Schwingung, am Ende ist der Wagen schwergängig. Abhilfe ist immer der Tausch des Führungswagens.

**Vorkommen 1 — 09.02.–20.02.2026, AX-02**

AX-02, schleichend über elf Tage. Drei Notizen mit steigender Deutlichkeit, dann Schwingungswarnung, dann geplante Prüfung mit Wagentausch.

Einträge: `SN-006` 09.02. AX-02 (Notiz) · `SN-010` 13.02. AX-02 (Notiz) · `SN-013` 17.02. AX-02 (Notiz) · `AL-001` 18.02. AX-02 (Alarm, AXIS_VIB_WARN) · `WA-012` 20.02. AX-02 (Wartung, inspection)

**Vorkommen 2 — 12.05.–15.05.2026, AX-03**

AX-03 (Vertikalachse), von einer Schicht auf die andere. Zwei Notizen, Warnung, Prüfung — der ganze Vorgang dauert vier Tage.

Einträge: `SN-076` 12.05. AX-03 (Notiz) · `SN-077` 13.05. AX-03 (Notiz) · `AL-006` 14.05. AX-03 (Alarm, AXIS_VIB_WARN) · `WA-059` 15.05. AX-03 (Wartung, inspection)

**Vorkommen 3 — 20.07.–04.08.2026, AX-01**

AX-01, zuerst am falschen Ende gesucht: Der Motor wurde getauscht, ohne dass sich etwas änderte. Kein Alarm, nur Notizen und die abschließende Prüfung.

Einträge: `SN-139` 20.07. AX-01 (Notiz) · `SN-146` 24.07. AX-01 (Notiz) · `SN-150` 30.07. AX-01 (Notiz) · `WA-103` 04.08. AX-01 (Wartung, inspection)

**Woran die Wiederholung hängt.** Gemeinsam ist nur die Sache: ein Laufgeräusch an einer Handling-Achse, das über Tage zunimmt, und ein Führungswagen als Befund. Sprachlich trennen sich die drei Vorkommen vollständig — hoher Ton und Pfeifen · Mahlen und Kratzen · Rumpeln und Poltern.

**Ablenker.** AX-01 im April: gleiches Geräuschbild an derselben Maschinenklasse, Ursache ist aber die Energiekette, die an der Verkleidung schleift. Die Prüfung stellt Führung und Lager ausdrücklich ohne Befund fest.

Einträge: `SN-066` 28.04. AX-01 (Notiz) · `WA-050` 29.04. AX-01 (Wartung, inspection)

---

## V2 — Spiel im Kugelgewindetrieb, Positionsabweichung beim Richtungswechsel

**Maschinenklasse** `servo_axis` · **Komponente** `ballscrew`

Umkehrspiel in Spindel, Mutter oder Festlagerung. Die Achse trifft die Position nur noch aus einer Anfahrrichtung, Korrekturen im Programm halten nicht.

**Vorkommen 1 — 03.03.–10.03.2026, AX-01**

AX-01, über eine Woche. Zwei Notizen, dann Messung des Umkehrspiels und Nachstellen der Vorspannung.

Einträge: `SN-025` 03.03. AX-01 (Notiz) · `SN-029` 06.03. AX-01 (Notiz) · `WA-021` 10.03. AX-01 (Wartung, inspection)

**Vorkommen 2 — 25.05.–11.06.2026, AX-04**

AX-04, schleichend über gut zwei Wochen mit drei Notizen. Befund ist diesmal die Festlagerung, nicht die Mutter.

Einträge: `SN-087` 25.05. AX-04 (Notiz) · `SN-094` 02.06. AX-04 (Notiz) · `SN-101` 09.06. AX-04 (Notiz) · `WA-072` 11.06. AX-04 (Wartung, inspection)

**Vorkommen 3 — 05.08.–12.08.2026, AX-02**

AX-02, läuft bis die Qualität es sieht. Befund ist eine beschädigte Kugelrückführung, die Einheit muss raus — die Achse läuft bis dahin langsamer weiter (siehe Notiz vom 26.08.).

Einträge: `SN-156` 05.08. AX-02 (Notiz) · `SN-161` 10.08. AX-02 (Notiz) · `WA-108` 12.08. AX-02 (Wartung, inspection)

**Woran die Wiederholung hängt.** Dreimal dasselbe Muster: die Abweichung hängt an der Anfahrrichtung, nicht am Ort. Beschrieben wird es einmal als Ablegen daneben, einmal als Streuung, einmal über die Prüfmaße.

**Ablenker.** AX-02 im April: die Achse setzt daneben, aber die Greiferbacke hat Spiel. Der Verfasser sagt es selbst, und zwar erst im zweiten Satz.

Einträge: `SN-063` 22.04. AX-02 (Notiz)

---

## V3 — Haltebremse am Servomotor schleift oder löst verzögert

**Maschinenklasse** `servo_axis` · **Komponente** `motor`

Die Bremse öffnet nicht vollständig. Folge sind erhöhte Motortemperatur, höherer Strom und ein zähes Losfahren aus dem Stillstand.

**Vorkommen 1 — 24.02.–02.03.2026, AX-03**

AX-03, über eine Woche. Zwei Notizen, dann Prüfung mit Nachstellen der Bremse. Enthält eine falsche Fremdvermutung (Lager) im Text.

Einträge: `SN-019` 24.02. AX-03 (Notiz) · `SN-023` 26.02. AX-03 (Notiz) · `WA-017` 02.03. AX-03 (Wartung, inspection)

**Vorkommen 2 — 15.06.–16.06.2026, AX-01**

AX-01, innerhalb eines Tages eskaliert: nachts der Ruck beim Anfahren, morgens der Geruch, mittags die getauschte Bremseinheit.

Einträge: `SN-108` 15.06. AX-01 (Notiz) · `SN-110` 16.06. AX-01 (Notiz) · `WA-075` 16.06. AX-01 (Wartung, inspection)

**Vorkommen 3 — 11.08.–20.08.2026, AX-04**

AX-04, wird über zehn Tage dreimal notiert und bleibt offen — es gibt keinen Wartungseintrag dazu. Der Faden läuft im Sande und taucht in den Routine-Notizen vom 28.07. und 31.08. noch einmal auf.

Einträge: `SN-164` 11.08. AX-04 (Notiz) · `SN-172` 14.08. AX-04 (Notiz) · `SN-178` 20.08. AX-04 (Notiz)

**Woran die Wiederholung hängt.** Wärme, Strom und ein zäher Anlauf an einer Achse, deren Schwestern unter gleicher Last unauffällig sind. Einmal über die Temperatur erzählt, einmal über den Geruch, einmal über den Energieverbrauch.

**Ablenker.** AX-04 im Juli: Übertemperaturabschaltung, aber der Motor ist handwarm — der Schaltschranklüfter ist ausgefallen. Steht zeitlich zwischen den Vorkommen und betrifft dieselbe Maschine wie Vorkommen 3.

Einträge: `SN-126` 02.07. AX-04 (Notiz) · `WA-086` 02.07. AX-04 (Wartung, inspection)

---

## V4 — Falscher Schmierstoff bei der Nachschmierung, Führung läuft nicht frei

**Maschinenklasse** `servo_axis` · **Komponente** `bearing`

Bei der Regelschmierung wird ein Fett verwendet, das nicht dem Schmierplan entspricht. Acht bis vierzehn Tage später wird die Achse schwergängig. Der Wartungseintrag davor benennt das verwendete Material — dort steht die Ursache, nicht in der Notiz.

**Vorkommen 1 — 11.02.–04.03.2026, AX-04**

AX-04. Mehrzweckfett ISO VG 460 statt ISO VG 150. Symptom: verharzt, klebrig, zäh im Kaltlauf.

Einträge: `WA-006` 11.02. AX-04 (Wartung, lubrication) · `SN-017` 19.02. AX-04 (Notiz) · `SN-022` 25.02. AX-04 (Notiz) · `WA-019` 04.03. AX-04 (Wartung, inspection)

**Vorkommen 2 — 19.05.–05.06.2026, AX-02**

AX-02. EP-Fett NLGI 3 statt NLGI 2. Symptom: zu steif, feines Ruckeln bei langsamer Fahrt, Klemmen nach dem Wochenende.

Einträge: `WA-061` 19.05. AX-02 (Wartung, lubrication) · `SN-089` 27.05. AX-02 (Notiz) · `SN-095` 03.06. AX-02 (Notiz) · `WA-069` 05.06. AX-02 (Wartung, inspection)

**Vorkommen 3 — 08.07.–27.07.2026, AX-03**

AX-03. Fließfett NLGI 0 aus der Zentralanlage. Symptom: Schmierfilm reißt an der senkrechten Führung ab, Fett tritt unten aus. Enthält eine falsche Erstvermutung (Lager wie im Mai), die in der nächsten Notiz widerrufen wird.

Einträge: `WA-090` 08.07. AX-03 (Wartung, lubrication) · `SN-136` 16.07. AX-03 (Notiz) · `SN-143` 22.07. AX-03 (Notiz) · `WA-099` 27.07. AX-03 (Wartung, inspection)

**Woran die Wiederholung hängt.** Der Vorgang ist nur über die Paarung Wartungseintrag → Notiz erkennbar: ein abweichendes Schmiermittel, danach eine schwergängige Achse, danach eine Prüfung, die auf den Schmierplan zurückstellt. Die drei Fehlgriffe gehen in drei verschiedene Richtungen — zu zäh, zu steif, zu dünn.

**Ablenker.** AX-01 im Juni: schwergängig kurz nach einer Schmierung, der Verfasser tippt ausdrücklich auf falsches Fett. Die Prüfung bescheinigt den Schmierstoff als spezifikationskonform und findet einen eingeklemmten Span. Das ist der härteste Ablenker im Bestand, weil er die richtige Hypothese nennt und trotzdem falsch ist.

Einträge: `SN-100` 08.06. AX-01 (Notiz) · `WA-071` 09.06. AX-01 (Wartung, inspection)

---

## V5 — Geberrückführung am Motor gestört, sporadische Schleppfehler

**Maschinenklasse** `servo_axis` · **Komponente** `motor`

Leitung oder Steckverbinder der Motorrückführung sind angegriffen. Die Achse geht unregelmäßig in Störung, lässt sich quittieren und läuft weiter — bis die Kontaktstelle gefunden ist.

**Vorkommen 1 — 17.03.–01.04.2026, AX-02**

AX-02, über zwei Wochen mit drei Notizen. Befund: Scheuerstelle in der Energiekette.

Einträge: `SN-036` 17.03. AX-02 (Notiz) · `SN-037` 19.03. AX-02 (Notiz) · `SN-040` 24.03. AX-02 (Notiz) · `WA-034` 01.04. AX-02 (Wartung, inspection)

**Vorkommen 2 — 18.06.–25.06.2026, AX-04**

AX-04, eine Woche. Befund: feuchter Steckverbinder mit oxidierten Kontakten.

Einträge: `SN-111` 18.06. AX-04 (Notiz) · `SN-113` 22.06. AX-04 (Notiz) · `WA-083` 25.06. AX-04 (Wartung, inspection)

**Vorkommen 3 — 06.08.–13.08.2026, AX-01**

AX-01, zwei Notizen, keine Auflösung. Der Fehler bleibt aus und der Verfasser schiebt es auf eine Parametrierung — belegt ist das nicht.

Einträge: `SN-158` 06.08. AX-01 (Notiz) · `SN-169` 13.08. AX-01 (Notiz)

**Woran die Wiederholung hängt.** Sporadische Abschaltung ohne erkennbares Muster, quittierbar, kehrt wieder. Einmal Störung genannt, einmal Positionsverlust, einmal Fehlermeldung.

**Ablenker.** AX-03 Ende Mai: Schleppfehler nach einer Programmänderung. Zwei Notizen, die zweite nimmt die Rampe zurück und beendet den Fall. Keine Hardware beteiligt.

Einträge: `SN-090` 28.05. AX-03 (Notiz) · `SN-091` 01.06. AX-03 (Notiz)

---

## V6 — Lagerbock der Spindel gelockert, Schlag am Umkehrpunkt

**Maschinenklasse** `servo_axis` · **Komponente** `ballscrew`

Die Verschraubung der Spindellagerung löst sich. Am Richtungswechsel entsteht ein einzelner harter Schlag, der über Wochen zunimmt.

**Vorkommen 1 — 07.04.–13.04.2026, AX-03**

AX-03, eine Woche, rechtzeitig bemerkt. Vier von sechs Schrauben unter Anzugsmoment.

Einträge: `SN-050` 07.04. AX-03 (Notiz) · `SN-053` 09.04. AX-03 (Notiz) · `WA-038` 13.04. AX-03 (Wartung, inspection)

**Vorkommen 2 — 29.06.–09.07.2026, AX-01**

AX-01, über zehn Tage. Zu spät bemerkt: Gewinde im Grundkörper ausgerissen, Reparatur mit größerem Gewinde.

Einträge: `SN-120` 29.06. AX-01 (Notiz) · `SN-127` 06.07. AX-01 (Notiz) · `WA-091` 09.07. AX-01 (Wartung, inspection)

**Vorkommen 3 — 18.08.–19.08.2026, AX-04**

AX-04, am Folgetag der ersten Notiz erledigt. Nur eine Notiz und eine Prüfung — der kürzeste Vorgang dieses Typs.

Einträge: `SN-175` 18.08. AX-04 (Notiz) · `WA-118` 19.08. AX-04 (Wartung, inspection)

**Woran die Wiederholung hängt.** Ein Schlag genau im Umkehrpunkt, spürbar am Bauteil. Klopfen · Stoß und Hämmern · Rappeln.

**Ablenker.** AX-02 im Juli: klopft am Ende der Fahrt, es ist aber der Anschlag der Energiekette. Eine Zeile, keine Prüfung — so wie es im Betrieb notiert würde.

Einträge: `SN-134` 15.07. AX-02 (Notiz)

---

## F1 — Klemmzylinder am Dosiertrichter schaltet verzögert

**Maschinenklasse** `feeder` · **Komponente** `hopper`

Der pneumatische Klemmzylinder erreicht die Endlage später. Ursache liegt jedes Mal im Zylinder selbst — Kondensat, trockene Führung, verschlissene Dichtung.

**Vorkommen 1 — 17.02.–27.02.2026, FD-02**

FD-02, zehn Tage. Befund: Wasser im Zylinder, Dichtung gequollen.

Einträge: `SN-014` 17.02. FD-02 (Notiz) · `SN-018` 23.02. FD-02 (Notiz) · `WA-015` 27.02. FD-02 (Wartung, inspection)

**Vorkommen 2 — 06.05.–13.05.2026, FD-01**

FD-01, eine Woche. Befund: trocken gelaufene Führungsbuchse.

Einträge: `SN-070` 06.05. FD-01 (Notiz) · `SN-073` 11.05. FD-01 (Notiz) · `WA-056` 13.05. FD-01 (Wartung, inspection)

**Vorkommen 3 — 10.08.–17.08.2026, FD-02**

FD-02, erst am falschen Ende gesucht — Ventil getauscht ohne Wirkung. Befund: innere Leckage an der Kolbendichtung.

Einträge: `SN-163` 10.08. FD-02 (Notiz) · `SN-168` 12.08. FD-02 (Notiz) · `WA-115` 17.08. FD-02 (Wartung, inspection)

**Woran die Wiederholung hängt.** Die Klemmung braucht länger als an der Schwestermaschine. Beschrieben als Verzögerung im Takt · als Rucken beim Zufahren · als verdoppelte Schaltzeit.

**Ablenker.** FD-01 im März: die Klemmung kommt kaum noch, aber die Presse ist ebenfalls langsam — der Netzdruck im ganzen Hallenabschnitt ist unten. Erkennbar erst am zweiten Halbsatz.

Einträge: `SN-041` 25.03. FD-01 (Notiz)

---

## F2 — Brückenbildung im Dosiertrichter, Zuführung setzt aus

**Maschinenklasse** `feeder` · **Komponente** `hopper`

Das Schüttgut verhakt sich über dem Auslauf. Der Trichter ist voll, es kommt trotzdem nichts. Klopfen oder Rütteln hilft kurzfristig.

**Vorkommen 1 — 10.03.–16.03.2026, FD-01**

FD-01, knapp eine Woche. Befund: Ablagerungen an der Innenwand verringern den Auslaufwinkel.

Einträge: `SN-031` 10.03. FD-01 (Notiz) · `SN-033` 12.03. FD-01 (Notiz) · `WA-027` 16.03. FD-01 (Wartung, inspection)

**Vorkommen 2 — 08.06.–17.06.2026, FD-02**

FD-02, gut eine Woche. Befund: Charge mit stärkerem Grat verhakt sich im Auslaufkonus. Die Wirkung reicht bis PR-02, das steht in der Notiz.

Einträge: `SN-099` 08.06. FD-02 (Notiz) · `SN-106` 12.06. FD-02 (Notiz) · `WA-076` 17.06. FD-02 (Wartung, inspection)

**Vorkommen 3 — 06.08.–13.08.2026, FD-01**

FD-01, eine Woche, endet ohne belegten Erfolg: das Rüttler-Intervall wurde verkürzt, die Wirkung ist laut Wartungseintrag noch zu beobachten.

Einträge: `SN-157` 06.08. FD-01 (Notiz) · `SN-166` 11.08. FD-01 (Notiz) · `WA-111` 13.08. FD-01 (Wartung, inspection)

**Woran die Wiederholung hängt.** Voller Trichter, kein Nachschub, mechanische Nachhilfe hilft für eine Weile. Einmal als Aussetzer · einmal als Lücken im Nachschub · einmal als schwankende Dosierung erzählt.

**Ablenker.** FD-02 im Mai: eine halbe Stunde kein Nachschub, der Trichter war schlicht leer. Der Verfasser stellt selbst klar, dass es kein technischer Fehler war.

Einträge: `SN-081` 19.05. FD-02 (Notiz)

---

## F3 — Kraftschluss im Förderantrieb geht verloren, Zuführung bleibt hinter dem Takt

**Maschinenklasse** `feeder` · **Komponente** `feeder_drive`

Riemen oder Kupplung übertragen die Drehzahl nicht mehr vollständig. Sollwert und tatsächliche Fördermenge laufen auseinander.

**Vorkommen 1 — 14.04.–20.04.2026, FD-02**

FD-02, eine Woche. Befund: gelängter Zahnriemen, Spannrolle am Ende des Verstellwegs.

Einträge: `SN-057` 14.04. FD-02 (Notiz) · `SN-060` 16.04. FD-02 (Notiz) · `WA-044` 20.04. FD-02 (Wartung, inspection)

**Vorkommen 2 — 30.06.–07.07.2026, FD-01**

FD-01, eine Woche. Befund: durchgerutschte Klemmnabe auf der Motorwelle.

Einträge: `SN-122` 30.06. FD-01 (Notiz) · `SN-125` 02.07. FD-01 (Notiz) · `WA-089` 07.07. FD-01 (Wartung, inspection)

**Vorkommen 3 — 19.08.–21.08.2026, FD-02**

FD-02, rechtzeitig bemerkt: ein Pfeifen beim Anlauf, Taktzeit noch in Ordnung. Riemen nachgespannt, kein Schaden.

Einträge: `SN-177` 19.08. FD-02 (Notiz) · `WA-120` 21.08. FD-02 (Wartung, inspection)

**Woran die Wiederholung hängt.** Der Antrieb dreht, das Band folgt nicht. Einmal über die Presse erzählt, die wartet · einmal über die Differenz zwischen Anzeige und Menge · einmal nur über ein Geräusch, bevor überhaupt etwas messbar ist.

**Ablenker.** FD-01 im August: langsamer als am Vortag, weil ein anderes Rezept mit anderer Taktzeit geladen wurde.

Einträge: `SN-153` 04.08. FD-01 (Notiz)

---

## P1 — Innere Undichtigkeit im Hydraulikkreis, Druck bricht weg

**Maschinenklasse** `servo_press` · **Komponente** `hydraulic`

Dichtung, Schlauch oder Ventil im Druckkreis geben nach. Der Druckaufbau dauert länger, der Haltedruck fällt ab, am Ende steht die Presse.

**Vorkommen 1 — 05.03.–18.03.2026, PR-03**

PR-03, dreizehn Tage. Vollständige Spur: zwei Notizen, Warnung, kritischer Alarm, Prüfung. Befund: ausgeschlagene Stangendichtung.

Einträge: `SN-027` 05.03. PR-03 (Notiz) · `SN-032` 11.03. PR-03 (Notiz) · `AL-003` 13.03. PR-03 (Alarm, HYD_PRESS_LOW_WARN) · `AL-004` 18.03. PR-03 (Alarm, HYD_PRESS_LOW_CRIT) · `WA-028` 18.03. PR-03 (Wartung, inspection)

**Vorkommen 2 — 04.06.–05.06.2026, PR-02**

PR-02, ohne Vorlauf. Der kritische Alarm steht acht Minuten vor der Notiz. Befund: gerissene Hochdruckleitung.

Einträge: `AL-007` 04.06. PR-02 (Alarm, HYD_PRESS_LOW_CRIT) · `SN-096` 04.06. PR-02 (Notiz) · `WA-068` 05.06. PR-02 (Wartung, inspection)

**Vorkommen 3 — 14.07.–28.07.2026, PR-01**

PR-01, zwei Wochen, rechtzeitig geplant behoben. Nur die Warnung, kein kritischer Alarm. Befund: undichtes Rückschlagventil im Speicherkreis.

Einträge: `SN-132` 14.07. PR-01 (Notiz) · `SN-141` 21.07. PR-01 (Notiz) · `AL-011` 23.07. PR-01 (Alarm, HYD_PRESS_LOW_WARN) · `WA-100` 28.07. PR-01 (Wartung, inspection)

**Woran die Wiederholung hängt.** Druck, der nicht steht — als zäher Aufbau · als plötzlicher Verlust · als abfallender Haltedruck über Nacht.

**Ablenker.** PR-02 im Mai: meldet zu wenig Druck, die Presse fügt aber sauber. Der Drucksensor zeigt 14 bar zu wenig. Die Hydraulik wird ausdrücklich ohne Befund geprüft.

Einträge: `SN-075` 12.05. PR-02 (Notiz) · `WA-055` 13.05. PR-02 (Wartung, inspection)

---

## P2 — Wärmeabfuhr im Ölkreis gestört, Druck wird unruhig

**Maschinenklasse** `servo_press` · **Komponente** `hydraulic`

Kühler, Thermostat oder Kühlerlüfter arbeiten nicht. Das Öl wird zu warm, die Viskosität fällt, der Druck schwankt. Dichtungen sind in Ordnung, es geht kein Öl verloren.

**Vorkommen 1 — 08.04.–15.04.2026, PR-01**

PR-01, eine Woche. Tag-Nacht-Unterschied im Verhalten. Befund: zugesetzte Kühlerlamellen.

Einträge: `SN-052` 08.04. PR-01 (Notiz) · `SN-056` 10.04. PR-01 (Notiz) · `WA-042` 15.04. PR-01 (Wartung, inspection)

**Vorkommen 2 — 13.07.–17.07.2026, PR-03**

PR-03, vier Tage, mit Druckwarnung. Befund: Thermostatventil klemmt in Bypass-Stellung.

Einträge: `SN-131` 13.07. PR-03 (Notiz) · `AL-010` 15.07. PR-03 (Alarm, HYD_PRESS_LOW_WARN) · `WA-096` 17.07. PR-03 (Wartung, inspection)

**Vorkommen 3 — 04.08.–12.08.2026, PR-02**

PR-02, gut eine Woche, mit falscher Erstvermutung (Dichtung wie im Juni). Befund: Kühlerlüfter läuft nur auf halber Drehzahl.

Einträge: `SN-154` 04.08. PR-02 (Notiz) · `SN-159` 07.08. PR-02 (Notiz) · `WA-110` 12.08. PR-02 (Wartung, inspection)

**Woran die Wiederholung hängt.** Warmes Aggregat und unruhiger Druck ohne Ölverlust. Das ist der Gegenspieler zu P1 und der schwierigste Trennfall im Bestand: gleiche Maschinenklasse, gleiche Komponente, teils derselbe Alarmcode — andere Ursache, andere Abhilfe. Vorkommen 3 sagt den Unterschied selbst an: nichts undicht, Ölstand seit vier Wochen gleich, Tank warm.

**Ablenker.** PR-01 Ende Juli: warmes Öl an allen drei Pressen, 34 Grad draußen, Hallentor offen. Ein Umgebungseinfluss, keine Anlagenstörung.

Einträge: `SN-149` 30.07. PR-01 (Notiz)

---

## P3 — Verschleiß am Fügewerkzeug, Fügekraft läuft nach oben

**Maschinenklasse** `servo_press` · **Komponente** `tool`

Stempel und Matrize verschleißen über die Standmenge. Die Fügekraft steigt langsam, bis sie den Grenzwert reißt. Abhilfe ist der Werkzeugwechsel.

**Vorkommen 1 — 18.02.–03.03.2026, PR-02**

PR-02, knapp zwei Wochen. Notizen, Alarm, Wechsel. Befund: ausgebrochene Schneidkante.

Einträge: `SN-015` 18.02. PR-02 (Notiz) · `SN-021` 25.02. PR-02 (Notiz) · `AL-002` 02.03. PR-02 (Alarm, TOOL_LOAD_HIGH) · `WA-018` 03.03. PR-02 (Wartung, tool_change)

**Vorkommen 2 — 20.05.–03.06.2026, PR-01**

PR-01, zwei Wochen, planmäßig zur Standmenge gewechselt. Kein Alarm — der Vorgang wird bemerkt, bevor er eskaliert.

Einträge: `SN-083` 20.05. PR-01 (Notiz) · `SN-092` 01.06. PR-01 (Notiz) · `WA-067` 03.06. PR-01 (Wartung, tool_change)

**Vorkommen 3 — 05.08.–17.08.2026, PR-03**

PR-03, zwölf Tage, weil der Wechsel wegen eines Auftrags geschoben wurde. Läuft bis zum Alarm und bis in den Ausschuss. Befund: Stempelspitze und Matrizenkante ausgebrochen.

Einträge: `SN-155` 05.08. PR-03 (Notiz) · `AL-013` 14.08. PR-03 (Alarm, TOOL_LOAD_HIGH) · `SN-173` 14.08. PR-03 (Notiz) · `WA-114` 17.08. PR-03 (Wartung, tool_change)

**Woran die Wiederholung hängt.** Steigende Kraft am selben Teil über Wochen. Erzählt als steilere Kurve · als oberer Rand der Presskraft · als kletternde Kraft mit geschobenem Wechsel.

**Ablenker.** PR-01 im Juni: höhere Fügekraft bei drei Wochen altem Werkzeug. Die Prüfung findet das Werkzeug im Neuzustand und das Rohteilmaß 0,15 mm über Zeichnung. Ursache liegt in der Zuführung, nicht in der Presse.

Einträge: `SN-119` 26.06. PR-01 (Notiz) · `WA-085` 29.06. PR-01 (Wartung, inspection)

---

## P4 — Gleitbahnen des Ram-Antriebs ohne Schmierfilm, Hub läuft ungleichmäßig

**Maschinenklasse** `servo_press` · **Komponente** `ram_drive`

Die Zentralschmierung erreicht die Bahnen nicht. Der Ram stottert, hakt oder läuft unrund. Abhilfe ist Freimachen des Schmierwegs und Nachschmieren.

**Vorkommen 1 — 12.02.–19.02.2026, PR-01**

PR-01, eine Woche. Befund: verstopfte Schmierleitung zur unteren Bahn.

Einträge: `SN-009` 12.02. PR-01 (Notiz) · `SN-011` 16.02. PR-01 (Notiz) · `WA-009` 19.02. PR-01 (Wartung, lubrication)

**Vorkommen 2 — 04.05.–08.05.2026, PR-03**

PR-03, vier Tage. Befund: blockierter Dosierverteiler, zwei von vier Auslässen ohne Durchgang.

Einträge: `SN-067` 04.05. PR-03 (Notiz) · `SN-071` 07.05. PR-03 (Notiz) · `WA-053` 08.05. PR-03 (Wartung, lubrication)

**Vorkommen 3 — 10.07.–13.07.2026, PR-02**

PR-02, drei Tage, rechtzeitig: nur ein Geräusch, Kraft und Maß noch unauffällig. Intervall wurde verkürzt.

Einträge: `SN-130` 10.07. PR-02 (Notiz) · `WA-093` 13.07. PR-02 (Wartung, lubrication)

**Woran die Wiederholung hängt.** Ungleichmäßiger Hub an einer Presse, immer im selben Wegabschnitt, mit einem Schmierweg als Befund. Stottern · Haken · unrunder Lauf.

**Ablenker.** PR-03 im August: der Hub stoppt kurz, sieht aus wie Ruckeln — die Fahne des Endschalters hat sich gelöst und schaltet zwischendurch.

Einträge: `SN-167` 11.08. PR-03 (Notiz)

---

## P5 — Werkzeug sitzt nicht fest in der Aufnahme, Fügemaß wandert

**Maschinenklasse** `servo_press` · **Komponente** `tool`

Spannschrauben, Pratzen oder Anlagefläche geben nach. Das Fügemaß wandert oder wird einseitig. Der Verschleiß des Werkzeugs ist dabei unauffällig.

**Vorkommen 1 — 02.04.–07.04.2026, PR-03**

PR-03, fünf Tage. Befund: Spannschrauben unter Anzugsmoment, Auflagefläche mit Einschlagstellen.

Einträge: `SN-046` 02.04. PR-03 (Notiz) · `SN-048` 06.04. PR-03 (Notiz) · `WA-035` 07.04. PR-03 (Wartung, inspection)

**Vorkommen 2 — 24.06.–03.07.2026, PR-01**

PR-01, gut eine Woche, direkt nach einem Werkzeugwechsel. Befund: Werkzeug auf einem Span aufgesetzt.

Einträge: `SN-116` 24.06. PR-01 (Notiz) · `SN-124` 01.07. PR-01 (Notiz) · `WA-087` 03.07. PR-01 (Wartung, inspection)

**Vorkommen 3 — 18.08.–19.08.2026, PR-02**

PR-02, innerhalb eines Tages. Löst TOOL_LOAD_HIGH aus, obwohl das Werkzeug fast neu ist. Befund: zwei gelöste Spannpratzen.

Einträge: `SN-176` 18.08. PR-02 (Notiz) · `AL-014` 18.08. PR-02 (Alarm, TOOL_LOAD_HIGH) · `WA-117` 19.08. PR-02 (Wartung, inspection)

**Woran die Wiederholung hängt.** Das Maß wandert, das Werkzeug ist es nicht. Vorkommen 3 teilt sich den Alarmcode mit P3 und ist genau deshalb der interessante Fall: derselbe Alarm, andere Ursache. Der Hinweis steht in der Notiz — Werkzeug fast neu, es klappert im Oberteil.

**Ablenker.** PR-02 im April: die Fügemaße sind angeblich alle daneben, mit der zweiten Lehre gemessen passt alles. Das Prüfmittel war verstellt, die Presse in Ordnung.

Einträge: `SN-065` 27.04. PR-02 (Notiz)

---

## R1 — Spiel im Gelenklager Achse 1, Bestückposition wird ungenau

**Maschinenklasse** `robot` · **Komponente** `joint_bearing`

Das Gelenklager der ersten Achse bekommt Radialspiel. Der Roboter greift oder setzt daneben, am deutlichsten bei ausgestrecktem Arm.

**Vorkommen 1 — 04.03.–13.03.2026, RB-01**

RB-01, gut eine Woche. Befund: Radialspiel 0,25 mm gegen 0,08 mm Grenzwert. Lagerung wird zum Tausch angemeldet.

Einträge: `SN-026` 04.03. RB-01 (Notiz) · `SN-030` 09.03. RB-01 (Notiz) · `WA-024` 13.03. RB-01 (Wartung, inspection)

**Vorkommen 2 — 10.06.–19.06.2026, RB-02**

RB-02 (Reserve), gut eine Woche. Lange nicht bemerkt, weil die Maschine selten läuft — das steht so in der Notiz. Befund: Spiel und verbrauchtes Fett, nach Nachstellen wieder im Fenster.

Einträge: `SN-103` 10.06. RB-02 (Notiz) · `SN-109` 16.06. RB-02 (Notiz) · `WA-080` 19.06. RB-02 (Wartung, inspection)

**Vorkommen 3 — 11.08.–20.08.2026, RB-01**

RB-01, neun Tage, ohne Auflösung. Die Notiz vom 11.08. stellt selbst fest, dass das im März angemeldete Lager nie getauscht wurde. Der Vorgang ist am Ende der Historie offen.

Einträge: `SN-165` 11.08. RB-01 (Notiz) · `SN-180` 20.08. RB-01 (Notiz)

**Woran die Wiederholung hängt.** Ungenaue Bestückung mit sichtbarem oder messbarem Spiel im Fuß der ersten Achse. Nachgreifen · Fehlgriffe · Streuung in der Wiederholgenauigkeit. Vorkommen 1 und 3 hängen ausdrücklich zusammen — das ist im Bestand die einzige Stelle, an der ein Verfasser die Wiederholung selbst benennt.

**Ablenker.** RB-01 im Mai: greift daneben an Station 3, weil der Werkstückträger dort nicht einrastet. Gleiche Maschine, gleiches Symptom, Ursache außerhalb des Roboters.

Einträge: `SN-084` 20.05. RB-01 (Notiz)

---

## R2 — Ölverlust am Getriebe, Getriebe wird laut

**Maschinenklasse** `robot` · **Komponente** `gearbox`

Dichtring oder Flansch am Getriebe werden undicht, der Ölstand fällt, das Getriebe wird lauter.

**Vorkommen 1 — 16.04.–23.04.2026, RB-01**

RB-01, eine Woche. Befund: undichter Radialwellendichtring, Dichtring erneuert.

Einträge: `SN-059` 16.04. RB-01 (Notiz) · `SN-062` 21.04. RB-01 (Notiz) · `WA-048` 23.04. RB-01 (Wartung, inspection)

**Vorkommen 2 — 16.07.–24.07.2026, RB-02**

RB-02, gut eine Woche. Befund: dunkles Öl mit metallischem Abrieb, Magnetstopfen belegt. Ölwechsel, Probe zur Analyse, verkürztes Intervall.

Einträge: `SN-135` 16.07. RB-02 (Notiz) · `SN-142` 21.07. RB-02 (Notiz) · `WA-098` 24.07. RB-02 (Wartung, inspection)

**Vorkommen 3 — 24.08.–25.08.2026, RB-01**

RB-01, zwei Einträge. Der Wartungseintrag steht diesmal VOR der Notiz — die Regelprüfung findet den niedrigen Ölstand, der Werker wundert sich am Folgetag darüber. Ohne Auflösung.

Einträge: `WA-122` 24.08. RB-01 (Wartung, inspection) · `SN-183` 25.08. RB-01 (Notiz)

**Woran die Wiederholung hängt.** Öl geht weg und das Getriebe wird lauter. Erzählt über Tropfen am Boden · über den Klangvergleich mit der Schwestermaschine · über das Schauglas.

**Ablenker.** RB-02 im Juni: Öl unter dem Roboter, es läuft aber von der Presse herüber, das Blech hat Gefälle.

Einträge: `SN-097` 05.06. RB-02 (Notiz)

---

## R3 — Getriebespiel nach gehäuften Not-Halt-Bremsungen

**Maschinenklasse** `robot` · **Komponente** `gearbox`

Mehrere harte Bremsungen kurz hintereinander belasten die Verzahnung. Danach fährt der Roboter ruppig an, das Verdrehflankenspiel steigt.

**Vorkommen 1 — 05.02.–13.02.2026, RB-01**

RB-01 im Februar, acht Tage. Die Prüfung findet KEINEN Befund — kein Mehrspiel, Verzahnung in Ordnung, keine Maßnahme. Symptom und Vorgeschichte sind trotzdem dieselben wie bei den anderen beiden Vorkommen.

Einträge: `SN-003` 05.02. RB-01 (Notiz) · `SN-007` 10.02. RB-01 (Notiz) · `WA-008` 13.02. RB-01 (Wartung, inspection)

**Vorkommen 2 — 05.05.–15.05.2026, RB-01**

RB-01 im Mai, zehn Tage. Befund: Verdrehflankenspiel 12 gegen 6 Bogenminuten, Getriebe zum Austausch angemeldet.

Einträge: `SN-069` 05.05. RB-01 (Notiz) · `SN-074` 12.05. RB-01 (Notiz) · `WA-058` 15.05. RB-01 (Wartung, inspection)

**Vorkommen 3 — 29.07.–06.08.2026, RB-02**

RB-02, acht Tage. Befund: erhöhtes Spiel und Pittings an den Flanken, Beschleunigungsrampe halbiert.

Einträge: `SN-148` 29.07. RB-02 (Notiz) · `SN-151` 03.08. RB-02 (Notiz) · `WA-105` 06.08. RB-02 (Wartung, inspection)

**Woran die Wiederholung hängt.** Immer dieselbe Vorgeschichte: mehrere Not-Halt-Bremsungen, danach ein harter Anlauf oder Nachschwingen. Vorkommen 1 ist bewusst der Fall ohne Befund — wer nur nach bestätigten Schäden sucht, findet ihn nicht, und trotzdem gehört er in die Antwort auf die Frage, ob es das schon einmal gab.

**Ablenker.** RB-02 Ende August: fährt hart an, weil ein neues Programm eine steilere Rampe hat. Keine Not-Halt-Vorgeschichte, mechanisch alles fest.

Einträge: `SN-184` 25.08. RB-02 (Notiz)

---

## S1 — Lichtleistung der Beleuchtungseinheit fällt ab, Ausschuss steigt

**Maschinenklasse** `vision` · **Komponente** `lighting`

Die Beleuchtung der Prüfstation verliert Leistung oder leuchtet ungleichmäßig aus. Die Kamera ist in Ordnung, die Teile sind in Ordnung, die Prüfung weist trotzdem ab.

**Vorkommen 1 — 19.03.–24.03.2026, VS-01**

Fünf Tage, mit Ausschussalarm. Befund: Lichtleistung bei 62 Prozent des Neuwerts, LED-Ring getauscht.

Einträge: `SN-038` 19.03. VS-01 (Notiz) · `AL-005` 23.03. VS-01 (Alarm, REJECT_RATE_HIGH) · `WA-032` 24.03. VS-01 (Wartung, inspection)

**Vorkommen 2 — 11.06.–18.06.2026, VS-01**

Eine Woche. Befund: ein Segment des LED-Rings ohne Funktion, Treiberkanal defekt. Auffällig war eine einzelne Nesterposition.

Einträge: `SN-104` 11.06. VS-01 (Notiz) · `SN-107` 15.06. VS-01 (Notiz) · `WA-077` 18.06. VS-01 (Wartung, inspection)

**Vorkommen 3 — 13.08.–18.08.2026, VS-01**

Fünf Tage, mit Ausschussalarm und falscher Erstvermutung (Kamera). Befund: vergilbte Diffusorscheibe.

Einträge: `SN-170` 13.08. VS-01 (Notiz) · `AL-012` 14.08. VS-01 (Alarm, REJECT_RATE_HIGH) · `WA-116` 18.08. VS-01 (Wartung, inspection)

**Woran die Wiederholung hängt.** Steigender Ausschuss bei unauffälligen Teilen, das Bild ist zu dunkel oder ungleich ausgeleuchtet. Flau · Schatten in einer Ecke · zu dunkles Prüfteil.

**Ablenker.** VS-01 im Juli: mehr Ausschuss ab Mittag, weil die Sonne durchs offene Tor auf die Prüfstation fällt. Ein Lichtproblem — aber keines der Beleuchtungseinheit.

Einträge: `SN-144` 22.07. VS-01 (Notiz)

---

## S2 — Sicht der Inspektionskamera verlegt, Prüfung wird unzuverlässig

**Maschinenklasse** `vision` · **Komponente** `camera`

Linse, Schutzscheibe oder Gehäuse der Kamera sind verschmutzt, beschlagen oder belegt. Die Beleuchtung ist in Ordnung.

**Vorkommen 1 — 06.02.2026, VS-01**

Ein halber Tag. Befund: Öl-Sprühnebel auf der Frontlinse, danach Schutzscheibe montiert.

Einträge: `SN-004` 06.02. VS-01 (Notiz) · `WA-003` 06.02. VS-01 (Wartung, inspection)

**Vorkommen 2 — 18.05.–26.05.2026, VS-01**

Gut eine Woche, mit tageszeitlichem Muster (morgens milchig, später normal). Befund: Kondensat hinter der Schutzscheibe, spröde Gehäusedichtung.

Einträge: `SN-080` 18.05. VS-01 (Notiz) · `SN-085` 21.05. VS-01 (Notiz) · `WA-064` 26.05. VS-01 (Wartung, inspection)

**Vorkommen 3 — 09.07.–10.07.2026, VS-01**

Ein Tag, mit Ausschussalarm. Befund: Abrieb aus der Fügestation auf der Scheibe, Absaugung an PR-02 wirkungslos.

Einträge: `SN-129` 09.07. VS-01 (Notiz) · `AL-009` 09.07. VS-01 (Alarm, REJECT_RATE_HIGH) · `WA-092` 10.07. VS-01 (Wartung, inspection)

**Woran die Wiederholung hängt.** Das Bild stimmt nicht, und der Grund sitzt vor dem Sensor. Fleck an derselben Stelle · milchig und unscharf · Staubschicht auf der Scheibe. Trennfall zu S1: dort ist es zu dunkel, hier ist die Sicht verlegt.

**Ablenker.** VS-01 Ende Juni: Bild dunkel, Scheibe aber sauber — am Vorabend wurde die Belichtung im Prüfprogramm geändert.

Einträge: `SN-121` 30.06. VS-01 (Notiz)

---

## S3 — Endkontrolle schlägt aus, die Ursache liegt vor ihr in der Linie

**Maschinenklasse** `vision` · **Komponente** `camera`

Die Ausschussquote steigt, weil die Teile tatsächlich schlecht sind. Kamera und Beleuchtung sind in Ordnung. Die Ursache steht weiter vorne in der Linie und ändert sich von Fall zu Fall.

**Vorkommen 1 — 09.04.–13.04.2026, PR-02, VS-01**

Ursache PR-02, gebrochene Niederhalterfeder. Der Wartungseintrag steht deshalb auf der Presse, nicht auf der Endkontrolle.

Einträge: `SN-054` 09.04. VS-01 (Notiz) · `SN-055` 10.04. VS-01 (Notiz) · `WA-039` 13.04. PR-02 (Wartung, inspection)

**Vorkommen 2 — 23.06.–24.06.2026, VS-01**

Ursache FD-01, fehlender Nachschub. Mit Ausschussalarm, ohne Wartungseintrag.

Einträge: `SN-114` 23.06. VS-01 (Notiz) · `SN-115` 24.06. VS-01 (Notiz) · `AL-008` 24.06. VS-01 (Alarm, REJECT_RATE_HIGH)

**Vorkommen 3 — 20.08.–21.08.2026, VS-01**

Ursache AX-03, schiefes Einlegen. Zwei Notizen, keine Wartung, offen am Ende der Historie.

Einträge: `SN-179` 20.08. VS-01 (Notiz) · `SN-181` 21.08. VS-01 (Notiz)

**Woran die Wiederholung hängt.** Immer dasselbe Urteil aus zwei Sätzen: an der Prüfstation ist nichts falsch, das Problem kommt von vorne. Die verursachende Maschine ist jedes Mal eine andere — deshalb ist dieser Typ nur über den Sinn zu finden, nie über eine Maschinenkennung. Zugleich der wichtigste Kreuzfall: die Vorgänge gehören inhaltlich zu F2, P5 und V2 an der jeweils verursachenden Maschine.

**Ablenker.** VS-01 Ende März: Ausschuss doppelt so hoch, an der Linie ist nichts anders — die Prüfgrenze für den Sitz wurde enger gesetzt. Die Zahl steigt, ohne dass sich ein Teil geändert hat.

Einträge: `SN-045` 31.03. VS-01 (Notiz)

---

## Übersicht

| Typ | Fehlertyp | Maschinen | Vorkommen beginnen am | Einträge | Ablenker |
|---|---|---|---|---|---|
| V1 | Lagerschaden am Linearführungslager einer Handling-Achse | AX-01, AX-02, AX-03 | 09.02., 12.05., 20.07. | 13 | 2 |
| V2 | Spiel im Kugelgewindetrieb, Positionsabweichung beim Richtungswechsel | AX-01, AX-02, AX-04 | 03.03., 25.05., 05.08. | 10 | 1 |
| V3 | Haltebremse am Servomotor schleift oder löst verzögert | AX-01, AX-03, AX-04 | 24.02., 15.06., 11.08. | 9 | 2 |
| V4 | Falscher Schmierstoff bei der Nachschmierung, Führung läuft nicht frei | AX-02, AX-03, AX-04 | 11.02., 19.05., 08.07. | 12 | 2 |
| V5 | Geberrückführung am Motor gestört, sporadische Schleppfehler | AX-01, AX-02, AX-04 | 17.03., 18.06., 06.08. | 9 | 2 |
| V6 | Lagerbock der Spindel gelockert, Schlag am Umkehrpunkt | AX-01, AX-03, AX-04 | 07.04., 29.06., 18.08. | 8 | 1 |
| F1 | Klemmzylinder am Dosiertrichter schaltet verzögert | FD-01, FD-02 | 17.02., 06.05., 10.08. | 9 | 1 |
| F2 | Brückenbildung im Dosiertrichter, Zuführung setzt aus | FD-01, FD-02 | 10.03., 08.06., 06.08. | 9 | 1 |
| F3 | Kraftschluss im Förderantrieb geht verloren, Zuführung bleibt hinter dem Takt | FD-01, FD-02 | 14.04., 30.06., 19.08. | 8 | 1 |
| P1 | Innere Undichtigkeit im Hydraulikkreis, Druck bricht weg | PR-01, PR-02, PR-03 | 05.03., 04.06., 14.07. | 12 | 2 |
| P2 | Wärmeabfuhr im Ölkreis gestört, Druck wird unruhig | PR-01, PR-02, PR-03 | 08.04., 13.07., 04.08. | 9 | 1 |
| P3 | Verschleiß am Fügewerkzeug, Fügekraft läuft nach oben | PR-01, PR-02, PR-03 | 18.02., 20.05., 05.08. | 11 | 2 |
| P4 | Gleitbahnen des Ram-Antriebs ohne Schmierfilm, Hub läuft ungleichmäßig | PR-01, PR-02, PR-03 | 12.02., 04.05., 10.07. | 8 | 1 |
| P5 | Werkzeug sitzt nicht fest in der Aufnahme, Fügemaß wandert | PR-01, PR-02, PR-03 | 02.04., 24.06., 18.08. | 9 | 1 |
| R1 | Spiel im Gelenklager Achse 1, Bestückposition wird ungenau | RB-01, RB-02 | 04.03., 10.06., 11.08. | 8 | 1 |
| R2 | Ölverlust am Getriebe, Getriebe wird laut | RB-01, RB-02 | 16.04., 16.07., 24.08. | 8 | 1 |
| R3 | Getriebespiel nach gehäuften Not-Halt-Bremsungen | RB-01, RB-02 | 05.02., 05.05., 29.07. | 9 | 1 |
| S1 | Lichtleistung der Beleuchtungseinheit fällt ab, Ausschuss steigt | VS-01 | 19.03., 11.06., 13.08. | 9 | 1 |
| S2 | Sicht der Inspektionskamera verlegt, Prüfung wird unzuverlässig | VS-01 | 06.02., 18.05., 09.07. | 8 | 1 |
| S3 | Endkontrolle schlägt aus, die Ursache liegt vor ihr in der Linie | PR-02, VS-01 | 09.04., 23.06., 20.08. | 8 | 1 |

## Was sonst im Bestand liegt

Von 327 Einträgen gehören 186 zu einem der zwanzig Vorgangstypen und 26 zu einem Ablenker. Die übrigen 115 sind Regelwartung, Notizen ohne Befund, Betriebsalltag und offene Kleinigkeiten. Sie tragen keine Wiederholung und sind als Grundrauschen gedacht, gegen das sich ein Treffer behaupten muss.

Drei Vorgänge enden ohne Auflösung und sind so gewollt: V3 Vorkommen 3 (AX-04, kein Wartungseintrag), V5 Vorkommen 3 (AX-01, Fehler bleibt aus) und R1 Vorkommen 3 (RB-01, das im März angemeldete Lager wurde nie getauscht). R3 Vorkommen 1 hat einen Wartungseintrag mit dem Ergebnis *ohne Befund* — Symptom und Vorgeschichte stimmen trotzdem mit den anderen beiden Vorkommen überein.

An einer Stelle widersprechen sich zwei Schichten offen (PR-01 am 26./27.03.: die eine hört ein Geräusch, die andere nicht), an mehreren Stellen steht eine Vermutung, die sich später als falsch herausstellt (V1 Vorkommen 3, V3 Vorkommen 1, V4 Vorkommen 3, P2 Vorkommen 3, S1 Vorkommen 3).

## Wie sich die Wortgleichheit prüfen lässt

Die Forderung war, dass zwei Vorkommen desselben Vorgangstyps sich nicht über gleiche Wörter finden lassen. Das ist an den Schichtnotizen nachgerechnet: je Vorkommen die Menge der Wörter ab vier Zeichen ohne Funktionswörter, dann der Jaccard-Wert je Paar von Vorkommen. In eckigen Klammern stehen die tatsächlich geteilten Wörter.

| Typ | Vorkommen 1/2 | Vorkommen 1/3 | Vorkommen 2/3 |
|---|---|---|---|
| V1 | 0.00 [–] | 0.00 [–] | 0.00 [–] |
| V2 | 0.03 [teile] | 0.00 [–] | 0.00 [–] |
| V3 | 0.03 [motor] | 0.03 [gleichem] | 0.00 [–] |
| V4 | 0.00 [–] | 0.00 [–] | 0.00 [–] |
| V5 | 0.03 [zweimal] | 0.03 [zweimal] | 0.08 [nacht, zweimal] |
| V6 | 0.04 [spürt] | 0.00 [–] | 0.00 [–] |
| F1 | 0.00 [–] | 0.00 [–] | 0.00 [–] |
| F2 | 0.00 [–] | 0.05 [trichter] | 0.04 [leer] |
| F3 | 0.04 [sollwert] | 0.00 [–] | 0.00 [–] |
| P1 | 0.05 [druck] | 0.08 [aggregat, druck] | 0.10 [druck, nacht] |
| P2 | 0.05 [druck] | 0.07 [druck, schwankt] | 0.09 [druck, tank] |
| P3 | 0.09 [kraft, teile] | 0.04 [kraft] | 0.03 [kraft] |
| P4 | 0.00 [–] | 0.00 [–] | 0.00 [–] |
| P5 | 0.04 [werkzeug] | 0.05 [werkzeug] | 0.06 [werkzeug] |
| R1 | 0.00 [–] | 0.04 [teile] | 0.04 [daneben] |
| R2 | 0.00 [–] | 0.08 [getriebe] | 0.00 [–] |
| R3 | 0.03 [gestoppt] | 0.00 [–] | 0.06 [fährt, vorher] |
| S1 | 0.07 [teile] | 0.08 [teile] | 0.06 [teile] |
| S2 | 0.04 [bild] | 0.00 [–] | 0.00 [–] |
| S3 | 0.06 [ausschuss, teile] | 0.04 [teile] | 0.07 [endkontrolle, teile] |

Was übrig bleibt, sind Wörter des Fachgebiets, die im gesamten Bestand vorkommen und deshalb keine Brücke bilden: *Druck* steht in 22 Einträgen, *Kraft* in 16, *Teile* in 28. Ein Stichwort, das nur die drei Vorkommen eines Typs verbindet, gibt es in keinem der zwanzig Fälle. Die Maschinenkennung verbindet ebenfalls nicht, weil die Vorkommen bewusst auf Schwestermaschinen verteilt sind — die einzige Ausnahme ist die Endkontrolle VS-01, die es nur einmal gibt.
