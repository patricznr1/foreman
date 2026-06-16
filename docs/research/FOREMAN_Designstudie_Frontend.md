# FOREMAN — Designstudie & Designkonzept Frontend-Plattform

**Industrielle Production-Intelligence-Plattform auf Industrie-6.0-Niveau**
Strategische, konzeptionelle und operative Grundlage für Entwicklung, Stakeholder-Kommunikation und Implementierung.

Stand: 16.06.2026 · Bezug: GROUND_TRUTH (foreman repo) · Sprintbezug: konzeptionelle Grundlage für F5 (Dashboard) und den Plattform-Ausbau · Status: Designgrundlage (Arbeitsstand).

---

## 0. Wie diese Studie zu lesen ist

Diese Studie übersetzt den Projektrahmen nicht in eine Wiederholung, sondern in Entscheidungen. Sie ist so geschrieben, dass ein UI-Designer, ein Frontend-Entwickler und ein Stakeholder jeweils ihren Einstieg finden: Sektion 1–2 trägt die Haltung, Sektion 3 die Architektur, Sektion 4 die zehn Sichten im Detail, Sektion 5 das gebaute System aus Technologie, Farbe, Typografie, Komponenten und Bewegung.

Drei Begriffe ziehen sich als roter Faden durch:

- **Zustand zeigen** — Sichten, die einen Ist-Zustand permanent und live darstellen (Cockpit, Detail, Alarme). Sie sind ambient, drängen sich nicht auf, blockieren nie.
- **Erkenntnis erzeugen** — Aktionen, die eine Analyse anstoßen, deren Ergebnis abgerufen und dann gezeigt wird (Ereignisketten, Ausfallvorhersage, Wartungskausalität, Belastungs-Simulation, semantische Suche). Sie haben einen klaren Auslöser, einen Verarbeitungszustand und ein Ergebnis mit Herkunftsstempel.
- **Drei bleibende Haltungen** — keine Ausbaustufe, sondern Verfassung: (1) der **Simulations-Vorbehalt** an jeder Ausfallvorhersage ist immer sichtbar; (2) **Human-in-the-Loop statt Aktorik** — die Plattform erklärt und empfiehlt, sie schaltet nie; (3) das **Gedächtnis nach außen ist immer paraphrasiert** — kein internes Vokabular im sichtbaren Wording.

Wo im Frontend Erkenntnisse aus der dahinterliegenden Gedächtnis- und Analyseschicht auftauchen, werden sie in Werker-Sprache benannt. Die Studie hält diese Disziplin selbst ein: sie spricht von „Einflussfaktoren", „ähnlichen Fällen", „Abweichung gegen das eigene Profil" — nicht von den darunterliegenden Verfahren. Die technischen Verfahren stehen in Sektion 5 dort, wo sie die Entwicklung betreffen, nicht im Bedien-Wording.

---

## 1. Design-Research-Fundament

### 1.1 Normen- und Standardslandschaft — Bewertung und Synthese

Die Plattform steht an einer Stelle, an der drei Normwelten zusammenlaufen, die historisch wenig miteinander gesprochen haben: die **Web-Frontend-Welt** (HTML5, CSS, JavaScript, die Framework-Familien, WebGL, WebSockets), die **HMI-/Automations-Welt** (ISA-101, ISA-18.2, NAMUR NE 107) und die **Barrierefreiheits- und Security-Welt** (WCAG 2.2, Security by Design / OWASP). Der eigentliche Designanspruch liegt nicht darin, eine davon zu erfüllen, sondern ihre Reibungen aufzulösen.

**Die Frameworks — was wofür, mit Trade-off.**

Die Stack-Grundsatzentscheidung ist projektseitig bereits gefallen und soll es bleiben: **React über Next.js**, TypeScript strict, Tailwind, eine kuratierte Komponentenbasis, eine spezialisierte Charting-Bibliothek für Sensorzeitreihen. Das ist keine Modeentscheidung, sondern folgt aus dem Lastprofil dieser Plattform. Die offene „React vs. Angular"-Frage beantworte ich in Sektion 5.1 ausführlich; hier nur die Einordnung der Optionen aus dem Rahmen:

- **React** ist für FOREMAN die tragende Wahl, weil die Plattform aus vielen heterogenen, zustandsbehafteten Echtzeit-Sichten besteht, die unterschiedlich schnell atmen (Sensor-Stream im Sekundentakt neben einer statischen Stammdaten-Karte). Reacts feinkörniges Komponentenmodell und die reife Ökosystem-Abdeckung für Streaming-State und Virtualisierung passen exakt darauf. Trade-off: ohne Disziplin zerfasert die Architektur — deshalb die strikte Trennung Visualisierung/Datenlogik in 5.1.
- **Angular** wäre dort stärker, wo eine einzige große, formularlastige Linienanwendung mit erzwungener Struktur gebaut wird; sein Opinionated-Charakter nimmt Team-Varianz heraus. Für FOREMANs Vielzahl kleiner, schnell iterierter Spezialsichten ist diese Schwere ein Nachteil, nicht ein Vorteil.
- **Vue/Svelte** sind technisch tauglich und im Bundle leichter (relevant für Schwachnetz), verlieren aber gegen Reacts Ökosystem bei genau den Spezialteilen, die FOREMAN braucht: virtualisierte Tabellen mit zehntausenden Alarmzeilen, WebGL-Bridges, robuste Offline-Sync-Bibliotheken.
- **Electron** ist kein Web-Framework, sondern eine Verpackung; sein Platz ist eng umrissen (Leitstand-Kiosk, Service-Laptop mit Offline-Anspruch) und in 5.1 begründet. Pauschal eingesetzt wäre es Ballast.
- **WebGL/Three.js** ist kein Default, sondern ein Werkzeug für genau zwei Stellen: die Flotten-/Drift-Heatmap über viele Maschinen (A) und die Belastungs-Simulation (G). Überall sonst ist DOM/SVG/Canvas-Charting die robustere, barriereärmere und wartbarere Wahl.

**Die HMI-Normen — der eigentliche Charakterträger.**

Der entscheidende Hebel ist nicht Web-Technik, sondern die **High-Performance-HMI-Philosophie nach ISA-101**, die 2024/2025 als **IEC 63303** international übernommen wurde. Ihr Kern widerspricht direkt dem, was „modernes KI-Webdesign" produziert: nicht mehr Farbe, mehr Tiefe, mehr Bewegung — sondern eine **entsättigte, ruhige Grundfläche, auf der Farbe ein knappes, bedeutungstragendes Ereignis ist**. Eine Anlage im Normalbetrieb darf nicht bunt sein; Farbe erscheint, wenn etwas vom Normalen abweicht. ISA-101 trägt außerdem einen Lifecycle-Gedanken (Philosophie → Style Guide → Toolset → Betrieb → Pflege), den diese Studie spiegelt: das Design-System in Sektion 5 ist der Style Guide, nicht eine einmalige Skin.

Die **Alarm-Norm ISA-18.2 (2016) / IEC 62682** liefert das zweite Fundament und kollidiert produktiv mit der naiven Erwartung „alles Wichtige rot". Ihr Beitrag ist die **Rationalisierung**: jeder Alarm hat eine begründete Priorität, eine erwartete Bedienhandlung und eine Konsequenz; Prioritäten sind gestuft (kritisch/hoch/mittel/niedrig plus Journal-/Diagnose-Ebene), nicht binär. Daraus folgt direkt das Eskalations- und Farbmodell in Sektion 4C — und die harte Regel, dass eine Sicht, in der dauerhaft die Hälfte rot leuchtet, ein Normverstoß ist, kein Designgeschmack.

**NAMUR NE 107** ergänzt das um ein Vokabular, das im Feld bereits gelernt ist: die vier Statussignale **Failure (F), Function check (C), Out of specification (S), Maintenance required (M)** — „FCSM". Dieses Schema ist Gold wert, weil Techniker und Werker es von ihren Feldgeräten kennen. FOREMAN übernimmt es als kanonisches Zustandsmodell für Maschinenstatus (4B, 4C) statt ein eigenes zu erfinden. Hier verstärken sich die Standards: NE 107 liefert die Zustandsklassen, ISA-18.2 die Priorisierung der daraus entstehenden Alarme, ISA-101 die ruhige Darstellung.

**Wo Standards kollidieren — und wie aufgelöst.**

- **Webdesign-Konvention vs. ISA-101.** Web-Komponentenbibliotheken sind auf helle Flächen, Markenfarben und großzügige Farbigkeit getrimmt. ISA-101 verlangt das Gegenteil. Auflösung: die Komponentenbasis wird auf ein industrielles, entsättigtes Token-Set umgestellt (Sektion 5.2); die Farbigkeit der Standard-Themes wird aktiv entfernt, nicht ergänzt.
- **„Mehr Information ist besser" vs. Alarm-Rationalisierung.** Dashboards neigen zur Anhäufung. ISA-18.2 verlangt Reduktion auf das Handlungsrelevante. Auflösung: Informationshierarchie als Prinzip 1, mit messbarer Regel (Sektion 2).
- **WCAG-Mindestkontrast vs. Hallenrealität.** WCAG 2.2 fordert 4.5:1 für Text, 3:1 für große Schrift und für grafische/Bedien-Elemente (SC 1.4.11), und mit SC 2.5.8 ein Mindest-Touch-Ziel von 24×24 CSS-Pixeln. Das ist ein **Büro-Minimum**, kein Hallen-Maß. Auflösung: FOREMAN setzt die Messlatte härter — ≥7:1 für primären Status-Text wegen Distanz und Streulicht, Touch-Ziele weit über dem WCAG-Minimum (Sektion 1.2, 5). Hier verstärkt WCAG die HMI-Anforderung, kollidiert aber mit ihr im Niveau — FOREMAN nimmt jeweils den strengeren Wert.

**Security by Design in HMI/ISA.**

Security ist hier kein nachgelagertes Audit, sondern formt die Interaktion. Drei Einbindungen:

1. **Human-in-the-Loop als Sicherheits- und Designprinzip zugleich.** Die Plattform schaltet nie eine Aktorik; sie erklärt und empfiehlt. Das ist die wirksamste Angriffsflächen-Reduktion (keine Schreibpfade in die Anlage) und gleichzeitig die Haltung, die das ganze Interaktionsmodell trägt: jede Erkenntnis endet bei einem Menschen, der quittiert oder verwirft.
2. **Tool-/Modell-Ausgaben sind Daten, nie Instruktionen.** Was aus der Analyse- und Gedächtnisschicht ins Frontend kommt, wird als Inhalt dargestellt, nie als ausführbare Anweisung — sichtbar gemacht durch konsequente Herkunftsstempel und durch die Trennung „belegt durch Quelle" vs. „Freitext-Erzählung" (4D, 4E).
3. **Transparenzpflicht (AI-Act).** KI-generierter Inhalt im Frontend ist als solcher kenntlich. Das ist nicht nur Compliance, sondern Designelement: der Herkunftsstempel an jeder erzeugten Erkenntnis ist gleichzeitig die AI-Act-Transparenz und der Vertrauensanker.

### 1.2 Kontextanalyse — Designimplikationen

Jede physische, geräte- und netzbezogene Randbedingung wird hier in eine prüfbare Designregel übersetzt. „Prüfbar" heißt: ein Reviewer kann am fertigen Screen Ja/Nein sagen.

**Physische Umgebung.**

- **Handschuh-Bedienung** → kapazitive Touch-Genauigkeit sinkt, die effektive Fingerfläche wächst. WCAG-Minimum 24×24 px und das Material-Komfortmaß 48×48 dp reichen nicht. **Regel: primäre Touch-Ziele ≥ 56×56 px, sicherheitsrelevante Aktionen (Quittieren, Simulation auslösen) ≥ 64×64 px, Mindestabstand zwischen Zielen ≥ 12 px.** Begründung: Handschuh + Bewegung + Vibration erzeugen Ziel-Streuung, die nur durch Größe und Abstand, nicht durch Präzision aufgefangen wird.
- **Abstand zum Display (Leitstand, ≥ 1–3 m)** → Lesbarkeit ist eine Funktion von Winkelgröße, nicht Pixelgröße. **Regel: Körpertext am Leitstand ≥ 18 px, primäre KPI-Zahlen 48–72 px, Statusfarbflächen so dimensioniert, dass sie auf 3 m als Fläche, nicht als Punkt erkennbar sind (≥ 32 px Kantenlänge).**
- **Schlechte Lichtverhältnisse / wechselndes Licht** → Halle ist oft dunkel, aber Fensternähe und Stirnlampen erzeugen Streulicht und Reflexe. **Regel: Dark-Theme als Primärmodus mit Kontrast ≥ 7:1 für Status-Text; ein echtes High-Contrast-Light-Theme für Streulicht-Arbeitsplätze; keine reine Farbcodierung ohne zweiten Kanal (Form/Position/Label), weil Reflexe Farbe verfälschen.**
- **Hallenartige, laute Umgebung** → akustische Signale tragen nicht zuverlässig. **Regel: jeder kritische Zustand hat einen visuellen Hauptkanal (Position oben, Fläche, Bewegungs-Puls); Akustik ist additiv, nie Alleinträger.**

**Geräte.**

