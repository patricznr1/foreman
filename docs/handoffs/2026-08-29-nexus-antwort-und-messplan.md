# NEXUS-Antwort vom 29.08. — was daraus folgt

Eingegangen 29.08.2026 gegen 00:20. Alle Bestandszahlen darin sind eine
Momentaufnahme und vergehen mit unserem Neuspiegel-Lauf; was bleibt, sind die
Mechanismen.

---

## Das Einzige mit einem Termin

**Im selben Neuspiegel-Lauf müssen `occurred_at`, `machine_class` und
`component_type` als METADATENFELDER mitgehen.**

- Heute tragen **302 von 302** unserer Einträge `occurred_at` = Einspielzeit
  (Differenz unter 5 s, von ihnen nachgezählt). **Null** tragen `machine_class`
  oder `component_type`.
- Der Wissensgraph liefert diese Typ-Achse auch künftig **nicht**: Seine
  Entitäts-Typenliste ist geschlossen, und weder Maschinen- noch Bauteiltyp
  kommen darin vor.
- Jetzt kostet es einen Satz Code. Nach dem Neuspiegel kostet es **einen zweiten
  Vollspiegel**.

**Als Metadatenfelder, NICHT als Entitäten im Satz.** Ein Klassenwort im Satz
erzeugt bei ihnen nur eine weitere untypisierte Nabe — genau das Problem, das
wir mit den unterschiedlichen Satzanfängen beheben wollen.

Ohne diese zwei Felder ist alles Folgende unbaubar oder wertlos: Jeder
Fenster-Endpunkt filtert sonst das **Einspiel**fenster und antwortet plausibel
und zeitlich falsch, ohne Fehlermeldung.

---

## `context/build` — Absage, und diesmal mit tragfähigem Grund

Sie haben gegen unseren Gegenstand-Anker neu geprüft. Ergebnis: nein — aber
nicht, weil die Schichten leer wären, sondern weil sie **tautologisch** sind.

- **652 von 652** Gesprächszeilen in ihrer Produktivdatenbank tragen die Rolle
  `user`. Es gibt keine einzige Assistenten-Zeile: Die schreibende Funktion hat
  genau einen Aufrufer, und dort ist die Rolle fest verdrahtet.
- Wir bekämen also **unsere eigenen Alarmtexte zurück** — die letzten zwölf
  wörtlich, die älteren als Prosa mit Abschnitten wie „Emotionale Entwicklung"
  und „Wie hat sich die Stimmung entwickelt?". Über Hydraulikdruck.
- Zwei harte Sperren dazu: Wir können keine stabile Maschinenkennung einsetzen
  (die Gesprächskennung wird serverseitig erzeugt), und die Fassade kennt keinen
  Kontext-Endpunkt.

### Der Punkt, der die Absage von „passt nicht" auf „wäre schädlich" hebt

Ihre Vorwärmung schlüsselt den Zwischenspeicher nach **Nutzer und
Gesprächskennung — ohne Anteil der Nachricht**. Und die Wissensschicht gibt
einen vorhandenen vorgewärmten Satz **bedingungslos** zurück, ohne die aktuelle
Anfrage anzusehen.

Bei einem Faden je Anlage hieße das: **Zwei Alarme derselben Maschine innerhalb
einer Stunde — der zweite bekommt die Wissensschicht des ersten.** Stumm,
plausibel aussehend, falsch.

Alarmschauer sind in unserem Fach der Normalfall.

---

## Der Ersatz: ein Endpunkt an unserer Eintrags-Kennung

Meine Vermutung war richtig — es ist die Nachbar-Sache, nicht der Kontextaufbau.
Aber **nicht graphzentriert**, und das ist neu gegenüber ihrem letzten Vorschlag:

> Gemessen an unserem M7-Anker: Von 30 Kandidaten im Fenster (30 Tage davor /
> 7 danach) überleben nach der heutigen Reihenfolge — **erst deckeln, dann
> filtern** — genau **sechs**. Die Metadaten weisen **sieben** maschinenrichtige
> Einträge im selben Fenster aus.

Der Graph ist hier also nicht nur unnötig, er ist **schlechter als ein
Feldvergleich**. Bei zwei Sprüngen sind 78 % unseres Bestands erreichbar — dann
filtert er überhaupt nichts mehr.

Unsere drei fachlichen Stufen — dieselbe Maschine · baugleiche · derselbe
Bauteiltyp anderswo — sind **Feldvergleiche**. Der Endpunkt wird deshalb als
deterministische Metadaten-plus-Zeit-Gruppierung gebaut, der Graph als
abschaltbare Beigabe, und **der Filter vor dem Deckel**.

---

## Unsere drei Annahmen — alle beantwortet

### (a) Sucht `recall` über den ganzen Bestand? **Ja**, für die zwei dauerhaften Ebenen

Beide Abfragen setzen die Obergrenze **nach** dem Sortieren; der
Ausführungsplan gegen unseren Bereich zeigt, dass jede sichtbare Zeile bewertet
wird. Das Zufallssample sitzt ausschließlich in der Konsolidierung.

