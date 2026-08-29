# Warum FOREMAN NEXUS nicht so nutzt wie ein Gesprächspartner

**Erhoben:** 28.08.2026 · fünf unabhängige Leser über den Quelltext, je ein Teilsystem
**Anlass:** *„Warum kann FOREMAN NEXUS nicht für manche Dinge genau so nutzen wie Du bei
Deiner täglichen Arbeit? Wo ist das Problem?"*

**Antwort in einem Satz:** Es gibt keine technische Sperre. Von sechs Methoden des
Gedächtnisses ruft FOREMAN drei, und die drei, die den Unterschied zu einem Vektorspeicher
ausmachen, sind toter Code.

---

## 1. Was gerufen wird, und was nicht

| Methode | Zustand | Aufrufstellen in `src/` |
|---|---|---|
| `remember` | Betriebspfad, breit | 7 Schreibwege + Nachtrag + Smoke |
| `recall` | Betriebspfad, drei enge Stellen | Ketten-Reasoner, Empfehlung, Archiv-Suche |
| `forget` | nur zwei Betreiber-Werkzeuge | keine Route, kein Dienstpfad |
| **`reason`** | **toter Code** | **0** |
| **`drift_status`** | **toter Code** | **0** |
| **`reflect`** | **toter Code** | **0** |

Alle drei sind im Client implementiert und über `substrate_reason_path`,
`substrate_drift_status_path`, `substrate_reflect_path` konfigurierbar. Angefasst werden
sie ausschließlich in `tests/unit/test_substrate_client.py`.

**Das heißt:** Beziehungen, Ontologie, Drifterkennung der Gegenstelle und Selbstauskunft
werden nie abgerufen. Ein Pfad für den **Kontextaufbau** (`context/build`) fehlt im Client
ganz — weder Vorgabe noch Einstellung.

---

## 2. Der Unterschied zum Gesprächsgebrauch, an der konkreten Stelle

Ein Gesprächspartner ruft `nexus_context` und bekommt eine **Zusammenstellung**, die ein
Sprachmodell liest. FOREMAN baut eine **Zeichenkette** und nimmt die besten fünf Treffer:

```
"ähnlicher Vorfall Maschinenklasse servo_axis Signatur AXIS_VIB_WARN Kategorie hardware"
```

`event_chain/recall.py:139` · die zweite Fassung in `failure/recall.py:45` setzt
Maschinenklasse + die drei stärksten SHAP-Faktoren + die Entscheidung zusammen.

FOREMAN hat **zwei Stellen, an denen ein Sprachmodell liest** — also wo eine
Zusammenstellung genauso wirken würde wie im Gespräch:

- `event_chain/service.py:260` — `Task.SYNTHESIS`, die Ketten-Erklärung
- `failure/recommendation.py:272` — `Task.EXPLANATION`, die Werker-Empfehlung

An beiden wird nur `recall` mit dem Textstring gerufen. Die **einzige** Stelle, an der eine
Zusammenstellung wirklich nicht passt, ist die Archiv-Suche — sie fusioniert vier
Ranglisten und braucht Kandidaten mit Rängen, keine Prosa. Ausgerechnet dort ist das
Gedächtnis angebunden.

---

## 3. Fünf Befunde, die schwerer wiegen als die fehlenden Methoden

### 3.1 Die semantische Notiz-Suche im Ketten-Pfad ist gebaut und still tot

`EventChainService.embedding_provider` hat den Vorgabewert `None`, und der **einzige**
Produktions-Aufruf (`event_chain/router.py:118-123`) übergibt keinen Provider.
`_load_semantic_notes` liefert im Betrieb deshalb **immer eine leere Liste**. Die
fenster-exempte „hatten wir das schon mal"-Notizsuche läuft ausschließlich in Tests.

Ein `EmbeddingProviderDep` existiert und wird von drei anderen Routern genutzt. Es fehlt
ein Parameter.

### 3.2 Nichts löst von sich aus aus

Beide Reasoner laufen ausschließlich auf HTTP-POST eines Menschen. `EventChainService` und
`FailureService` werden außerhalb des Routers nur in Tests konstruiert. Der Router-Kopf
hält ausdrücklich fest, dass der alarm-getriebene Hook offen bleibt und **nicht verdrahtet**
ist.

Selbst wenn das Gedächtnis meldete „AX-02 zeigt dasselbe Muster" — es fragt niemand.

### 3.3 Der Ausgang fehlt nur im Simulationspark — nicht im Betrieb

**Korrigiert am 28.08.2026 nach Einspruch des Eigentümers.** Die erste Fassung dieses
Abschnitts behauptete, der Ausgang fehle grundsätzlich. Das war archiv-gedacht und falsch.