- **Leitstand-Monitore (groß, fix, Distanz)** → Platz für Übersicht und Dichte, aber Bedienung selten direkt am Schirm. **Regel: Leitstand-Layouts sind primär lese-/maus-/tastatur-optimiert, 12-Spalten-Raster, KPI-Kacheln und Trends im oberen Drittel, Alarmleiste persistent.**
- **Tablets (Schichtleiter, mobil in der Halle)** → Touch, mittlere Distanz, Handschuh. **Regel: Tablet-Layouts priorisieren Quittier- und Trigger-Aktionen mit großen Zielen, reduzierte Spaltenzahl (≤ 6), Daumen-Reichweiten-Zonen unten.**
- **Service-Laptops (Techniker, Diagnose)** → Tastatur, hohe Dichte erwünscht, aber oft schlechtes Netz. **Regel: dichteste Variante erlaubt, aber jede Sicht muss mit gecachten Daten und sichtbarem Offline-Stempel funktionieren.**
- **Mobilgeräte (Techniker im Feld, einhändig)** → kleinster Schirm, Handschuh, Einhand. **Regel: Einhand-Layout, kritische Aktionen im unteren Daumenbogen, eine Hauptaktion pro Screen, Schnellzugriff statt Navigationstiefe.**

**Netzwerk.**

- **Offline-Toleranz** → Verbindung darf jederzeit wegbrechen. **Regel: jede Sicht deklariert ihren Datenstand sichtbar („live" / „gecacht, Stand 10:42") und degradiert kontrolliert statt leer zu werden; Werker-Erfassung (J) schreibt lokal und synchronisiert nachträglich.**
- **Schwachnetz** → hohe Latenz, niedrige Bandbreite. **Regel: Live-Streams sind drosselbar (Push-Rate adaptiv), schwere Visualisierungen (Heatmap, Simulation) laden progressiv und sind abschaltbar; Erstbild < 100 KB kritischer Pfad.**

**Die drei kritischsten UX-Anforderungen je Rolle** (abgeleitet aus Zeitdruck, Verantwortung, Einsatzart, Reporting):

- **Werker** (erfassen, lesen, suchen):
  1. Erfassen ohne Reibung — eine Notiz an die richtige Maschine/Schicht in unter 15 Sekunden, ohne durch Navigation zu suchen.
  2. Lesen auf einen Blick — „ist meine Maschine ok?" muss ohne Interpretation beantwortet sein.
  3. Wiederfinden — „hatten wir das schon mal?" als greifbare Suche, nicht als Datenbankfrage.
- **Schichtleiter** (quittieren, Erkenntnis triggern):
  1. Priorisierte Entscheidung — Alarme nach echter Dringlichkeit gestaffelt, nicht als Flut, damit Quittieren eine Entscheidung bleibt und kein Reflex wird.
  2. Verantwortbares Quittieren — Quittieren ist nachvollziehbar (wer/wann/warum) und nie versehentlich auslösbar.
  3. Erkenntnis auf Abruf — eine Ereigniskette oder Vorhersage gezielt anstoßen und das Ergebnis mit Herkunft und Vorbehalt lesen.
- **Techniker** (Schnellzugriff, Offline, große Bedienelemente):
  1. Sofort am richtigen Detail — von Alarm/Auftrag direkt zur Maschine mit Historie und Ersatzteilkontext, ohne Umweg.
  2. Feldtauglichkeit — funktioniert mit Handschuh, einhändig, im Funkloch.
  3. Diagnose-Tiefe bei Bedarf — Ereignisketten und Verlauf als Werkzeug, wenn er sie braucht, ausgeblendet, wenn nicht.
- **Werks-/Flottenmanager** (Cockpit, übergreifend):
  1. Lageüberblick in Sekunden — Flotten-/Werksgesundheit als Ampel- und Heatmap-Bild, Drill nur bei Bedarf.
  2. Klassen- statt Einzelblick — gleiche Maschinentypen über Werke hinweg vergleichbar, um systematische Drift zu sehen.
  3. Belastbare Kennzahl — Verfügbarkeit/Stillstände/Ursachen als reportfähige, herkunftsklare Zahl, nicht als geschöntes Dashboard.

### 1.3 Industrie-6.0-Positionierung

**4.0** war Vernetzung und Sichtbarmachung: Maschinen liefern Daten, Dashboards zeigen sie. Der Designauftrag war Telemetrie — viele Kacheln, viele Kurven, Zustand in Echtzeit. **5.0** setzte den Menschen ins Zentrum und betonte Kollaboration und Ergonomie: das Interface passt sich der Rolle an, Mensch und System arbeiten zusammen, Wohlbefinden und Bedienbarkeit werden Designziele.

**6.0 im Frontend ist der Schritt von der Anzeige zur Erklärung — von Daten zu Gedächtnis.** Drei Paradigmenwechsel definieren die Ära, und sie sind genau das, was FOREMANs zehn Sektionen und drei Haltungen verkörpern:

1. **Von Echtzeit-Zustand zu zeitlich-kausalem Gedächtnis.** 4.0 zeigt, was jetzt ist. 6.0 beantwortet „hatten wir das schon mal, was folgte daraus, was wirkt dagegen" — über Zeit, über Anlagen, über die ganze Maschinenklasse. Im Frontend heißt das: die Zeitachse ist kein Filter, sondern ein Erzählraum (4B Zeitreise, 4D Ereignisketten), und Wissen ist eine eigene, begehbare Sicht (4H), kein Suchfeld in der Ecke. Das ist der Sprung, den 4.0-Dashboards strukturell nicht machen können.

2. **Von Automatisierung zu erklärter Empfehlung mit Vorbehalt.** 5.0 lässt Mensch und System kollaborieren; 6.0 macht die Maschine zum erklärenden Ratgeber, der seine eigene Unsicherheit ausstellt. Die Plattform empfiehlt und begründet — mit sichtbaren Einflussfaktoren — und sie schaltet nie selbst (HITL). Der **Simulations-Vorbehalt** ist der ehrlichste Ausdruck dieser Ära: ein System, das sagt „das beruht auf Simulationsdaten, nicht auf Feldvalidierung", ist 6.0; ein System, das eine Vorhersage als Gewissheit verkauft, ist Marketing. Im Frontend ist dieser Vorbehalt ein untrennbarer Block, kein Kleingedrucktes.

3. **Von App zu Plattform mit föderiertem, paraphrasiertem Gedächtnis.** 6.0 denkt nicht eine Anlage, sondern Werke, Klassen, Drittsysteme als ein verbundenes Ganzes (4A Föderation, 4I Plattform/Integration). Das Gedächtnis ist die Substanz, die das verbindet — und es bleibt nach außen paraphrasiert. Der Designauftrag ist hier, „Plattform statt App" sichtbar zu machen, ohne das innere Vokabular preiszugeben.

Die drei bleibenden Haltungen sind damit keine Vorsichtsmaßnahmen, sondern die Verkörperung von 6.0: **Vorbehalt** (ehrliche Unsicherheit), **HITL** (Mensch entscheidet), **Paraphrase** (Plattform-Gedächtnis ohne Selbstentblößung). Ein Frontend, das diese drei nicht permanent trägt, fällt auf 4.0 zurück, egal wie modern es aussieht.

---

## 2. Design-Leitbild und operative Prinzipien

### Leitbild

> **FOREMAN sieht aus wie eine ruhige Anlage, die im Normalfall schweigt und nur dann spricht, wenn sie etwas Belegbares zu sagen hat.** Die Oberfläche ist eine entsättigte, kontraststarke Werkstatt-Fläche, auf der Farbe knapp und ausschließlich bedeutungstragend ist; Information ist nach Dringlichkeit geschichtet, nicht nach Datenmenge ausgebreitet. Jede Erkenntnis trägt ihre Herkunft und, wo sie eine Vorhersage ist, ihren Vorbehalt offen mit sich. Die Plattform erklärt und empfiehlt mit großen, handschuhsicheren Bedienelementen, sie entscheidet und schaltet nie — der Mensch bleibt die letzte Instanz. Sie ist auf Distanz, im Halbdunkel, mit Handschuh und im Funkloch benutzbar, und sie spricht in der Sprache der Halle, nicht in der ihres Innenlebens.

Aus diesem Leitbild folgen acht operative Prinzipien. Jedes ist so formuliert, dass es eine prüfbare Regel, ein explizit verbotenes Gegenbild und einen Wirkungsschwerpunkt hat.

### Die acht Prinzipien

**1. Hierarchie statt Informationsflut**
- *Statement:* Was am dringendsten zu wissen ist, ist am schnellsten zu sehen — der Rest tritt zurück.
- *Regel:* Pro Sicht maximal eine primäre Information pro Blickzone; höchste Dringlichkeitsstufe belegt die obere und linke Position und die größte Typo-/Flächenstufe. Nie mehr als 3 visuelle Gewichtsstufen gleichzeitig aktiv. Eine Sicht im Normalbetrieb zeigt ≤ 7 farbige Akzente.
- *Negativbeispiel:* Eine Kachelwand, in der 20 KPIs gleich groß, gleich farbig und gleich laut nebeneinanderstehen — der Blick findet keinen Anker und liest alles oder nichts.
- *Wirkt in:* A (Cockpit), C (Alarme), E (Vorhersage).

**2. Konsistente Navigation und Zustände**
- *Statement:* Gleiche Dinge sehen gleich aus und verhalten sich gleich, egal in welcher Sicht.
- *Regel:* Ein einziges kanonisches Zustandsvokabular (NE 107 FCSM + Alarm-Prioritäten) gilt plattformweit; jede Komponente kennt die fünf Pflichtzustände live / gecacht / lädt / leer / Fehler und stellt sie identisch dar. Navigation, Breadcrumb und Zurück-Verhalten sind über alle Sektionen gleich.
- *Negativbeispiel:* „Gelb" bedeutet im Cockpit Warnung, im Detail aber „ausgewählt"; ein Ladezustand erscheint mal als Spinner, mal als leere Fläche.
- *Wirkt in:* alle, strukturell besonders A, B, C, H.

**3. Farben sparsam und semantisch**
- *Statement:* Farbe ist reserviert; sie codiert Bedeutung, nie Dekoration.
- *Regel:* Die Grundfläche ist neutral/entsättigt; gesättigte Farbe erscheint nur für Status, Severity und Abweichung. Jede Farbcodierung hat einen zweiten, farbunabhängigen Kanal (Form, Position, Label, Muster). Maximal eine kritische Farbe (Rot) gleichzeitig dominant.
- *Negativbeispiel:* Markenverlauf als Hintergrund, bunte Kategorie-Farben für neutrale Datenreihen, dauerhaft rote Header „weil das industriell wirkt".
- *Wirkt in:* C (Alarme), A (Heatmap), E (Konfidenz), B (Drift).

**4. Große Zielbereiche und robuste Bedienung**
- *Statement:* Bedienbar mit Handschuh, in Bewegung, im Halbdunkel — ohne Präzision vorauszusetzen.
- *Regel:* Primäre Touch-Ziele ≥ 56×56 px, sicherheitsrelevante ≥ 64×64 px, Abstand ≥ 12 px; jede destruktive/verantwortliche Aktion braucht eine zweistufige Bestätigung, die nicht versehentlich auslösbar ist; kein Hover als einziger Zugang zu Funktion.
- *Negativbeispiel:* Ein 32-px-„Quittieren"-Link neben anderen Links, der mit Handschuh die Nachbarzeile trifft; eine Aktion, die nur per Maus-Hover erscheint.
- *Wirkt in:* C (Quittieren), G (Slider), J (Erfassung), B (mobil).

**5. Rollenbasierte Views**
- *Statement:* Jede Rolle sieht ihren Auftrag zuerst, nicht das Maximum.
- *Regel:* Landing, Navigationseinträge, Informationsdichte und Default-Aktion sind je Rolle definiert (Matrix 3.1); eine Rolle bekommt keine Sektion, deren Aktion sie nicht hat. Rollenwechsel ändert die Sicht spürbar, nicht nur ein Badge.
- *Negativbeispiel:* Werker und Manager bekommen denselben überladenen Cockpit-Screen, einer davon ist immer falsch bedient.
- *Wirkt in:* A, B, F, I (am stärksten dichte-/zugriffsdifferenziert).

**6. Trend + Zustand + Ursache**
- *Statement:* Jeder Wert wird zusammen mit seiner Richtung und, wo verfügbar, seiner Ursache gezeigt — nie nackt.
- *Regel:* Numerische Kernwerte tragen immer einen Verlaufs-Spark (Trend) und einen Zustands-Indikator; wo eine Erkenntnisschicht existiert, ist der Sprung „Wert → Verlauf → Ursache/ähnlicher Fall" in maximal einer Interaktion erreichbar.
- *Negativbeispiel:* „Temperatur 78 °C" als einzelne Zahl ohne Verlauf, ohne Normalband, ohne Hinweis, ob das steigt oder steht.
- *Wirkt in:* B (Detail), D (Ketten), E (Vorhersage), F (Wartung).

