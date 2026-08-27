# Messbericht — Nachmessung der Archiv-Güte, Freigabe-Bedingung 1

**Stand:** 2026-08-27 (zwei Läufe: vor und nach dem Aufräumen) · **Gemessen gegen:** laufende Demo-Instanz (`frontend-production-169a`)
**Status:** intern, nicht freigegeben

> Fortschreibung von `2026-08-24_archiv_goldset.md`. Derselbe Bewertungssatz, dieselben
> 18 Anfragen, dieselben Beurteilungen. Geändert haben sich der **Code** (zwei Merges
> dazwischen), das **Auswertwerkzeug** (der Rückweg wird aufgelöst) und die **Schwelle**
> (präzisiert). Alle drei Änderungen sind unten einzeln ausgewiesen.
>
> Die abgeleiteten Aussagen stehen im Register als **C-064**, **C-066** und **C-068**; was hier steht
> und dort nicht, geht nicht nach draussen.

---

## 1. Was sich seit dem 24.08. geändert hat

| | Änderung | Wirkung auf die Messung |
|---|---|---|
| **Code** | Freitext von Wartung und Alarm im Gedächtnis, Nachtrag des Altbestands (#84) | mehr auffindbarer Inhalt je Erinnerung |
| **Code** | Rückweg `detail["quelle"]` im Produktpfad, Zusammenführung der Doppelfunde (#91) | Erinnerungen sind auf Goldset-Schlüssel abbildbar; derselbe Vorgang steht einmal |
| **Werkzeug** | `werte_aus.py::_schluessel` löst den Rückweg auf | **entscheidend** — ohne ihn 0 % Zusatztreffer, siehe §4 |
| **Schwelle** | „schlechter" heisst *verlorener Treffer*, nicht *gefallene Ranggüte* | **entscheidend** — siehe §5 |

## 2. Ergebnis

Rohdaten: `tools/archiv_guete/messung_2026-08-27_basis.json` und
`…_gedaechtnis.json`. Nachrechnen:

```bash
python tools/archiv_guete/werte_aus.py tools/archiv_guete/messung_2026-08-27_basis.json tools/archiv_guete/messung_2026-08-27_gedaechtnis.json
```

Die Rohdateien tragen intern die Laufnamen `neu_basis` und `neu_gedaechtnis` — so hat
`miss.py` sie beim Erheben benannt. Sie werden **nicht** nachträglich umbenannt: An einer
Messdatei wird nach der Erhebung nichts mehr geändert.

| Kennzahl (Mittel über 18 Anfragen) | drei Quellen | + Gedächtnis |
|---|---|---|
| Trefferquote (Recall) | 0,256 | **0,528** |
| Präzision | 0,415 | 0,394 |
| Ranggüte (nDCG) | 0,372 | **0,548** |
| Anfragen ganz ohne zutreffenden Treffer | 5 von 18 | **1 von 18** |

Gegen die beiden Schwellen der Freigabe-Bedingung 1:

| Bedingung | Ergebnis |
|---|---|
| (1) auf keiner Anfrage geht ein zutreffender Treffer verloren | **0 von 18** — erfüllt |
| (2) auf ≥ 30 % kommt ein zusätzlicher zutreffender Treffer hinzu | **11 von 18 = 61,1 %** — erfüllt |

**Freigabe-Bedingung 1: erfüllt.** Die einzige Anfrage ohne jeden zutreffenden Treffer
bleibt G-18 („Kühlschmierstoff Konzentration") — für sie führt das Goldset keinen
zutreffenden Eintrag im Bestand, sie kann also gar nicht erfüllt werden.

## 3. Unter welcher Bedingung gemessen wurde — und was das heisst

**Die Messung braucht den Schalter `FOREMAN_ARCHIVE_SUBSTRATE_ENABLED` auf `true`.**
Steht er auf `false`, reicht `archive/router.py` den Substrat-Client gar nicht erst durch und
setzt `substrate_k=0`: Die vierte Quelle ist dann **strukturell still**, unabhängig davon,
welche Quellen der Aufrufer anfordert. Ein Lauf mit ausgeschaltetem Schalter misst drei
Quellen gegen drei Quellen und meldet null Zusatztreffer.

Der Schalter war während dieses Laufs **an** und ist im Regelbetrieb **aus**. Die Zahlen oben
stammen also aus einem eigens hergestellten Messzustand, nicht aus dem Normalzustand der
Instanz. *(Nachtrag vom selben Tag: In der ersten Fassung dieses Berichts stand an dieser
Stelle nur „der Schalter steht weiterhin auf `false`" — das liest sich, als seien die Zahlen
im Normalzustand entstanden. Belegt ist der Messzustand durch zwei Läufe gegeneinander: mit
Schalter 77 Gedächtnis-Treffer über 18 Anfragen, ohne Schalter null.)*

**Erfüllt heisst nicht freigegeben.** Bedingung 1 ist **eine von mehreren** in
`GROUND_TRUTH.md` §15.10. Der Schalter geht nach jeder Messung wieder aus und bleibt es, bis
alle Bedingungen stehen. Dieser Bericht belegt eine Bedingung, keine Freigabe.

## 4. Warum die Auflösung des Rückwegs entscheidend ist

Ein Treffer aus dem Gedächtnis trägt als Herkunft `memory` und die Kennung `0` — die
Erinnerung hat keine Zeilen-Kennung im Archiv-Sinn. Ohne Auflösung lautet sein Schlüssel
also für jeden Treffer gleich `memory:0`, und kein einziger ist auf einen Goldset-Schlüssel
abbildbar. **Derselbe Messlauf, nur ohne die Auflösung, meldet 0 % Zusatztreffer** — nicht,
weil nichts gefunden wurde, sondern weil das Werkzeug nicht zuordnen kann, was gefunden
wurde. Genau dieser Vorbehalt stand seit dem 25.08. unter C-060.

Aufgelöst wird über `detail["quelle"] = {art, id}`, und dieses Feld kommt aus dem
**Produktpfad**: Die Antwort der Suche liefert es mit. Es wird nichts danebengerechnet und
nichts nachträglich rekonstruiert — der Unterschied zur Hilfsauswertung vom 25.08. (C-061),
die Treffer über Maschine und Zeitpunkt zuordnete.

**Kontrollpunkt gegen Doppelzählung.** Zwei Erinnerungen können auf dieselbe Quellzeile
zeigen; die Zusammenführung entfernt nur Erinnerungen gegen *eigene* Treffer, nicht
untereinander (bewusst so entschieden, #91). Ein aufgelöster Schlüssel könnte damit doppelt
in einer Liste stehen und die Trefferquote aufblähen. Nachgezählt: Dubletten treten auf
12 der 18 Anfragen auf, **ausschliesslich als `memory:0`** — also bei Erinnerungen ohne
Rückweg, und keine davon ist im Goldset zutreffend. Sie verwässern die Präzision, aber sie
zählen keinen zutreffenden Treffer doppelt.

Seit dem 27.08.2026 hängt das nicht mehr am Nachzählen: `kennzahlen()` gutschreibt jeden
Schlüssel nur bei seinem **ersten** Auftreten. Ohne diese Sperre lieferte derselbe Vorgang,
zweimal ausgeliefert, Trefferquote **2,0** und Ranggüte **1,63** — Werte, die es nicht geben
kann, und niemand hätte eine Meldung gesehen. Die Wiederholung belegt weiterhin einen Platz
und senkt damit die Präzision; nur zählt sie nichts doppelt gut. Auf die Zahlen dieses Laufs
wirkt sich die Sperre **nicht** aus (nachgerechnet: identische Werte vor und nach), weil der
Fall hier nicht eintrat. Sie ist gesetzt, **bevor** er eintritt.

## 5. Die Schwelle wurde präzisiert — nach der Messung, mit Wirkung auf das Urteil

Die ursprüngliche Fassung lautete „auf keiner Anfrage **schlechter** als die Baseline" und
wurde im Werkzeug als *gefallene Ranggüte* ausgelegt. Danach gilt eine Anfrage schon dann
als verschlechtert, wenn ein zutreffender Treffer eine Position nach hinten rutscht — auch
wenn keiner verloren geht und **mehr** gefunden wird. G-11 ist genau dieser Fall:

| | Trefferquote | Ranggüte | verlorene Treffer |
|---|---|---|---|
| G-11 | 0,50 → **0,67** | 0,64 → 0,59 | **keine** |

Eine Bedingung, die eine Verbesserung als Verschlechterung ausweist, misst nicht, was sie
messen soll. Die gültige Fassung lautet deshalb: **es geht kein zutreffender Treffer
verloren.**

**Was das für das Ergebnis bedeutet, offen ausgewiesen:**

| Lesart | Anfragen „schlechter" | Bedingung 1 |
|---|---|---|
| alt (gefallene Ranggüte) | **7** — G-01, G-03, G-04, G-08, G-10, G-11, G-15 | nicht erfüllt |
| neu (verlorener Treffer) | **0** | erfüllt |

Die Änderung ist also nicht kosmetisch: Sie kippt das Urteil. Sie wurde vorgenommen,
*nachdem* gemessen war. Beide Zahlen stehen deshalb hier und im Register nebeneinander
statt nur die günstigere — wer die Präzisierung nicht teilt, kann denselben Lauf gegen die
alte Lesart nachrechnen.

Was die Präzisierung **nicht** aufweicht: Ein verlorener Treffer bleibt ohne Toleranz ein
Ausschlussgrund. Die Ranggüte wird weiterhin erhoben und ausgewiesen — als Kennzahl, nicht
als Schwelle. Wer die Reihenfolge zur Bedingung machen will, braucht dafür ein eigenes,
begründetes Mass; die Position eines einzelnen Treffers ist keins.

## 6. Der offene Mangel, den die Schwelle nicht abfängt

Die mittlere Ranggüte steigt (0,372 → 0,548), aber auf sieben Anfragen fällt sie. Der Grund
steht in den Rohdaten:

> **40 von 137 ausgelieferten Plätzen (29,2 %) belegen Erinnerungen ohne Rückweg.
> Kein einziger davon ist zutreffend.**

Auf der laufenden Instanz sind das überwiegend **verwaiste Spiegelungen** (C-054): Der
Datenbestand wurde zwischenzeitlich neu aufgebaut, die zugehörigen Erinnerungen blieben
stehen. Sie beschreiben Vorgänge, die niemand mehr nachschlagen kann, belegen aber Plätze
in jeder Trefferliste.

Das Aufräumen (`substrate/aufraeumen.py`, C-065) entfernt genau sie. Der scharfe Lauf ist noch
am selben Tag gefahren worden; **das Ergebnis steht in §8** — und es fällt deutlicher aus als
hier erwartet.

## 7. Was dieser Bericht nicht belegt

- **Keine Freigabe.** Siehe §3.
- **Keine Aussage über echte Werkstätten.** Der Bestand ist eine Demo-Instanz mit 36
  Freitext-Einträgen. Die Anfragen sind formuliert, wie ein Meister sie eintippen würde,
  aber sie stammen nicht von einem Meister.
- **Keine Aussage über die Ranggüte als Schwelle.** Sie ist hier ausdrücklich Kennzahl.
- **Kein Nachweis, dass die verbleibende Ranggüte-Schwäche behoben ist.** Fünf von 18 Anfragen
  verlieren weiterhin Ranggüte (§8). Die Ursache ist nicht erhoben.
- **Kein Nachweis über Ableitungen des Systems.** Ob Empfehlung und Ereigniskette in die
  Archiv-Suche gehören, ist ungeklärt und wird von diesem Bericht nicht beantwortet.

## 8. Nach dem Aufräumen — dieselbe Messung noch einmal

Der scharfe Lauf fand am 27.08.2026 statt: **22 Erinnerungen entfernt**, alle `200 OK`, kein
Fehlschlag. Der zweite Trockenlauf meldet `geprüft=22 · mit_quelle=22 · mehrdeutig=0 ·
verwaist=0` — nichts übrig, und der Vorgang ist wiederholbar, ohne etwas anzurichten.

Danach dieselben 18 Anfragen, dieselben Beurteilungen, derselbe Messzustand:

| Kennzahl (Mittel) | drei Quellen | + Gedächtnis, vorher | + Gedächtnis, nachher |
|---|---|---|---|
| Trefferquote | 0,256 | 0,528 | **0,558** |
| Präzision | 0,415 | 0,394 | **0,425** |
| Ranggüte | 0,372 | 0,548 | **0,597** |
| Anfragen mit Zusatztreffer | — | 61,1 % | **66,7 %** |
| verlorene zutreffende Treffer | — | 0 | **0** |
| Plätze für Erinnerungen ohne Rückweg | — | 29,2 % | **11,0 %** |
| Anfragen mit gefallener Ranggüte | — | 7 von 18 | **5 von 18** |

Rohdaten: `tools/archiv_guete/messung_2026-08-27b_nach_aufraeumen_{basis,gedaechtnis}.json`.

**Kontrolle, ohne die die Zahlen nichts belegen:** Die Grundlinie aus drei Quellen ist vor und
nach dem Aufräumen **identisch** (Trefferquote 0,256, Ranggüte 0,372). Sie muss es sein — das
Aufräumen hat ausschliesslich das Gedächtnis angefasst. Bewegte sie sich, wäre zwischen den
beiden Läufen noch etwas anderes passiert und der Vergleich wertlos.

**Meine Vorhersage war in einem Punkt falsch, und zwar zugunsten der Sache.** Erwartet hatte
ich „steigende Präzision und Ranggüte bei **unveränderter** Trefferquote" — tatsächlich steigt
auch die Trefferquote, von 0,528 auf 0,558. Der Grund liegt in einer Grenze, die ich übersehen
hatte: Der Abruf aus dem Gedächtnis liefert je Anfrage nur eine begrenzte Zahl von Erinnerungen.
Die verwaisten belegten davon Plätze — sie verdrängten also nicht nur in der Trefferliste,
sondern schon **eine Ebene früher**, im Abruf selbst. Ihr Wegfall macht Platz für Erinnerungen,
die vorher gar nicht bis zur Verschmelzung kamen.

**Was bleibt:** 11,0 % der Plätze gehen weiterhin an Erinnerungen ohne Rückweg. Das Aufräumen
fasst ausdrücklich nur Wartung und Alarm an; die übrigen stammen aus Notiz-Spiegelungen und aus
Ableitungen des Systems (Empfehlung, Ereigniskette). Ob Ableitungen überhaupt in die
Archiv-Suche gehören, ist eine eigene, bewusst offen gelassene Frage — sie hier nebenbei mit zu
entfernen hiesse, sie stillschweigend zu entscheiden. Fünf Anfragen verlieren weiterhin
Ranggüte; das ist die nächste Spur.

## 9. Was am Werkzeug selbst gefunden wurde

Vor dem Push lief eine adversariale Prüfung gegen den fertigen Stand. Zwei Befunde betrafen
dieses Messwerkzeug, und beide sind behoben:

1. **Doppelte Gutschrift war möglich** — siehe §4. Ein Fall, der in diesem Lauf nicht eintrat,
   aber eine Freigabe hätte belegen können, die nicht gilt.
2. **Die Ausgabe nannte die frühere Schwellenfassung.** Das Werkzeug rechnete nach der neuen
   Fassung und druckte darüber `(1) auf KEINER Anfrage schlechter als die Baseline … ERFUELLT`.
   Wer nur die Werkzeugausgabe liest — und dazu lädt §2 dieses Berichts ausdrücklich ein —
   hätte ein Urteil über eine Bedingung gelesen, die so nicht mehr gilt. Die Ausgabe nennt
   jetzt den geltenden Wortlaut samt Fassungsdatum, und ein Prüffall fordert das ein.

Beide Prüffälle liegen in `tests/unit/test_archiv_guete_auswertung.py`. Das Erheben braucht
weiterhin eine laufende Instanz und gehört in keinen Prüflauf; das **Rechnen** braucht nichts
als die Rohdateien und wird ab jetzt geprüft.