Eine **Reparatur ist ein Wartungsereignis mit Datum**, und Wartungsereignisse werden
gespiegelt — `Wartung (repair) an Maschine 2 durchgeführt (2026-06-21T…). Lager getauscht.`
Seit `#142` mit korrekter Ereigniszeit. Im Betrieb liegt der Ausgang also vor.

Und der Kausalsatz **muss nirgends stehen**. Für AX-02 liegen vier datierte Ereignisse zur
selben Maschine und demselben Bauteil im Gedächtnis:

| Tag | Ereignis | gespiegelt als |
|---|---|---|
| 2 | Nachschmierung mit Schmierstoff Y | `maintenance_performed` |
| 3 | Drift `bearing_vibration` beginnt | `drift_detected` |
| 14 | Alarm `AXIS_VIB_WARN` | `alarm_raised` |
| 20 | *(Reparatur — im Betrieb ein Wartungsereignis)* | `maintenance_performed` |

Aus vier Zeitpunkten am selben Gegenstand ist der Zusammenhang **erschließbar**. Das ist
die Aufgabe eines Gedächtnisses, nicht die des Absenders.

**Was wirklich fehlt, ist zweierlei:**

1. **Im Simulationspark** endet der Lauf nach 21 Tagen und erzeugt für den `bearing_failure`
   bei 20d10h **kein** Ereignis — weder kritischen Alarm noch Reparatur. Der Fall ist in
   `ground_truth` ausgelegt (`narrative_anchor`: „gleiche Wartung, anderer Schmierstoff,
   divergente Degradation") und in den Daten unvollständig. Das ist ein Mangel der
   **Demo-Daten**, nicht der Architektur.
2. **Niemand stellt die Frage.** Alle drei `recall`-Anfragen sind Textstrings ohne
   Zeitbezug, ohne Bauteil, ohne Beziehung. Die vier Ereignisse liegen da — und werden nie
   in einen zeitlichen Zusammenhang gebracht, weil FOREMAN nur „welcher Text ähnelt diesem"
   fragt.

`failure_predictions` speichert im Übrigen **Vorhersagen**, keine eingetretenen Schäden —
das bleibt richtig, ändert aber nichts daran, dass die Reparatur als Wartung ankommt.

### 3.4 Baugleichheit wird nie geprüft, Ähnlichkeit nie gemessen

`build_sibling_references` übernimmt `machine_class` ungeprüft aus Treffer oder Datenbank;
ein Vergleich gegen die Klasse der Anker-Maschine findet **nirgends** statt. Ein
„Geschwister" kann eine beliebige andere Maschine sein.

`RecallItem.relevance` wird aus der Antwort gelesen, geht aber **nicht** in
`SiblingReference` ein — keine Schwelle, kein Cutoff, keine Rangfolge. Der Basis-Satz
(„Ähnlich anhand: Maschinenklasse …, Signatur …") ist ein **Etikett**, keine berechnete
Ähnlichkeit.

Und es gibt nirgends in `src/` ein Prädikat der Form `machine_class = X AND id <> self` —
niemand sucht baugleiche Schwestern.

### 3.5 Kein Profil im Fachsinn

`readings.value` ist ein einzelner Double je Zeitstempel. Eine Suche über `src/` nach
`fft|spectrum|envelope|waveform` liefert **nichts**. Ableitbar sind Niveau, Steigung und
Streuung einer Skalarreihe — keine Signatur, kein Spektrum, keine Lagerschadensfrequenz.
„Dasselbe Profil" kann heute nur „ähnlicher Kurvenverlauf" heißen.

Nebenbefund: Der `measurement_type`-Enum kennt gar keinen Wert `vibration`; Schwingung ist
auf `signal` abgebildet — in `docs/simulation/szenarien.md` §0 als offener Punkt vermerkt.

---

## 4. Was die Daten hergeben — und was nicht

**Gebaut und befüllt:**

- `machines.machine_class` ist eine echte Spalte und wird beim Seeding gesetzt
- Twin-Park „Montagelinie 1": 12 Maschinen, 5 Klassen, je Klasse eine gesunde Kontroll-Schwester
- Vier baugleiche `servo_axis` (AX-01…04) mit **identisch benanntem** Datenpunkt
  `axis_bearing_vibration`, gleicher Einheit, gleichem Normband — auf DB-Ebene joinbar
- `readings` als TimescaleDB-Hypertable, 10-Minuten-Takt über 21 Tage
- `park_ax02.yaml` trägt den kausalen Zusammenhang aus: `maintenance_causal.pattern='grease_choice'`,
  Ursache, betroffene Maschine, Kontrollmaschine AX-01, `failure {offset 20d10h, bearing_failure}`
- Ein Bauteil-Typ verbindet **zwei Maschinenklassen**: `bearing` sitzt an AX-01…04
  (`servo_axis`) *und* RB-01/02 (`robot`) — die Brücke für den Ventil-Fall existiert strukturell

**Fehlt für den geschilderten Fall:**

- Die zeitliche Voraussetzung. Alle 12 Szenarien starten auf `2026-06-01T06:00` und laufen
  21 Tage **parallel**. Es gibt keinen abgeschlossenen Präzedenzfall an Maschine A und keine
  spätere Wiederholung an Maschine B — nur einen gleichzeitigen Krank/Gesund-Kontrast.
- Die Rollen sind vertauscht: **AX-02 ist die kranke** Schwester, AX-01 die gesunde Kontrolle.
  Ein Szenario „AX-01 hatte den Schaden, AX-02 zeigt es jetzt" existiert nicht.

---

## 5. Was das für die Reihenfolge heißt

Nach Aufwand, nicht nach Wichtigkeit — die ersten drei sind klein:

| # | Was | Umfang |
|---|---|---|
| 1 | `embedding_provider` an den Ketten-Reasoner durchreichen | ein Parameter · schaltet eine tote Funktion an |
| 2 | Bauteil-Typ in `build_recall_query` | eine Zeile · macht den Ventil-Fall adressierbar |
| 3 | `relevance` in `SiblingReference` führen und schwellen | wenige Zeilen · macht „ähnlich" messbar statt behauptet |
| 4 | **Eine zeitliche Frage stellen** statt eines Textstrings | die Anfrage, nicht die Daten |
| 5 | Kontextaufbau an den zwei LLM-Stellen | Pfad im Client + Einstellung + Verdrahtung |
| 6 | `reason` verdrahten | hängt an der Fassaden-Durchreichung (1.6) |
| 7 | Ein Auslöser, der von sich aus fragt | Architekturentscheidung, kein Handgriff |
| 8 | Simulationspark: den Ausfall als Ereignis erzeugen | Demo-Daten, damit der Fall vorführbar wird |

**Punkt 4 ist der Angelpunkt** — und er kostet keine Daten, sondern eine andere Frage. Die
vier datierten Ereignisse liegen im Gedächtnis. Solange FOREMAN nur „welcher Text ähnelt
diesem" fragt, bleiben sie unverbunden; nicht weil etwas fehlt, sondern weil niemand nach
dem Zusammenhang fragt.

Der ursprüngliche Punkt 4 dieser Liste lautete „Ausgänge spiegeln" und beruhte auf dem
Irrtum aus §3.3 — er ist ersetzt.

---

## 6. Was hier NICHT belegt ist

- Die Leser konnten nur das Repository lesen. Ob die betriebene Instanz andere Einstellungen
  trägt, ist daraus nicht feststellbar. **Nachgetragen aus eigener Messung am selben Tag:**
  Die vierte Archiv-Quelle IST im Betrieb eingeschaltet — ein Nur-Gedächtnis-Lauf gegen die
  öffentliche Demo-Instanz lieferte bei 10 von 10 Anfragen je 5 Treffer.
- Ein grüner Integrationstestlauf in dieser Sitzung. Belegt sind Code-Pfad und die
  Zusicherungen in den Tests, nicht deren Ausführung.
- **Warum** die drei Methoden nie verdrahtet wurden. Eine Entscheidung dagegen ist in
  GROUND_TRUTH, im Register und in den Freigabe-Bedingungen nirgends dokumentiert — daraus
  folgt nicht, dass sie nicht getroffen wurde.

## 7. Zwei Funde am Rand, die eigene Behebung verdienen

- **`substrate/content.py:139`** kodiert den Satz „(simulationsbasiert, nicht validiert)"
  **hart** und liest `payload['validation_status']` nicht, obwohl die Nutzlast das Feld
  führt. Heute stimmt der Satz, weil `ModelMetadata` per `Literal` nur `simulation_only`
  zulässt. Sobald ein reales Artefakt zugelassen wird, schreibt der Spiegel eine falsche
  Aussage ins Gedächtnis, ohne dass etwas anschlägt.
- **Widerspruch in F-REC:** Regel 4 des System-Prompts verbietet dem Modell, den
  Validierungs-Status zu erwähnen, während `build_recommendation_user_prompt` es auffordert,
  „den simulationsbasierten Charakter" zu benennen. Der Vorbehalt kommt ohnehin
  deterministisch dazu — der Auftrag im User-Prompt ist tote, widersprüchliche Anweisung.