**7. Responsives Verhalten**
- *Statement:* Dieselbe Sicht funktioniert vom Leitstand-Monitor bis zum Handschuh-Handy — durch Umbau, nicht durch Schrumpfen.
- *Regel:* Definierte Breakpoints mit je eigener Layout-Absicht (Leitstand-Dichte / Tablet-Touch / Mobil-Einhand); auf kleinen Geräten wird Inhalt priorisiert weggelassen, nicht skaliert; Touch-Zonen wandern in den Daumenbogen.
- *Negativbeispiel:* Der Leitstand-Screen wird per CSS auf Handygröße gestaucht, KPI-Zahlen werden 9 px klein, der Quittieren-Button rutscht außer Daumenreichweite.
- *Wirkt in:* B, C, J (Geräteband Leitstand→Mobil), G.

**8. Barrierearme, kontraststarke Darstellung**
- *Statement:* Lesbar auf Distanz, im Streulicht, mit eingeschränktem Farbsehen.
- *Regel:* Status-Text ≥ 7:1 Kontrast (über WCAG-AA hinaus), Körpertext ≥ 4.5:1, grafische/Bedien-Elemente ≥ 3:1; keine Information allein über Farbe; `prefers-reduced-motion` und Tastaturbedienung vollständig unterstützt; Farbpaletten gegen die häufigen Farbsehschwächen geprüft (Rot/Grün nie allein bedeutungstragend).
- *Negativbeispiel:* Rot/grüne Statuspunkte ohne Form-Unterschied; dünner hellgrauer Text auf mittelgrauem Grund, der auf 2 m verschwindet.
- *Wirkt in:* alle; am schärfsten C, A, E.

Die Prinzipien sind nicht gleichrangig in Konfliktfällen: bei Widerspruch gewinnt die Reihenfolge **8 → 4 → 1 → 3** (Lesbarkeit/Bedienbarkeit/Hierarchie/Farbsemantik) vor allem anderen. Ein schönes Layout, das auf 3 m nicht lesbar ist, ist falsch, egal wie konsistent es ist.

---

## 3. Informationsarchitektur und Navigationsmodell

### 3.1 Rollenbasierte Navigationslogik

Der Rollenschnitt ist die früheste Designentscheidung, weil er die Navigation trägt. Die Matrix zeigt je Rolle und Sektion den Zugriff, die Hauptaktion und die Informationsdichte. Lesart der Zugriffsspalte: **●** voll · **◐** reduziert/lesend · **○** kein Zugriff.

| Sektion | Werker | Schichtleiter | Techniker | Manager |
|---|---|---|---|---|
| **A** Flotten-Cockpit | ○ — | ◐ eigene Linien, lesen · *mittel* | ○ — | ● Vollbild, alle Werke/Klassen · *hoch (verdichtet)* |
| **B** Maschinen-Detail | ◐ lesen + notieren · *mittel* | ● lesen + quittieren · *hoch* | ● lesen + Offline-Cache · *hoch* | ◐ verdichtet lesen · *mittel* |
| **C** Alarme & Warnungen | ◐ eigener Bereich, filtern · *mittel* | ● quittieren + eskalieren · *hoch* | ◐ zugewiesene, offline · *mittel* | ◐ Zähler/Trends, aggregiert · *niedrig* |
| **D** Ereignisketten | ◐ gespeicherte lesen · *niedrig* | ● rekonstruieren (Trigger) · *hoch* | ● lesen für Diagnose · *hoch* | ◐ Zusammenfassung lesen · *niedrig* |
| **E** Ausfallvorhersage | ◐ Empfehlung lesen · *niedrig* | ● anstoßen + quittieren · *hoch* | ◐ lesen · *mittel* | ◐ Risiko aggregiert · *niedrig* |
| **F** Wartungszyklen | ◐ Anstehendes lesen · *niedrig* | ● planen · *hoch* | ● ausführen/abhaken · *mittel* | ● Intervall-/Kostenblick · *hoch* |
| **G** Belastungs-Simulation | ● durchspielen · *mittel* | ● durchspielen · *hoch* | ● durchspielen · *hoch* | ◐ Ergebnis lesen · *niedrig* |
| **H** Gedächtnis & Verknüpfung | ● suchen/lesen · *mittel* | ● suchen/verknüpfen · *hoch* | ● suchen für Diagnose · *hoch* | ◐ thematisch suchen · *mittel* |
| **I** Integration/Plattform | ○ — | ◐ Status lesen · *niedrig* | ○ — | ● Topologie + Audit · *hoch* |
| **J** Eingabe & Erfassung | ● erfassen (primär) · *fokussiert* | ● erfassen + sichten · *mittel* | ● mobil erfassen · *mittel* | ◐ lesen · *niedrig* |

**Begründung der Ausschlüsse** (jeder Ausschluss ist eine Entlastung, kein Mangel):

- **Werker → A, I (○).** Das Flotten-Cockpit aggregiert über Werke und Klassen; das ist nicht der Auftrag des Werkers und würde ihn von seiner Maschine ablenken. Die Plattform-/Integrationssicht ist Administrations- und Audit-Material ohne Bezug zu seiner Schichtaufgabe. Ausblenden schützt seinen Fokus auf Erfassen/Lesen/Suchen.
- **Techniker → A, I (○).** Der Techniker arbeitet maschinen- und auftragszentriert, nicht flottenstrategisch; das Cockpit gäbe ihm Breite, wo er Tiefe braucht. Die Plattformsicht ist für seinen Diagnoseauftrag irrelevant.
- **Schichtleiter → A, I (◐).** Er sieht die Flotte nur für seine Linien (Lagebild seiner Verantwortung), nicht werksübergreifend; Plattformstatus nur lesend, weil Integrationsentscheidungen Management/Admin sind.
- **Manager → C, D, E (◐, aggregiert).** Der Manager quittiert keine Einzelalarme und stößt keine Einzel-Rekonstruktion an — das wäre Mikromanagement und verwischt Verantwortung. Er bekommt verdichtete Zähler, Trends und Risikobilder; der Drill ins Einzelne ist möglich, aber nicht die Default-Dichte.
- **G ist für alle ● (außer Manager ◐).** Die Belastungs-Simulation ist bewusst die eine Sektion, in der auch der Werker aktiv durchspielt statt nur liest — sie ist das didaktische, gefahrlose Probierfeld. Der Manager liest hier nur Ergebnisse, weil das Durchspielen eine operative, keine strategische Handlung ist.

### 3.2 Live-vs-On-Demand-Architektur

Die Architektur trennt zwei Datenregime, und diese Trennung ist im UI erlebbar, nicht nur technisch.

**Informationsfluss (beschriebenes Diagramm):**

```
   ANLAGE / SUBSTRAT                  FOREMAN-BACKEND                 FRONTEND-SICHTEN
   ─────────────────                  ───────────────                ────────────────

   Sensoren  ─┐                                                      ┌─ A Cockpit      ◀── live
   Maschinen ─┤   Stream    ┌────────────────────────┐   PUSH       ├─ B Detail (Trend)◀── live
   Alarme    ─┴──────────▶  │  Ingest + Zustandskern │ ════════════▶├─ C Alarme       ◀── live
                            │  (live, push-fähig)    │  WebSocket   └─ Status-/Alarmleiste (global)
                            └───────────┬────────────┘
                                        │
                                        │  speist
                                        ▼
                            ┌────────────────────────┐
   Nutzer-Trigger ────────▶ │  Erkenntnis-Schicht    │   PULL       ┌─ D Ereignisketten
   („rekonstruieren",       │  (Reasoner, on-demand) │ ◀───────────▶├─ E Ausfallvorhersage
    „vorhersagen",          │  + Herkunft + Vorbehalt│  Request/    ├─ F Wartungskausalität
    „simulieren",           │                        │  Response    ├─ G Belastungs-Simulation
    „suchen")               └───────────┬────────────┘              └─ H Semantische Suche
                                        │
                                        ▼
                            ┌────────────────────────┐
                            │  Gedächtnis-Substrat    │ (paraphrasiert nach außen)
                            │  speist Erkenntnis +    │
                            │  H-Suche, klassen-/     │
                            │  werksübergreifend      │
                            └────────────────────────┘
```

**Wie der Übergang im UI erlebt wird.** Live-Sichten (A, B-Trend, C) atmen sichtbar: ein dezenter Live-Puls am Sicht-Header und ein „aktualisiert vor 2 s"-Stempel signalisieren, dass die Daten von selbst kommen. Niemand drückt einen Knopf, um Zustand zu sehen. On-Demand-Sichten (D–H) sind im Ruhezustand leer oder zeigen frühere Ergebnisse mit Datum; sie tragen einen klaren **Auslöser** („Kette rekonstruieren", „Vorhersage anfordern", „Szenario rechnen", „suchen"). Nach dem Auslösen erscheint ein **Verarbeitungszustand** (kein generischer Spinner, sondern ein benannter Fortschritt: „suche ähnliche Fälle über die Klasse…"), dann das **Ergebnis mit Herkunftsstempel** (Stand, Datenbasis, bei Vorhersage der Simulations-Vorbehalt).

**Daraus entstehende Interaktionsmuster:**

- **Ambient-Read (live):** kein Trigger, kein Bestätigen; Aufmerksamkeit wird nur bei Schwellenüberschreitung geholt (Alarm-Puls), sonst ruhig. Regel: Live-Sichten dürfen den Nutzer nie zu einer Aktion zwingen, nur einladen.
- **Trigger → Provenance → Vorbehalt (on-demand):** jede erzeugte Erkenntnis durchläuft sichtbar denselben Dreischritt. Das macht „erklärte Empfehlung" zum wiederkehrenden, lernbaren Muster statt zu zehn verschiedenen Dialogen.
- **Pin/Persist:** eine abgerufene Erkenntnis kann an eine Live-Sicht angeheftet werden (z. B. eine rekonstruierte Kette an die Maschinen-Zeitachse), wodurch ein On-Demand-Ergebnis kontrolliert in den Live-Kontext wandert — mit eingefrorenem Stand-Stempel, damit klar bleibt, dass es eine Momentaufnahme ist.
- **Degradation:** bricht das Netz, frieren Live-Sichten auf „gecacht, Stand X" ein (kein Leerlaufen), On-Demand-Trigger werden sichtbar deaktiviert mit Grund („offline — Erkenntnis nicht abrufbar"), Erfassung (J) bleibt voll funktionsfähig und puffert.

### 3.3 Navigationsstruktur

Die Struktur folgt drei Kräften gleichzeitig: dem Rollenschnitt (wer darf was), der Live/On-Demand-Trennung (Zustand vs. Erkenntnis) und der Bereichs-Fokus-Matrix (Leitstand/Linie/Instandhaltung/Mobil/Management).

**Persistente Rahmenelemente (immer sichtbar, sektionsunabhängig):**

- **Globale Status-/Alarmleiste (oben, live).** Trägt das aggregierte FCSM-/Alarmbild des aktuellen Geltungsbereichs (Flotte/Werk/Linie/Maschine je nach Tiefe). Sie ist der einzige Ort, an dem Live-Dringlichkeit den Nutzer aktiv holen darf, und über alle Sektionen identisch — Prinzip 2.
- **Geltungsbereichs-Breadcrumb mit Zoom (Föderations-Achse).** `Flotte ▸ Klasse ▸ Werk ▸ Maschine` als durchgehender, anklickbarer Pfad; er ist gleichzeitig Navigation und Kontextanzeige und trägt den Zoom-Pfad aus Sektion A.
- **Globale Suche / Befehlsleiste (Cmd-K-Muster).** Erreicht Sektion H (semantische Suche) und Sprungziele von überall — der Werker findet „hatten wir das schon mal" ohne Menütiefe.
- **Schnellerfassung (Floating Action / Sprachknopf).** Sektion J ist als persistente Schnellaktion erreichbar, weil Erfassen die Kern-Werkertätigkeit ist und nie zwei Navigationsschritte kosten darf.

**Primärnavigation (rollengefiltert, links am Leitstand/Tablet, unten/Drawer am Mobil):**

1. **Cockpit** (A) — nur Manager/Schichtleiter; deren Landing.
2. **Linie & Maschinen** (B) — alle; Landing für Werker/Techniker.
3. **Alarme** (C) — alle außer rein aggregiert für Manager.
4. **Erkenntnisse** (D, E, F, G gruppiert) — die On-Demand-Reasoner unter einem Dach, weil sie dasselbe Interaktionsmuster teilen (Trigger→Provenance→Vorbehalt). Untergliederung als Sekundärnavigation.
5. **Gedächtnis** (H) — eigener Raum, zusätzlich global über die Befehlsleiste.
6. **Erfassung** (J) — eigener Raum plus persistente Schnellaktion.
7. **Plattform** (I) — nur Manager/Admin.

**Sekundärnavigation (innerhalb einer Sektion):** z. B. innerhalb der Maschine: `Trends · Stammdaten · Wartungshistorie · Notizen · Alarme`; innerhalb von „Erkenntnisse": `Ketten · Vorhersage · Wartung · Simulation`. Immer als horizontale, gleichbleibende Reiterleiste direkt unter dem Sicht-Header.

**Kontextnavigation:** Drill-down- und Querverlinkungs-Pfade, die nicht im Menü stehen, sondern im Inhalt: ein Alarm verlinkt zur Maschine und zur passenden Ereigniskette; eine Vorhersage verlinkt zu den belegenden Sensorverläufen; ein Suchtreffer (H) springt zur Quelle. Diese Pfade sind in Sektion 4 je Sektion unter „Verbindung zu anderen Sektionen" ausspezifiziert.