**Einschränkung:** Die flüchtige Ebene wird mit dem Original-Wunsch statt mit der
dreifachen Kandidatenzahl gerufen — dort kann eine Obergrenze einen echten
Treffer verdrängen. **Und nach unserem Neuspiegel liegt zunächst der GESAMTE
Bestand in dieser Ebene**, bis die erste Schlafphase ihn verschiebt.

### (b) Was geht außer Ähnlichkeit ein?

| Faktor | Wirkung |
|---|---|
| Ebenengewicht | stable 1,0 · plastic 0,8 · working 0,6, multiplikativ — bis 25 % |
| Phrasen-Zuschlag | +0,5 bei wortgetreuem Vorkommen |
| Rangfusion | bis ~+0,033 je Liste |
| Graph-Nachbarn | flacher Ersatzwert |
| Ontologie | +0,1 |
| Frische | +0,05 × 2^(−Tage/14) |

**Der Frische-Zuschlag rechnet gegen JETZT, nicht gegen unseren Ankerzeitpunkt.**
Eine Nähe zum Alarmereignis kennt NEXUS nicht — genau die Lücke, die der neue
Endpunkt schließen muss.

Präzisierung zu ihrer früheren Aussage „fast ausschließlich Ähnlichkeit": Sie ist
**gemessen, nicht konstruktionsbedingt.** Unsere Relevanzwerte liegen zwischen
0,9368 und 1,000 bei einem Mittel von 0,9979 — der Faktor ist **gesättigt, nicht
abwesend.**

### (c) Liefert kleines `k` eine andere Rangfolge? **JA** — das ändert die Messung

Die ersten fünf können sich umsortieren. Identisch bleiben sie nur, wenn drei
Dinge gleichzeitig zutreffen: kein Volltext-/Schattentreffer, keine
Graph-Erweiterung, und der Nachsortierer wird beide Male übersprungen.

Vier k-abhängige Mechanismen — der wichtigste:

> Der Nachsortierer gibt **„neu sortierte erste zehn + unveränderter Rest"**
> zurück. **Platz 11 kann nie in die ersten zehn aufsteigen.** Die Plätze 1–10
> und 11–20 einer `k=20`-Antwort sind nach **verschiedenen Kriterien** geordnet.

---

## Wie die `substrate_k`-Messung gebaut werden muss

1. **Jedes `k` ist ein eigener Arm.** Nie zwei k-Werte als „dieselbe Messung mit
   mehr Zeilen" führen.
2. **Vor jedem Lauf den Zugriffs-Zuschlag abschalten** —
   `NEXUS_RELEVANCE_ACCESS_BOOST_ENABLED`. Jeder ausgelieferte Treffer bekommt
   sonst dauerhaft **+0,1** auf seine Relevanz: *Die Messung verändert den
   Bestand, den sie misst.* NEXUS setzt den Schalter für den Messzeitraum auf
   Zuruf.
   → **Betrifft rückwirkend die drei Läufe vom 28.08.** (C-101/C-102): Sie liefen
   mit aktivem Zuschlag. Wirkung vermutlich gering, weil 291 von 302 Einträgen
   ohnehin auf der Deckelung 1,0 liegen — aber es ist ungeprüft und gehört in die
   Bedingung der Einträge nachgetragen.
3. **Auf unserer Seite protokollieren.** Sie protokollieren Substrate-Abrufe
   nicht.
4. **Der Neuspiegel-Lauf ist ein harter Schnitt.** Messungen davor und danach
   sind nicht vergleichbar: Danach liegt der ganze Bestand in der flüchtigen
   Ebene (anderes Gewicht, andere Kandidatenzahl), und der Wissensgraph ist für
   die neuen Einträge leer, bis der Aufbau erneut läuft.

---

## Ein Fehler bei ihnen, den sie offengelegt haben

Der vorhandene Zeitfenster-Baustein, auf den sie für unseren Endpunkt
zurückgreifen wollten, ist defekt: Er fährt zwei Speicher-Ebenen **nebenläufig
über eine geteilte Datenbanksitzung** — an anderer Stelle in ihrem Code
ausdrücklich verboten — und verschluckt den Konflikt still. **Die Antwort wird
kürzer, nicht erkennbar falsch.** Ihre Tests laufen gegen Attrappen und können
das per Konstruktion nicht sehen.

Sie bauen ihn neu und sequentiell.

---

## Was daraus für unser Schreib-Paket folgt

Das Paket bleibt eines und wird einmal gefahren. Inhalt jetzt:

1. Entitäten in den Satz, unterschiedliche Satzanfänge (gegen den Sammelknoten)
2. `component_id` in `alarm_payload` — wird heute stillschweigend fallengelassen
3. **`machine_class` und `component_type` als Metadatenfelder** ← neu, mit Termin
4. `occurred_at` ist seit `#142` drin und seit heute Nacht auch für die Abweichung
5. Danach: löschen, neu spiegeln, Archiv-Güte neu messen, Register nachziehen
   (C-050, C-078, C-079, C-084 auf `ueberholt`)