**Warum diese Struktur optimal bedient:**

- **Rollenschnitt:** die Primärnavigation ist je Rolle eine andere kurze Liste mit rollenspezifischem Landing — kein Nutzer sieht Einträge ohne zugehörige Aktion (Prinzip 5). Die Liste bleibt mit ≤ 7 Einträgen auf einen Blick erfassbar.
- **Live/On-Demand:** die Trennung ist in der IA verankert — „Cockpit/Linie/Alarme" sind die Zustandsräume, „Erkenntnisse/Gedächtnis" die Abrufräume. Der Nutzer lernt einmal, wo er mit Selbst-Aktualisierung rechnet und wo er triggert.
- **Bereichs-Fokus-Matrix:** Leitstand bedient Cockpit + Alarme; Linien-/Maschinenansicht ist „Linie & Maschinen"; Instandhaltung lebt in „Erkenntnisse" + Maschinen-Historie; die Techniker-Mobilansicht ist die Einhand-Projektion von „Linie & Maschinen" + „Alarme" + „Erfassung"; das Management-Dashboard ist das Cockpit plus die aggregierten Schnitte von C/E/F. Jede Zeile der Matrix hat damit einen eindeutigen Heimatort.

---

## 4. Zehn Sektionen — Designkonzept je Sektion

Jede Sektion folgt demselben Raster, damit sie einzeln umsetzbar ist. Layout-Angaben sind in Zonen, Proportionen und Ankerelementen beschrieben; konkrete Token (Farbe, Typo, Abstand) liefert Sektion 5.

### A. Flotten-Cockpit · [VISION]

**Reifegrad und was das für die Gestaltung heißt.** [VISION] — das Zielbild im Vollausbau, föderiert über Werke. Gestalterisch heißt das: das Cockpit wird so entworfen, dass es **mit einer einzigen Maschine genauso stimmig ist wie mit tausend**. Es darf nie leer oder „kaputt" wirken, wenn die Föderation noch klein ist. Daher: Verdichtungsstufen, die graceful von „ein Werk" auf „viele Werke" hochskalieren, und klar als Zielbild markierte Bereiche (dezent, nicht als Platzhalter-Geröll).

**Zweck und Leitfrage.** *„Wo in meiner Flotte muss ich jetzt hinschauen — und gibt es ein Muster über gleichartige Maschinen hinweg?"*

**Informationsarchitektur.** Drei Ebenen, von grob nach fein: (1) Aggregierte Gesundheits-Ampel je Geltungsbereich (Werk/Klasse), (2) Drift-Heatmap, die gleichartige Maschinen einer Klasse nebeneinanderstellt, (3) die kritischsten Einzel-Ereignisse als Einstiegspunkte. Gruppierung primär nach **Maschinenklasse** (gleiche Typen zusammen), sekundär nach Werk. Das ist die Kerninnovation: nicht „Werk A, Werk B", sondern „alle Pressen, alle Spindeln" — so wird systematische Drift sichtbar, die pro Maschine im Rauschen verschwindet.

**Layout-Konzept.** Querformat, Leitstand-Monitor. Oben die globale Status-/Alarmleiste (live). Darunter eine schmale **KPI-Zeile** (Flottenverfügbarkeit, offene kritische Alarme, Maschinen in Drift) — links, weil oben/links die höchste Aufmerksamkeit trägt (Prinzip 1). Die mittlere, größte Zone (≈ 60 % der Höhe) gehört der **Drift-Heatmap**: Zeilen = Maschinenklassen, Spalten = einzelne Maschinen/Werke, Zellfarbe = Abweichung gegen Klassen-/Eigenprofil. Rechts eine schmale Spalte „braucht Blick jetzt" mit den 3–5 dringendsten Einstiegen. Leserichtung: KPI links→rechts, dann Heatmap als Block, dann rechte Prioritätsspalte als Abschluss. Ankerelement ist die Heatmap; alles andere ordnet sich ihr unter.

**Interaktionsmodell.** *Ein:* Hover/Tap auf Heatmap-Zelle → Mini-Vorschau (Maschine, Klasse, Driftwert, Trend); Klick → Zoom-Pfad `Flotte → Klasse → Werk → Maschine`. Geltungsbereichs-Breadcrumb erlaubt Sprung auf jede Ebene. *Aus:* live Push der Aggregate; Zellen aktualisieren in-place mit dezentem Wert-Übergang (kein Springen). Zustandsübergänge: eine Zelle, die in Drift kippt, pulst einmal kurz auf und bleibt dann farbig stehen (kein Dauerblinken).

**Visuelle Kodierung.** Heatmap-Farbe = sequenzielle, einfarbige Intensitätsskala für Driftstärke (nicht Regenbogen — Regenbogen verfälscht Ordnung). Severity-Farben nur in der KPI-Zeile und Prioritätsspalte. Form/Position codieren Klasse (Zeile) und Identität (Spalte) farbunabhängig. Keine Animation außer dem einmaligen Kipp-Puls. Typo: KPI-Zahlen groß (Distanzlesbarkeit), Heatmap-Achsenlabels klein, aber ≥ 14 px.

**Rollenspezifische Varianten.** Manager: voller föderierter Umfang, alle Werke/Klassen. Schichtleiter: auf eigene Linien/Werk gefiltert, Heatmap zeigt nur seine Maschinen. Werker/Techniker: kein Zugang (3.1).

**Verbindung zu anderen Sektionen.** Zelle → B (Maschinen-Detail). Prioritätsspalte → C (Alarm) oder E (Vorhersage). Klassen-Drift-Muster → D (klassenübergreifende Ereigniskette an Schwestermaschine) und H (Gedächtnis: „ähnliche Drift schon mal in dieser Klasse?").

---

### B. Maschinen-Detail · [KERN STEHT]

**Reifegrad.** [KERN STEHT] — Sensortrends, Stammdaten, Historie, Alarme sind belastbar; die tiefe Zeitreise (neun Monate, Profilvergleich) ist Vision. Gestalterisch: das Grundlayout wird voll ausgebaut und stabil, die Zeitreise-Achse wird als erweiterbare Komponente entworfen, die heute mit vorhandener Tiefe funktioniert und später nahtlos in Wochen/Monate/Jahre wächst — ohne Re-Design.

**Zweck und Leitfrage.** *„Wie geht es dieser Maschine — jetzt und im Verlauf — und weicht sie von ihrem eigenen Normalverhalten ab?"*

**Informationsarchitektur.** Kopf: Identität + aktueller FCSM-Status + Schlüssel-KPIs. Hauptkörper: Sensortrends (live + historisch) mit Normalband und Eigenprofil-Overlay. Seitlich/darunter: Stammdaten, Wartungshistorie, Notizen, maschinenbezogene Alarme. Hierarchie: Zustand jetzt (oben) → Verlauf (Mitte, größte Fläche) → Kontext/Historie (unten/seitlich).

**Layout-Konzept.** Kopfzone (≈ 12 % Höhe): Maschinenname, Klasse, Standort, großer Statusindikator (FCSM), 3–4 KPI-Werte mit Spark. Mittelzone (≈ 55 %): die **Trend-/Zeitreise-Komponente** als Ankerelement — eine oder gestapelte Sensorkurven mit gemeinsamer X-Zeitachse, Normalband als hinterlegte Fläche, Eigenprofil als gestrichelte Referenzlinie. Unterzone (≈ 33 %): Reiter `Stammdaten · Wartung · Notizen · Alarme`. Leserichtung: Status oben → Verlauf → Detailreiter. Auf Tablet/Mobil klappt die Unterzone unter den Trend, KPIs werden zu einer scrollbaren Zeile.

**Zeitachsen-Interaktion und Profilvergleich (im Detail).** Die Zeitachse hat zwei gekoppelte Ebenen: einen **Übersichts-Streifen** (ganze verfügbare Historie als komprimierter Spark, mit markierten Ereignissen: Wartungen, Alarme, Notizen als kleine Marker) und ein **Detailfenster** darüber. Ziehen/Pinch im Detailfenster zoomt; Ziehen im Übersichts-Streifen verschiebt das Fenster („Zeitreise"). Vordefinierte Sprünge: `Schicht · Tag · Woche · Monat · 9 Monate`. **Profilvergleich:** ein Umschalter „gegen Eigenprofil" legt das gelernte Normalband der Maschine als Referenz unter die Live-Kurve; Abweichung wird als Differenzfläche eingefärbt (Über-/Unterschreitung farblich getrennt, aber mit Form/Schraffur zusätzlich). Ein zweiter Modus „gegen Klasse" vergleicht mit dem Klassenprofil (Brücke zu A). Marker auf der Achse sind anklickbar → Sprung zur Notiz (J), zum Alarm (C) oder zur Ereigniskette (D).

**Interaktionsmodell.** *Ein:* Zeitfenster wählen, Sensoren ein/ausblenden, Profil-Overlay schalten, Marker antippen, Notiz hinzufügen. *Aus:* Live-Kurve schiebt nach links (Stream), historische Bereiche sind statisch; Profil-Differenz aktualisiert live. Zustandsübergänge: Wechsel live↔historisch ist sichtbar (Live-Puls erlischt, „Stand"-Stempel erscheint).

**Visuelle Kodierung.** Sensorlinien in entsättigten, unterscheidbaren Neutraltönen (nicht semantische Farben — die bleiben dem Status vorbehalten); Normalband als sehr dezente Fläche; Abweichung als einzige gesättigte Einfärbung. Marker formcodiert (Wartung = Schraubsymbol, Alarm = Dreieck, Notiz = Stift). Typo: aktuelle Sensorwerte mit Tabellenziffern (tabular figures), damit sie beim Live-Update nicht springen.

**Rollenspezifische Varianten.** Werker: lesen + Notiz, reduzierte Sensorauswahl, große Marker. Schichtleiter: voll + quittieren direkt aus dem Alarm-Reiter. Techniker: volle Dichte, Offline-Cache mit „Stand"-Stempel, große Bedienelemente für mobil. Manager: verdichtete Kurve, keine Einzelnotiz-Aktion.

**Verbindung zu anderen Sektionen.** Achsen-Marker → C/D/J. Profil-/Klassenvergleich ↔ A. „braucht das Aufmerksamkeit?" → E (Vorhersage für diese Maschine). Notiz-Reiter ↔ J und H.

---

### C. Alarme & Warnungen · [STEHT]

**Reifegrad.** [STEHT] — voll ausgestalten. Live-Alarme inkl. Drift-Warnungen, Severity, Status, Quittieren (HITL), Filter. Hier wird nichts angedeutet, hier wird die Eskalationslogik vollständig gebaut.

**Zweck und Leitfrage.** *„Was verlangt jetzt meine Entscheidung — in welcher Reihenfolge?"*

**Informationsarchitektur.** Alarme nach **Priorität gestaffelt** (ISA-18.2: kritisch / hoch / mittel / niedrig + Diagnose-/Journal-Ebene), nicht chronologisch-flach. Jede Alarmzeile: Priorität, Maschine, Zustandsklasse (FCSM), Kurztext, Zeit, Status (aktiv / quittiert / unterdrückt), erwartete Bedienhandlung. Gruppierung wahlweise nach Priorität, Bereich oder Maschine. Drift-Warnungen sind eine eigene, klar markierte Klasse (weicher als ein harter Alarm, aber sichtbar).

**Layout-Konzept.** Kopf: Filter-/Gruppierungsleiste + Zähler je Priorität (z. B. „2 kritisch · 5 hoch · 11 mittel"). Hauptkörper: virtualisierte Alarmliste, nach Priorität sortiert, kritische immer oben und farblich/flächig hervorgehoben. Jede Zeile ist hoch genug für Handschuh-Tap (≥ 56 px) und trägt rechts die Primäraktion (Quittieren) als großes Ziel. Leserichtung: Zähler → Liste von oben (kritisch) nach unten. Persistente globale Alarmleiste bleibt darüber.

**Eskalationslogik (im Detail).** Drei Achsen: **Priorität** (statisch je Alarm aus der Rationalisierung), **Lebenszyklus** (aktiv → quittiert → geklärt; ISA-18.2-Zustände inkl. „unterdrückt/shelved" und „außer Dienst") und **zeitliche Eskalation** (ein unquittierter kritischer Alarm verschärft seine Präsenz nach definierter Frist: erst Listenhervorhebung, dann globale Leiste, dann Benachrichtigung an die nächste Verantwortungsstufe). Unquittierte kritische Alarme tragen einen langsamen 1-Hz-Aufmerksamkeitspuls (ISA-18.2-konform: Blinken signalisiert *unquittiert*, nicht *Severity*); mit Quittieren hört das Blinken auf, die Farbe bleibt, bis geklärt. **Flood-Schutz:** bei Alarmlawinen (viele Alarme einer Wurzelursache) werden zusammengehörige Alarme gebündelt dargestellt („12 Alarme, gemeinsame Quelle Linie 3") statt als 12 Einzelzeilen — sonst kippt die Liste in Unlesbarkeit. Shelving/Unterdrücken ist möglich, aber sichtbar und zeitlich begrenzt (nie still verschwinden).

**Interaktionsmodell.** *Ein:* filtern, gruppieren, Zeile öffnen, **Quittieren** (zweistufig: Tap → kurze Bestätigung mit Pflicht-Kontext bei kritisch), eskalieren, shelven. *Aus:* live Push neuer Alarme (oben einfügen mit kurzem Einblend-Puls, nie die ganze Liste neu sortieren-springen lassen). Zustandsübergänge: aktiv→quittiert wechselt Zeilenzustand sichtbar (Puls aus, Häkchen + „quittiert von … um …").

**Visuelle Kodierung.** Severity als Farbe **und** Position **und** Label (dreifach codiert — Prinzip 3/8). Kritisch = einzige dominante Rot-Fläche; hoch = Orange-Akzent (kein Vollflächen-Rot); mittel = gedämpftes Gelb als Rand/Punkt; niedrig/Diagnose = neutral mit Symbol. FCSM-Symbol je Zeile. Bewegung nur für „unquittiert kritisch" und für das Einblenden neuer Alarme.

**Rollenspezifische Varianten.** Werker: eigener Bereich, lesen + filtern, kein Quittieren. Schichtleiter: voll, Quittieren/Eskalieren ist die Default-Aktion, Pflicht-Kontext beim Quittieren kritischer Alarme. Techniker: zugewiesene Alarme, offline lesbar, große Ziele. Manager: nur Zähler/Trends (Alarmrate, häufigste Quellen), kein Einzel-Quittieren.

**Verbindung zu anderen Sektionen.** Alarm → B (Maschine), → D (Ereigniskette rekonstruieren), → E (führt das zu einem Ausfall?). Quittier-Vorgang ist im Audit (I) nachvollziehbar. Drift-Warnung ↔ A-Heatmap.

---

### D. Ereignisketten · [STEHT]

**Reifegrad.** [STEHT] — voll ausgestalten. Rekonstruierte Erzählung mit verlinkten Quellen auf der Zeitachse, klassenübergreifend.

**Zweck und Leitfrage.** *„Was ist hier in welcher Reihenfolge passiert — und gab es das an einer Schwestermaschine schon mal?"*

**Informationsarchitektur.** Kern ist eine **Erzählung entlang der Zeitachse**: eine geordnete Folge von Ereignissen (Sensorausschlag, Alarm, Wartung, Notiz), die zu einer lesbaren Geschichte verbunden sind. Jeder Erzählschritt ist **an seine Quelle gebunden** — der Text ist nie quellenlos. Streng getrennt: was durch eine Quelle **belegt** ist (vertrauenswürdig markiert) vs. die **verbindende Freitext-Erzählung** (als erzeugt gekennzeichnet, AI-Act-Transparenz). Klassenübergreifend: eine ähnliche Kette an einer Schwestermaschine wird als Querverweis angeboten.

**Layout-Konzept.** Zweispaltig (Leitstand/Tablet): links die **Zeitachsen-Spalte** (vertikale Timeline, Ereignisse als Knoten mit Zeitstempel und Quelltyp-Symbol), rechts die **Erzähl-/Detailspalte** (die zusammenhängende Geschichte, Absätze mit Inline-Quellverweisen `[Quelle]`). Klick auf einen Timeline-Knoten scrollt die Erzählung zur passenden Stelle und hebt die Quelle hervor (gekoppeltes Scrollen). Oben: Anker-/Auslöser-Leiste (Kette rekonstruieren / gespeicherte abrufen). Mobil: Timeline und Erzählung gestapelt, Sprungmarken statt Nebeneinander.

**Zeitachsen-Narrativ und Quellenverknüpfung (im Detail).** Die Timeline ist kein Filter, sondern ein Lesepfad: Ereignisse sind durch verbindende Segmente verkettet, die die vermutete Beziehung andeuten (zeitliche Folge, nicht behauptete Kausalität — Kausalität ist Sektion F vorbehalten). Jeder Erzählabsatz trägt am Rand die Quell-Chips, aus denen er stammt; Tap auf einen Chip öffnet die Originalquelle (Alarm, Sensorfenster, Notiz) in einem Seitenpanel, ohne den Lesefluss zu verlassen. **Belegt vs. erzählt** ist visuell hart getrennt: belegte Fakten in normaler Schrift mit Quell-Chip, die verbindende Erzählung in einer abgesetzten, als „rekonstruiert" gekennzeichneten Darstellung. So bleibt für den Schichtleiter jederzeit erkennbar, was Datum ist und was Deutung.

**Interaktionsmodell.** *Ein:* Anker setzen (Maschine + Zeitfenster + Auslöse-Ereignis) → „Kette rekonstruieren" (On-Demand-Trigger); gespeicherte Ketten abrufen; Quell-Chips öffnen; Schwesterketten vergleichen; Kette an die Maschinen-Zeitachse (B) anpinnen. *Aus:* nach Trigger benannter Verarbeitungszustand („verknüpfe Ereignisse über die Klasse…"), dann Erzählung mit Herkunftsstempel (Stand, einbezogene Quellen). Zustandsübergänge: leer → rekonstruiert → gespeichert.

**Visuelle Kodierung.** Quelltypen formcodiert (gleiche Symbole wie B-Marker — Konsistenz, Prinzip 2). Belegt = solide, erzählt = abgesetzt/kursiv mit Kennzeichnung. Keine Severity-Farbe in der Erzählung; Farbe nur an den verlinkten Original-Alarmen. Dezente Verbindungslinien, keine animierten „Fließeffekte".

**Rollenspezifische Varianten.** Schichtleiter: rekonstruiert aktiv (Trigger). Techniker: liest für Diagnose, pinnt an die Maschine. Werker: liest gespeicherte Ketten. Manager: liest verdichtete Zusammenfassung (ein Satz + Kennzahl), nicht die volle Erzählung.

**Verbindung zu anderen Sektionen.** Anker kommt oft aus C (Alarm) oder B (Achsen-Marker). Schwesterkette ↔ A (Klasse) und H (Gedächtnis). Ergebnis pinnbar in B. Mündet bei wiederkehrendem Muster in F (Wartungskausalität).

---

### E. Ausfallvorhersage & Empfehlung · [STEHT]

**Reifegrad.** [STEHT] — voll ausgestalten, aber unter dem schärfsten der drei bleibenden Haltungen: der **Simulations-Vorbehalt** ist hier untrennbarer Bestandteil, kein Beiwerk.

**Zweck und Leitfrage.** *„Wie wahrscheinlich ist ein Ausfall, warum, was soll ich tun — und wie sehr darf ich dieser Zahl trauen?"*

**Informationsarchitektur.** Vier untrennbar zusammengehörige Blöcke in fester Reihenfolge: (1) **Wahrscheinlichkeit/Konfidenz**, (2) **Einflussfaktoren** (die Haupttreiber der Vorhersage, in Werker-Sprache — die zugrunde liegende Faktor-Methode wird *nicht* benannt), (3) **Werker-Empfehlung** (konkrete Handlung), (4) **Vorbehalt-Block** (Datenbasis, Validierungsstatus, Grenzen). Block 4 ist nie wegklappbar, nie unter „mehr". Reihenfolge ist Pflicht: Zahl → Warum → Tu-das → Aber-bedenke.

**Layout-Konzept.** Einspaltige, gut lesbare Karte (kein Dashboard-Gewimmel — das hier ist eine Entscheidung, keine Übersicht). Oben die Konfidenz-Darstellung als Ankerelement. Darunter die Einflussfaktoren als geordnete Liste mit Richtungs- und Stärkeangabe. Darunter die Empfehlung als klar abgesetzter Handlungsblock. Darunter, **gleichwertig und visuell verbunden** (gemeinsamer Rahmen, nicht abgetrennt nach unten verbannt), der Vorbehalt-Block. Leserichtung strikt vertikal, oben→unten = Zahl→Begründung→Handlung→Vorbehalt.

**Konfidenz-Darstellung und Vorbehalt-Integration (im Detail).** Die Wahrscheinlichkeit wird **nicht als Scheingenauigkeit** (z. B. „87,3 %") gezeigt, sondern als **Wahrscheinlichkeitsband mit Unsicherheitsbreite** plus eine grobe verbale Stufe („erhöht", „hoch") — ehrliche Unsicherheit ist 6.0. Ein breites Band signalisiert mehr Unsicherheit visuell, nicht nur numerisch. Die **Einflussfaktoren** zeigen je Treiber Richtung (treibt hoch/runter) und relatives Gewicht als Balken, mit Werker-Label (z. B. „Lagertemperatur über Normalband seit 3 Schichten") — die mathematische Faktor-Zerlegung dahinter bleibt unbenannt im UI. Der **Vorbehalt-Block** ist farblich und durch ein festes Symbol als Dauerbestandteil markiert; er nennt: Datenbasis (z. B. „beruht auf Simulationsdaten, nicht auf Feldvalidierung"), Validierungsstatus, und was die Zahl *nicht* bedeutet. Designregel: Konfidenz und Vorbehalt teilen sich einen Rahmen; man kann das eine nicht sehen, ohne das andere zu sehen. Die Empfehlung ist immer als *Vorschlag an den Menschen* formuliert, nie als Befehl, und nie mit einer Schalt-Aktion verknüpft (HITL).

**Interaktionsmodell.** *Ein:* Vorhersage für Maschine anfordern (Trigger, Schichtleiter); Einflussfaktor antippen → Sprung zum belegenden Sensorverlauf (B); Empfehlung quittieren/verwerfen mit Begründung. *Aus:* benannter Verarbeitungszustand, dann die Vier-Block-Karte mit Herkunftsstempel. Zustandsübergänge: angefordert → Ergebnis → vom Menschen entschieden (quittiert/verworfen, im Audit sichtbar).

**Visuelle Kodierung.** Konfidenzband in einer einzigen, ruhigen Farbe mit sichtbarer Breite; keine Ampel-Dramatik. Einflussfaktor-Richtung durch Pfeil/Position, Stärke durch Balkenlänge (farbunabhängig lesbar). Vorbehalt in einer festen, ruhigen Signalfarbe (nicht Alarm-Rot — es ist kein Alarm, sondern Ehrlichkeit) mit konstantem Symbol. Keine Animation, die Dringlichkeit suggeriert.

**Rollenspezifische Varianten.** Werker: liest Empfehlung + Vorbehalt, klar und knapp, ohne Trigger. Schichtleiter: fordert an, quittiert. Techniker: liest mit Faktor-Detail für die Diagnose. Manager: aggregiertes Risikobild über Maschinen, nie die Einzelempfehlung als Befehl.

**Verbindung zu anderen Sektionen.** Einflussfaktor → B (Sensorbeleg). Auslöser oft aus C (Alarm) oder A (Drift). Mündet in F (welche Wartung senkt dieses Risiko?). Quittier-/Verwerf-Entscheidung → Audit (I). Ähnliche Vorfälle → H.

---

### F. Wartungszyklen · [VISION, Reasoner #4]

**Reifegrad.** [VISION] — kausale Auswertung als Zielbild. Gestalterisch: die Sicht wird so entworfen, dass sie auch mit dünner Datenlage einen ehrlichen, nützlichen Stand zeigt („noch zu wenig Historie für belastbare Aussage") statt eine Scheinpräzision. Kausalität wird als *Hypothese mit Stärke* dargestellt, nie als bewiesene Wahrheit.

**Zweck und Leitfrage.** *„Welche Wartung wirkt wirklich — und wann ist das optimale Intervall, statt nach Kalender oder Bauchgefühl?"*

**Informationsarchitektur.** Zwei Stränge: (1) **Wirkungsanalyse** — welche Wartungsmaßnahme korreliert mit welcher Verbesserung (Standzeit, Driftrückgang, Ausfallreduktion), als kausale Hypothese mit Stärkegrad; (2) **Intervall-Optimierung** — empfohlenes Intervall gegen aktuelles Intervall, mit erwarteter Wirkung und Unsicherheit. Dazu Planungsblick: anstehende Wartungen je Maschine/Linie.

**Layout-Konzept.** Dreizonig. Links **Maßnahmen-Wirkungs-Liste** (Wartungstyp → Wirkungsstärke-Balken → Konfidenz). Mitte **Intervall-Achse**: eine horizontale Skala je Wartungstyp mit aktuellem Intervall (Marker), empfohlenem Intervall (zweiter Marker) und einem Wirkungs-/Risikoverlauf darüber (zu früh = unnötig teuer, zu spät = Ausfallrisiko steigt). Rechts **Planungsblick** (kommende Wartungen). Ankerelement ist die Intervall-Achse. Leserichtung: Wirkung (links) → Intervall (Mitte) → Plan (rechts).

**Kausalitäts-Visualisierung und Intervall-Optimierung (im Detail).** Kausalität wird als **gerichtete Beziehung „Maßnahme → Wirkung" mit Stärke und Unsicherheit** gezeigt, bewusst zurückhaltend: ein Balken für die geschätzte Wirkung, ein Unsicherheitsband, ein Klartext-Satz („Schmierung alle 2 Wochen senkt die Lagertemperatur-Drift deutlich; mittlere Belegstärke"). Es gibt einen festen Ehrlichkeits-Marker, der *Korrelation aus Beobachtung* von *belastbarer kausaler Aussage* trennt — die Sicht behauptet nie mehr, als die Datenlage trägt. Die **Intervall-Optimierung** ist eine Kurve über der Zeitachse: erwartete Gesamtkosten/Risiko als Funktion des Intervalls mit einem markierten Optimum; der Nutzer sieht, *warum* das empfohlene Intervall besser ist (Schnittpunkt zweier gegenläufiger Kurven: Wartungsaufwand vs. Ausfallrisiko). Auch hier: Empfehlung, kein Automatismus — die Plattform plant nichts selbst um.

**Interaktionsmodell.** *Ein:* Wartungstyp wählen (Trigger Wirkungsanalyse), Intervall-Szenario durchschieben, Empfehlung in die Planung übernehmen (als Vorschlag, der von einem Menschen bestätigt wird). *Aus:* On-Demand-Ergebnis mit Herkunft + Belegstärke. Zustandsübergänge: angefordert → Hypothese → vom Planer übernommen/verworfen.

**Visuelle Kodierung.** Wirkungsstärke als Balken, Unsicherheit als Band — farbunabhängig. Optimum als klarer Marker, nicht als grelle Farbe. Aktuelles vs. empfohlenes Intervall durch zwei unterscheidbare Marker (Form, nicht nur Farbe). Belegstärke als diskrete Stufung (niedrig/mittel/hoch) mit Symbol.

**Rollenspezifische Varianten.** Manager/Schichtleiter: planen, sehen Kosten-/Intervallblick. Techniker: führt aus, hakt ab, sieht die nächste fällige Maßnahme. Werker: liest Anstehendes für seine Maschine.

**Verbindung zu anderen Sektionen.** Wirkung speist sich aus B (Verlauf), C (Alarme), D (Ketten). Senkt das Risiko aus E. Plan ↔ Wartungshistorie in B. Muster ↔ H.

---

### G. Belastungs-Simulation · [VISION, Reasoner #5]

**Reifegrad.** [VISION] — und die **einzige Sektion, in der der Werker durchspielt statt nur liest**. Gestalterisch ist das die didaktischste, „spielerischste" Sicht — aber spielerisch im Sinn von *gefahrlos erkundbar*, nicht verspielt-dekorativ. Klare Grenzen, ehrliche Herkunft (Folgen aus historischen Maxima), kein Eindruck, man steuere die echte Anlage.

**Zweck und Leitfrage.** *„Was passiert, wenn ich diese Maschine an ihre Lastgrenze fahre — virtuell, ohne Risiko?"*

**Informationsarchitektur.** Eingang: **Last-Parameter** (z. B. Drehzahl, Durchsatz, Temperatur-Vorgabe) als Slider mit klar markierten Normalbereich- und Grenzwert-Zonen. Ausgang: **prognostizierte Folgen** (Sensorreaktionen, Belastung, Ausfallrisiko), abgeleitet aus historischen Maxima dieser Maschine/Klasse. Dazu Szenario-Vergleich (mehrere Einstellungen nebeneinander).

**Layout-Konzept.** Zweigeteilt: oben/links das **Steuerpult** (Slider, groß, handschuhsicher), unten/rechts die **Folgen-Visualisierung** (Reaktionskurven + Grenzwert-Linien + Risiko-Anzeige), die live auf Slider-Bewegung reagiert. Darunter eine **Szenario-Leiste** (gespeicherte Einstellungen als Chips zum Vergleich). Ankerelement ist die Slider→Folgen-Kopplung — Eingabe und Wirkung müssen gleichzeitig im Blick sein. Mobil: Slider oben, Folgen direkt darunter, Szenarien als horizontale Chip-Reihe.

**Slider-Interaktion, Szenario-Vergleich, Grenzwert-Visualisierung (im Detail).** Die **Slider** sind groß (Track-Höhe und Griff handschuhtauglich, Griff ≥ 64 px) und tragen drei markierte Zonen: Normalbereich (neutral), Annäherung an die Grenze (Warnzone), jenseits historischer Maxima (extrapoliert — sichtbar als „über belegtem Bereich, Aussage unsicherer"). Bewegt der Nutzer den Slider, reagieren die **Folgenkurven live**; an der **Grenzwert-Linie** kippt die Darstellung sichtbar (die Linie ist fett, beschriftet, und die Kurve, die sie überschreitet, wechselt in die Warn-Kodierung). **Extrapolation jenseits der Maxima** wird ehrlich als unsicherer gekennzeichnet (gestrichelt, mit Vorbehalt-Hinweis — verwandt mit dem E-Vorbehalt). **Szenario-Vergleich:** der Nutzer friert eine Einstellung als Chip ein und legt eine zweite daneben; die Folgenkurven werden überlagert (mit Differenz-Hervorhebung), sodass „Einstellung A vs. B" direkt ablesbar ist. Wichtig: ein dauerhaftes, ruhiges Label „Simulation — beeinflusst die reale Anlage nicht" verankert, dass hier nichts geschaltet wird (HITL/Sicherheit).

**Interaktionsmodell.** *Ein:* Slider schieben, Szenario einfrieren/vergleichen, Grenzwert-Detail antippen. *Aus:* live berechnete Folgen (On-Demand-Reasoner, aber interaktiv-kontinuierlich statt einmaliger Trigger). Zustandsübergänge: Eingabe → Folgen → Szenario gespeichert.

**Visuelle Kodierung.** Normal/Warn/Extrapoliert als Zonen (Fläche + Label + Muster, nicht nur Farbe). Grenzwert-Linie als stärkstes grafisches Element. Szenario-Chips farblich unterscheidbar, aber gedämpft. Bewegung ist hier funktional (Kurve folgt Slider) — das ist die eine Sektion, in der kontinuierliche Animation richtig ist, weil sie die Ursache-Wirkung sichtbar macht; `prefers-reduced-motion` ersetzt sie durch diskrete Schritt-Updates.

**Rollenspezifische Varianten.** Werker/Schichtleiter/Techniker: voll durchspielen (das ist der Sinn der Sektion). Werker bekommt eine geführtere Variante mit stärker markierten Grenzen. Manager: liest gespeicherte Szenario-Ergebnisse, spielt nicht selbst.

**Verbindung zu anderen Sektionen.** Maximalwerte und Reaktionsprofile aus B. Risiko-Logik verwandt mit E. „Was wäre wenn" speist Wartungsplanung F. Auffällige Szenarien als Notiz nach J / Wissen nach H.

---

### H. Gedächtnis & Verknüpfung · [KERN STEHT]

**Reifegrad.** [KERN STEHT] — semantische Suche steht im Kern; die volle klassen- und werksübergreifende Breite ist Vision. Gestalterisch: Gedächtnis ist ein **eigener, begehbarer Raum**, nicht ein Suchfeld in der Ecke. Das ist die sichtbarste Verkörperung des 6.0-Sprungs.

**Zweck und Leitfrage.** *„Hatten wir das schon mal — irgendwo, an irgendeiner Maschine, in irgendeiner Schicht?"*

**Informationsarchitektur.** Eine **Bedeutungssuche** über Notizen, Vorfälle, Ketten — nicht Stichwort-Matching, sondern „ähnliche Situationen". Treffer sind heterogen (Notiz, Alarm, Kette, Wartung) und tragen je: Quelle, Maschine/Klasse, Zeit, Ähnlichkeitsgrund („ähnlich, weil …"). Gruppierung nach Relevanz, filterbar nach Klasse/Werk/Zeit. Die **Verknüpfung** ist das Besondere: Treffer werden nicht nur gelistet, sondern in Beziehung gezeigt (gleiche Klasse, gleiche Wurzelursache, zeitliche Nähe).

**Layout-Konzept.** Oben eine große, einladende **Suchzeile** (Freitext, „beschreibe die Situation") — bewusst prominent, weil sie das Tor zum Raum ist. Darunter zweispaltig: links die **Trefferliste** (heterogene Karten mit Quelltyp-Symbol, Maschine/Klasse, Zeit, Ähnlichkeitsbegründung), rechts eine **Verknüpfungs-Ansicht** (wie die Treffer zusammenhängen — als kompakte Beziehungsdarstellung, nicht als wilder Graph). Leserichtung: Suche → Treffer → Beziehungen. Mobil: Suche + Trefferliste, Verknüpfung als aufklappbares Detail je Treffer.

**Suchinteraktion und Verknüpfungslogik (im Detail).** Die Suche akzeptiert natürliche Beschreibung („Lager läuft heiß nach Schichtwechsel") und liefert bedeutungsähnliche Fälle, auch wenn die Worte nicht übereinstimmen. Jeder Treffer **begründet seine Ähnlichkeit** in einem Satz (Transparenz statt Blackbox). Filter sind als Chips über der Liste (Klasse, Werk, Zeitraum, Quelltyp). Die **Verknüpfungslogik** verbindet Treffer über drei Beziehungstypen: gleiche Maschinenklasse (Schwestermaschine), gemeinsame vermutete Wurzelursache, zeitliche/kontextuelle Nähe — jeweils farbunabhängig durch Label und Anordnung markiert. Ein Treffer ist Sprungbrett: er öffnet die Originalquelle und bietet „dazu Ereigniskette rekonstruieren" (D) oder „an Maschine anpinnen" (B). Wichtig fürs Wording: die Sicht spricht von „ähnlichen Fällen" und „Verknüpfung", nicht vom inneren Mechanismus der Gedächtnisschicht — Paraphrase-Disziplin.

**Interaktionsmodell.** *Ein:* suchen (Trigger, On-Demand), filtern, Treffer öffnen, verknüpfen, weiterspringen (D/B/J). *Aus:* benannter Suchzustand („suche ähnliche Fälle über die Klasse…"), dann Treffer mit Ähnlichkeitsbegründung und Herkunft. Zustandsübergänge: leer → Treffer → Sprung in Quelle/Folgesektion.

**Visuelle Kodierung.** Quelltypen formcodiert (konsistent mit B/D). Ähnlichkeitsgrad als dezente Stufung (kein lauter Score). Beziehungstypen durch Anordnung/Label, nicht durch Regenbogenfarben. Ruhig, lesefreundlich, textbetont — das ist ein Lese-/Denkraum, kein Alarmraum.

**Rollenspezifische Varianten.** Alle Rollen suchen. Werker: einfache Suche + lesen, große Treffer-Karten. Schichtleiter/Techniker: volle Filter, Verknüpfung, Sprung in Diagnose. Manager: thematische Suche über Werke (Muster), weniger Einzelfall.

**Verbindung zu anderen Sektionen.** Erreichbar von überall (globale Befehlsleiste). Treffer → B, D, J. Klassen-Muster ↔ A. Speist Kontextvorschläge in J und Schwesterketten in D.

---

### I. Integrations-/Plattformsicht · [VISION, F7 MCP]

**Reifegrad.** [VISION] — macht „Plattform statt App" sichtbar. Gestalterisch: eine ruhige, vertrauensbildende Administrations-/Audit-Sicht, kein operativer Hallen-Screen. Sie zeigt das Nervensystem, nicht den Betrieb.

**Zweck und Leitfrage.** *„Mit welchen Drittsystemen ist die Plattform verbunden, was fließt woher, und ist jede abgerufene Erkenntnis nachvollziehbar?"*

**Informationsarchitektur.** Zwei Teile: (1) **Systemtopologie** — FOREMAN im Zentrum, ringsum die angebundenen Drittsysteme (ERP, Simulationssoftware, Energiemanagement u. a.) mit Verbindungsstatus und Datenrichtung; (2) **Audit-Blick** — ein nachvollziehbares Protokoll, wer/welches System wann welche Erkenntnis abgerufen oder welche Aktion (z. B. Quittierung) ausgelöst hat. Gruppierung der Topologie nach Systemtyp, des Audits chronologisch/filterbar.

**Layout-Konzept.** Oben/Mitte die **Topologie** als zentrierte Darstellung (FOREMAN-Knoten in der Mitte, Drittsysteme als umgebende Knoten, Verbindungen mit Status und Richtungspfeil — ruhig, nicht animiert). Darunter der **Audit-Trail** als filterbare, chronologische Liste (Zeit, Akteur/System, Aktion, betroffene Maschine/Erkenntnis, Ergebnis). Leserichtung: Topologie (Lagebild) → Audit (Nachweis). Ankerelement ist die Topologie.

**Systemtopologie und Audit-Trail (im Detail).** Die Topologie zeigt je Verbindung: Systemname, Typ, Status (verbunden / gestört / inaktiv — FCSM-ähnlich, konsistent), Datenrichtung (liest FOREMAN / liefert an FOREMAN / beides), letzte Aktivität. Ein gestörter Konnektor ist klar markiert, aber ruhig (kein Alarm-Drama — das ist Admin-Kontext). Der **Audit-Trail** ist die Vertrauens-Substanz der Plattform: jede abgerufene Erkenntnis und jede menschliche Entscheidung (Quittierung, Verwerfung, Plan-Übernahme) erscheint als unveränderliche Zeile mit Herkunft. Das ist gleichzeitig AI-Act-Transparenz (nachvollziehbarer KI-Einsatz) und Security-Nachweis (keine stillen Schreibpfade). Filter nach System, Maschine, Akteur, Aktionstyp, Zeit.

**Interaktionsmodell.** *Ein:* Konnektor antippen (Detail/Status), Audit filtern/durchsuchen, einzelne Audit-Zeile öffnen (volle Herkunft). *Aus:* überwiegend lesend; Status der Topologie wird live aktualisiert, der Audit-Trail wächst chronologisch. Zustandsübergänge: Konnektor verbunden↔gestört sichtbar.

**Visuelle Kodierung.** Verbindungsstatus farb- **und** formcodiert (konsistent FCSM). Datenrichtung durch Pfeilform. Audit ruhig, monospace-betonte IDs für Nachvollziehbarkeit. Keine Spielereien — Vertrauen entsteht durch Nüchternheit.

**Rollenspezifische Varianten.** Manager/Admin: volle Topologie + Audit. Schichtleiter: liest nur Verbindungsstatus (betrifft seine Datenqualität). Werker/Techniker: kein Zugang (3.1).

**Verbindung zu anderen Sektionen.** Audit referenziert Entscheidungen aus C (Quittierung), E/F (Übernahme von Empfehlungen). Datenquellen der Topologie speisen B/A. „Plattform statt App" ist hier das sichtbar gemachte Gegenstück zur Föderation in A.

---

### J. Eingabe & Erfassung · [CRUD STEHT, Sprache VISION]

**Reifegrad.** [CRUD STEHT, Sprache VISION] — die Werkernotiz (Freitext, Schicht, Maschine) ist voll baubar; Spracheingabe ist der Ausbau. Gestalterisch: das Formular wird heute reibungsarm und feldtauglich gebaut, die Sprach-UI als nahtlose Erweiterung desselben Erfassungsflusses entworfen (nicht als zweite, getrennte App).

**Zweck und Leitfrage.** *„Wie bekomme ich, was ich gerade sehe, in unter 15 Sekunden korrekt zugeordnet ins System?"*

**Informationsarchitektur.** Eine Notiz besteht aus: Freitext (Kern), Maschine/Linie (Zuordnung), Schicht (Kontext), optional Schweregrad/Kategorie. Maximale Vorbelegung aus dem Kontext: kommt die Erfassung aus einer Maschinensicht, ist Maschine/Schicht vorausgefüllt. Hierarchie: Freitext zuerst (das Wichtigste), Zuordnung minimiert durch Vorbelegung, Rest optional.

**Layout-Konzept.** Fokussiertes, einspaltiges Formular. Oben groß das **Freitextfeld** (oder der Sprach-Aufnahmeknopf — beide gleichberechtigt nebeneinander). Darunter die **Zuordnungs-Chips** (Maschine, Schicht) — vorausgefüllt, ein Tap zum Ändern. Darunter optionale Felder, eingeklappt. Unten, im Daumenbogen, der große **Speichern**-Button (≥ 64 px). Auf Mobil ist genau das die ganze Sicht — eine Aufgabe, ein Screen. Die Schnellerfassung (Floating Action) öffnet genau dieses Formular mit maximalem Kontext.

**Eingabeformulare, Sprach-UI-Konzept, Kontextvorschläge (im Detail).** **Formular:** so wenig Pflichtfelder wie möglich; Zuordnung per vorausgefüllten Chips statt Dropdown-Suche; Eingabe wird **lokal sofort gespeichert** (Offline-Toleranz) und synchronisiert nachträglich, mit sichtbarem Sync-Status („gespeichert · synchronisiert" / „gespeichert · wartet auf Netz"). **Sprach-UI (Vision):** ein großer Aufnahmeknopf startet die Diktatfunktion; während der Aufnahme zeigt eine ruhige Pegel-/Transkriptanzeige, dass zugehört wird; nach Stopp erscheint der **transkribierte Text editierbar** (nie blind übernehmen — der Werker bestätigt). Aus dem Diktat werden Maschine/Schicht als Vorschlag erkannt und als Chips zur Bestätigung angeboten. Wichtig (Sicherheit/Datenschutz): personenbezogene Inhalte werden **im Backend maskiert** — das UI macht transparent, dass Namen/IDs vor Speicherung geschützt werden, ohne dem Werker zusätzliche Arbeit aufzubürden. **Kontextvorschläge:** während der Eingabe bietet die Sicht dezent passende frühere Fälle an („ähnliche Notiz an dieser Maschine vor 3 Wochen") — eine Brücke zu H, die das Erfassen mit dem Gedächtnis verbindet, ohne aufdringlich zu sein (Vorschlag, kein Pop-up-Zwang).

**Interaktionsmodell.** *Ein:* tippen oder diktieren, Zuordnung bestätigen/ändern, speichern. *Aus:* sofortige lokale Bestätigung + Sync-Status; Kontextvorschläge erscheinen passiv. Zustandsübergänge: Entwurf → lokal gespeichert → synchronisiert; Sprache: Aufnahme → Transkript → bestätigt.

**Visuelle Kodierung.** Sehr ruhig, hoher Kontrast, große Touch-Ziele. Sync-Status als kleines, klares Symbol (kein Alarm-Rot für „wartet auf Netz" — das ist normal). Sprach-Pegel als dezente, nicht-dramatische Bewegung. Kontextvorschläge optisch klar als sekundär (gedämpft, abgesetzt).

**Rollenspezifische Varianten.** Werker: primäre, geführte Erfassung, größte Ziele, Sprache zuerst angeboten. Techniker: mobil erfassen, einhändig, im Feld. Schichtleiter: erfassen + frühere Notizen sichten/kommentieren. Manager: liest, erfasst nicht.

**Verbindung zu anderen Sektionen.** Notiz erscheint als Marker in B (Zeitachse) und als Quelle in D (Ketten) und H (Suche). Kontextvorschlag zieht aus H. Erfassung ist von überall über die persistente Schnellaktion erreichbar.

---

## 5. Design System und Component Library

### 5.1 Technologie-Architektur

**Framework-Empfehlung: React über Next.js — begründet, nicht gesetzt.**

Die GROUND_TRUTH legt React/Next.js fest; diese Studie stützt das, weil die Begründung aus dem Lastprofil folgt, nicht aus Konvention. Der Vergleich gegen Angular, ehrlich geführt:

| Kriterium | React/Next.js | Angular | Für FOREMAN entscheidend |
|---|---|---|---|
| Echtzeit-Vielfalt (viele heterogene Streaming-Sichten) | feinkörnige Komponenten, reifes Streaming-/State-Ökosystem | starkes RxJS-Streaming, aber schwerer pro Kleinsicht | **React** — FOREMAN hat viele kleine, schnell iterierte Spezialsichten |
| Virtualisierung großer Listen (Alarme, Treffer) | erstklassige Bibliotheken | vorhanden, weniger Auswahl | **React** |
| WebGL-Bridge (A-Heatmap, G-Simulation) | nahtlose Three.js-/Canvas-Einbindung | möglich, mehr Reibung | **React** |
| Offline/Schwachnetz (Sync, Service Worker) | breites Ökosystem, Next.js-Kontrolle über Rendering | solide, aber starrer | **React** |
| Erzwungene Struktur im Team | erfordert Disziplin (Risiko) | eingebaut (Vorteil) | Angular-Pluspunkt — durch Konventionen aufgefangen |
| Bundle-Gewicht (Schwachnetz) | gut kontrollierbar (Code-Splitting, RSC) | tendenziell schwerer | **React** |

Der einzige echte Angular-Vorteil (erzwungene Struktur) wird durch das Architektur-Regelwerk dieser Studie und TypeScript-strict aufgefangen. Reacts Stärke bei genau den vier kritischen Bauteilen (Streaming-Vielfalt, Virtualisierung, WebGL, Offline) ist für FOREMAN ausschlaggebend.

**Echtzeitdaten-Architektur.** Die tragende Entscheidung ist die **strikte Entkopplung von Datenlogik und Visualisierung** — das ist der einzige Weg, mit dem Reacts Freiheit nicht in Chaos kippt:

- **Transport:** WebSocket für Push-Sichten (A, B-Trend, C, globale Leiste); ein einziger, gemultiplexter Verbindungskanal mit Themen-Abonnements (pro Maschine/Bereich), nicht ein Socket pro Kachel. Request/Response (HTTP) für On-Demand-Erkenntnisse (D–H). Adaptive Push-Rate: bei Schwachnetz drosselt der Server die Update-Frequenz, das UI bleibt stabil.
- **State-Schichtung:** drei getrennte Ebenen — **Server-/Stream-State** (eingehende Live-Daten, in einer dedizierten Streaming-State-Schicht gepuffert und gedrosselt), **abgeleiteter View-State** (Selektoren/Transformationen, memoisiert), **lokaler UI-State** (Auswahl, Filter, Zoom — in der Komponente). Visualisierungskomponenten lesen nur aus der abgeleiteten Ebene und kennen den Transport nicht. So ist eine Chart-Komponente gegen WebSocket, gecachte Daten oder Simulationswerte austauschbar testbar.
- **Offline/Resilienz:** Service-Worker-Cache je Sicht mit sichtbarem „Stand"-Stempel; Erfassung (J) schreibt in eine lokale Queue und synchronisiert nachträglich; Live-Sichten frieren bei Verbindungsverlust ein statt zu leeren.
- **Backpressure/Virtualisierung:** Alarmlisten und Suchtreffer sind virtualisiert (nur Sichtbares im DOM); Streamdaten werden auf Anzeigeauflösung downgesampelt, bevor sie die Charts erreichen (kein 1000-Punkte-Rerender pro Sekunde).

**WebGL/Three.js — wo und warum.** Zwei Einsatzorte, nicht mehr: (1) **A-Drift-Heatmap** über viele Maschinen — bei großer Föderation rendert SVG/DOM zehntausende Zellen nicht flüssig; WebGL hält die Heatmap interaktiv. (2) **G-Belastungs-Simulation** — kontinuierliche, slider-gekoppelte Folgenkurven mit Überlagerung profitieren von GPU-Rendering. Überall sonst (B-Trends, C-Liste, D-Timeline, E-Karte) ist SVG/Canvas-Charting richtig: barriereärmer, einfacher, wartbarer, druck-/screenshot-fähig für Reports. Regel: WebGL nur, wo DOM nachweislich an die Performancegrenze kommt.

**Electron — wo und warum.** Eng umrissen: (1) **Leitstand-Kiosk** — ein dedizierter Leitstand-Rechner soll FOREMAN als Vollbild-Anwendung ohne Browser-Chrome, mit kontrolliertem Auto-Restart und lokalem Zwischenspeicher fahren; Electron liefert das Kiosk-Gehäuse. (2) **Service-Laptop mit hartem Offline-Anspruch** — wo ein Techniker garantiert ohne Netz arbeiten muss, gibt Electron tieferen lokalen Speicher und OS-Integration als der reine Browser. **Nicht** für Tablet/Mobil (dort PWA — installierbar, offlinefähig, leichter) und **nicht** als Default-Auslieferung. Der Web-Build bleibt die Quelle; Electron ist nur eine Verpackung desselben Codes für zwei Spezialfälle.

### 5.2 Farbsystem

Das Farbsystem ist die schärfste Umsetzung von ISA-101: **entsättigte Grundfläche, Farbe nur für Bedeutung.** Primärmodus ist Dark (Halle), mit einem gleichwertigen High-Contrast-Light-Modus (Streulicht). Alle Werte sind als Design-Tokens organisiert (5.7), hier mit Beispiel-Hex für den Dark-Modus.

**Neutrale UI-Palette (Grundfläche, ~90 % der Pixel).** Entsättigte, leicht kühle Grautöne — die ruhige Bühne, gegen die Farbe wirkt.

| Token | Dark (Beispiel) | Verwendung |
|---|---|---|
| `surface/canvas` | `#15181C` | Haupt-Hintergrund |
| `surface/raised` | `#1C2025` | Karten, Panels |
| `surface/overlay` | `#23282E` | Dialoge, Seitenpanels |
| `border/subtle` | `#2C3239` | Trennlinien |
| `border/strong` | `#3A424B` | Aktive Ränder |
| `text/primary` | `#E8ECEF` | Haupttext (≥ 12:1 auf canvas) |
| `text/secondary` | `#A7B0B8` | Sekundärtext (≥ 7:1) |
| `text/muted` | `#7C858D` | Tertiär/Hinweis (≥ 4.5:1) |

**Alarmstufen-Palette (ISA-18.2-Prioritäten).** Gestuft, nicht „alles rot". Jede Stufe hat Farbe **plus** Form/Position/Label (Prinzip 8).

| Priorität | Token | Dark (Beispiel) | Einsatzregel |
|---|---|---|---|
| Kritisch | `alarm/critical` | `#E5484D` | Einzige vollflächig erlaubte Alarm-Farbe; sparsam |
| Hoch | `alarm/high` | `#F2820D` | Akzent/Rand, keine Vollfläche |
| Mittel | `alarm/medium` | `#E8C500` | Punkt/Rand, gedämpft |
| Niedrig | `alarm/low` | `#5B8DEF` | dezent, informativ |
| Diagnose/Journal | `alarm/journal` | `#7C858D` | neutral, kein Farbgewicht |

**Zustands-Palette (NAMUR NE 107 FCSM).** Das im Feld gelernte Vokabular — kanonisch über alle Sektionen.

| Status | Token | Dark (Beispiel) | Bedeutung |
|---|---|---|---|
| Failure (F) | `state/failure` | `#E5484D` | Ausfall, sofortige Aktion |
| Function check (C) | `state/check` | `#F2820D` | Funktionsprüfung läuft |
| Out of spec (S) | `state/outofspec` | `#E8C500` | außerhalb Spezifikation |
| Maintenance (M) | `state/maintenance` | `#5B8DEF` | Wartung erforderlich |
| Normal/OK | `state/ok` | `#3BA776` | Normalbetrieb (gedämpftes Grün, nie dominant) |

**Daten-/Visualisierungs-Palette.** Sensorlinien und neutrale Datenreihen nutzen **entsättigte, kategorial unterscheidbare Neutraltöne** — bewusst *keine* semantischen Farben, damit Status-Farbe ihre Bedeutung behält. Driftstärke/Heatmap: eine **sequenzielle einfarbige Skala** (hell→intensiv eines Tons), nie Regenbogen (Regenbogen zerstört die wahrgenommene Ordnung und ist farbsehschwäche-feindlich). Differenz-/Über-/Unterschreitung: zwei gegensätzliche, farbsehschwäche-sichere Töne (z. B. Blau↔Orange) plus Schraffur.

**Kontrast- und Theming-Regeln.** Status-Text ≥ 7:1, Körpertext ≥ 4.5:1, grafische/Bedien-Elemente ≥ 3:1 (WCAG 1.4.11) — FOREMAN nimmt durchgehend den strengeren Wert. Der **Vorbehalt** (E) hat eine eigene, ruhige Signalfarbe, die **nicht** Alarm-Rot ist (es ist kein Alarm, sondern Ehrlichkeit) — Vorschlag: ein gedämpftes Violett/Indigo `note/caveat #8B7CE5`, konsistent mit dem festen Vorbehalt-Symbol. Der Light-Modus invertiert nicht naiv, sondern ist eine eigene, geprüfte Palette mit denselben Kontrastzielen. Jede Farbe ist gegen Deuteranopie/Protanopie geprüft; kein Bedeutungsträger lebt allein von Rot/Grün.

### 5.3 Typografie

Industrielle Lesbarkeit auf Distanz und im Streulicht verlangt eine humanistische, offene Grotesk mit klaren Zahlen — keine geometrische Mode-Schrift mit engen Punzen.

- **UI-Schrift:** eine gut lesbare humanistische Sans (Empfehlung: *Inter* oder gleichwertig) mit **Tabellenziffern** (`font-feature-settings: "tnum"`) für alle Messwerte — damit Live-Werte beim Update nicht horizontal springen.
- **Mono-Schrift:** eine echte Monospace (Empfehlung: *IBM Plex Mono* / *JetBrains Mono*) für IDs, Audit-Zeilen, technische Identifier — Nachvollziehbarkeit durch feste Zeichenbreite.
- **Type-Scale (Dark, Leitstand-Basis):** untere Grenze in der Halle ist **14 px**, nie darunter.

| Stufe | Größe / Zeilenhöhe | Verwendung |
|---|---|---|
| Display / KPI | 48–72 px / 1.0 | Cockpit-KPIs, große Statuszahlen (Distanz) |
| H1 | 28 px / 1.2 | Sicht-Titel |
| H2 | 22 px / 1.25 | Sektionsüberschrift |
| Body-L | 18 px / 1.4 | Leitstand-Körpertext (Distanz) |
| Body | 16 px / 1.45 | Standard |
| Caption | 14 px / 1.4 | Achsenlabel, Metadaten (Minimum) |
| Mono | 14–16 px | IDs, Audit, Werte |

- **Gewichte:** maximal drei (Regular / Medium / Semibold) — Hierarchie über Größe und Gewicht, nicht über Farbe. Werte in Medium mit Tabellenziffern, Labels in Regular.
- **Zeilenlänge:** Erzähltexte (D, E, H) auf 60–75 Zeichen begrenzt; Tabellen/Listen ungebunden.

### 5.4 Raster, Spacing und Dichte

- **Basisraster:** 8-px-System mit 4-px-Subraster für Feinjustage. Alle Abstände sind Vielfache.
- **Layout-Raster:** 12 Spalten am Leitstand, 8 auf Tablet, 4 auf Mobil; konsistente Gutter (24/16/12 px).
- **Dichte-Modi:** drei umschaltbare Dichten — `comfortable` (Mobil/Handschuh, größte Ziele), `standard` (Tablet), `compact` (Service-Laptop/Leitstand). Dichte ändert Abstände und Zeilenhöhen, **nie** die Touch-Zielgröße unter die Mindestwerte (5.5).
- **Touch-Ziele (verbindlich):** primär ≥ 56×56 px, sicherheitsrelevant ≥ 64×64 px, Quittieren/Speichern bis 72 px Höhe; Abstand ≥ 12 px (Handschuh).

### 5.5 Komponenten-Bibliothek

Aufgebaut als **Atomic-Schichtung** (Token → Primitive → Muster → Sichten) auf einer kuratierten, headless-orientierten Basis (z. B. shadcn/Radix-Primitiven), die zugänglich ist und sich vollständig auf das industrielle Token-Set umstellen lässt. Jede Komponente liefert die fünf Pflichtzustände **live / gecacht / lädt / leer / Fehler** (Prinzip 2). Kernkomponenten:

- **StatusIndicator (FCSM):** Farbe + Symbol + Label; Größen S/M/L; das meistgenutzte Atom — kanonisch über alle Sichten.
- **AlarmRow:** prioritätscodierte Zeile, Handschuh-Höhe, integrierte zweistufige Quittieren-Aktion, Flood-Bündelung.
- **KpiTile:** großer Wert + Spark + Zustand + Trendrichtung (Prinzip 6); nie nackte Zahl.
- **TimeSeriesChart:** Live/historisch, Normalband, Eigen-/Klassenprofil-Overlay, Differenzfläche; transport-agnostisch.
- **TimelineNarrative (D):** gekoppelte Timeline + Erzählung, Quell-Chips, „belegt vs. erzählt"-Trennung.
- **ConfidenceCaveatCard (E):** Wahrscheinlichkeitsband + Einflussfaktoren + Empfehlung + **untrennbarer Vorbehalt** in einem Rahmen.
- **DriftHeatmap (A):** WebGL-gestützt, Klasse×Maschine, sequenzielle Skala, Zoom-Pfad.
- **ScenarioSlider (G):** Handschuh-Slider mit Normal/Warn/Extrapoliert-Zonen, live gekoppelte Folgenkurve.
- **SearchResultCard (H):** heterogener Treffer mit Ähnlichkeitsbegründung und Sprungzielen.
- **CaptureForm / VoiceCapture (J):** vorbefüllte Zuordnungs-Chips, Offline-Queue mit Sync-Status, editierbares Transkript.
- **ProvenanceStamp:** wiederkehrender Herkunftsstempel (Stand, Datenbasis) — der AI-Act-Transparenzanker, an jeder erzeugten Erkenntnis.
- **ScopeBreadcrumb / GlobalStatusBar / CommandPalette / QuickCaptureFab:** die persistenten Rahmenelemente aus 3.3.

Jede Komponente wird mit Zuständen, Rollenvarianten und Barriere-Annotationen dokumentiert — der lebende Style Guide im Sinne von ISA-101.

### 5.6 Motion und Feedback

Bewegung ist funktional, nie dekorativ (ISA-101-Ruhe). Regeln:

- **Dauer:** Zustandsübergänge 120–200 ms, Ein-/Ausblenden ≤ 200 ms; nichts „schwebt" oder „federt" verspielt.
- **Erlaubte Bewegung:** einmaliger Aufmerksamkeits-Puls bei Statuskippung (A-Zelle, neue Alarmzeile); langsamer 1-Hz-Puls **nur** für unquittiert-kritische Alarme (ISA-18.2 — Blinken = unquittiert, nicht Severity); kontinuierliche Kurvenbewegung **nur** in G (Slider↔Folge, funktional) und im Live-Stream-Nachrücken (B).
- **Verbotene Bewegung:** Dauerblinken außer dem genannten Fall, dekorative Parallax-/Glow-/Verlaufs-Animation, springende Layouts bei Live-Updates.
- **Reduced Motion:** `prefers-reduced-motion` ersetzt alle Bewegung durch diskrete Zustandswechsel (G zeigt Schritt-Updates statt fließender Kurve).
- **Feedback:** jede Aktion bestätigt sofort (lokal, optimistisch) mit Status; nie ein stiller Klick.

### 5.7 Design-Tokens

Eine einzige Token-Quelle (z. B. JSON/Style-Dictionary) speist Web (CSS-Variablen/Tailwind-Theme) und etwaige native Verpackungen. Drei Token-Ebenen:

1. **Primitive Tokens:** Rohwerte (`gray-900 #15181C`, `space-2 8px`, `font-size-body 16px`).
2. **Semantische Tokens:** Bedeutung (`surface/canvas`, `alarm/critical`, `state/failure`, `note/caveat`) — UI referenziert nur diese, nie Rohwerte.
3. **Theme-Tokens:** Dark / High-Contrast-Light / (optional) Außenlicht-Modus überschreiben die semantische Ebene.

Vorteil: ein Theme-Wechsel oder eine Kontrast-Verschärfung ändert eine Ebene, nicht hunderte Komponenten. Dichte- und Geräte-Varianten laufen über dieselbe Mechanik.

### 5.8 Barrierefreiheit und Robustheit (Querschnitt)

- **Mehrkanal-Kodierung:** jede Bedeutung über mindestens zwei Kanäle (Farbe + Form/Position/Label). Pflicht, kein Nice-to-have.
- **Kontrast:** Status-Text ≥ 7:1, Körper ≥ 4.5:1, UI/Grafik ≥ 3:1; auf 3 m und im Streulicht geprüft (nicht nur am Schreibtisch).
- **Tastatur & Fokus:** vollständige Tastaturbedienung, sichtbarer Fokusring (≥ 3:1 gegen Umgebung); keine reine Hover-Funktion.
- **Screenreader/Semantik:** Live-Regionen für Alarme (höflich/assertiv je Priorität), beschriftete Bedienelemente, sinnvolle Lesereihenfolge.
- **Sprache:** UI-Wording in Hallensprache, kurze Sätze, keine Fachjargon-Hürde; KI-Inhalte als solche gekennzeichnet (AI-Act).
- **Degradation:** alles funktioniert offline/gecacht mit sichtbarem Stand; kein weißer Screen bei Netzverlust.

---

## Anhang — Abgleich, offene Punkte, Übergabe

**Abgleich mit der GROUND_TRUTH.** Das Frontend dieser Studie ruht auf dem etablierten Stack (React/Next.js, TypeScript strict, Tailwind, kuratierte Komponentenbasis, spezialisiertes Charting) und den belastbaren Backend-Fundamenten (Live-Streaming, Reasoner für Drift/Ketten/Ausfallvorhersage, semantische Querfunktion, Werker-Erfassung). Die Sektionen-Reifegrade entsprechen dem Sprintstand: C/D/E [STEHT], B/H/J [KERN/CRUD STEHT], A/F/G/I [VISION]. Wo der Prompt „React vs. Angular" offenließ, ist die Entscheidung konsistent zur GROUND_TRUTH auf React gefallen (5.1).

**Bewusst paraphrasiert (Hidden-Term-Disziplin).** Im gesamten sichtbaren Wording und in der Studie sind die inneren Verfahren der Gedächtnis- und Analyseschicht umschrieben („Einflussfaktoren", „ähnliche Fälle", „Abweichung gegen das Eigenprofil", „biologisch inspirierte Gedächtnisarchitektur"). Konkrete interne Bibliotheks-/Verfahrensnamen erscheinen nicht im Bedien-Wording. Die im Repo öffentlich geführten Werkzeuge des FOREMAN-eigenen Stacks (Charting, Streaming, ML-Bibliothek) sind in 5.1 technisch benannt, weil sie Entwicklungs-, kein Bedienkontext sind. **Vor jeder externen Freigabe (Mentor, Capstone, Kunde): erneuter Hidden-Term-Scan auf genau dieser Grenze.**

**Offene Designentscheidungen für die nächste Runde:**
1. Konkrete UI-Schrift final wählen und Lizenz/Selfhosting klären (Halle = offline-fähig).
2. Außenlicht-/Sonnenlicht-Modus: braucht es einen dritten Theme jenseits Dark/High-Contrast-Light?
3. Sprach-UI (J): On-Device-Transkription vs. Backend — Datenschutz/Netz-Trade-off, an die Maskierungs-Strategie koppeln.
4. Heatmap-Schwelle (A): ab welcher Föderationsgröße WebGL statt SVG real nötig wird (messen, nicht raten).
5. Eskalations-Fristen (C): konkrete Zeiten je Priorität mit den realen Schicht-/Verantwortungsstrukturen abstimmen.

**Übergabe-Pfad.** Diese Studie ist der Konzept-Stand. Der nächste Schritt Richtung Bau ist ein GROUND_TRUTH-Eintrag für das Frontend (Komponenten-Inventar, Token-Quelle, Routen je Sektion) und daraus abgeleitete Implementation-Prompts pro Sektion — beginnend bei den [STEHT]-Sichten C/E mit dem höchsten Sofort-Wert. Das gehört in die Bau-Werkzeuge, nicht in diesen Denkraum.

