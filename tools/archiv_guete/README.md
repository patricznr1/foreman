# Güte-Messung der Archiv-Suche

Werkzeuge für **Freigabe-Bedingung 1** aus `GROUND_TRUTH.md` §15.10: ein Bewertungssatz,
gegen den sich Änderungen an der Archiv-Suche belegen lassen, statt sie zu behaupten.

Messberichte, jüngster zuerst:

- [`2026-08-27_archiv_goldset_nachmessung.md`](../../docs/messungen/2026-08-27_archiv_goldset_nachmessung.md) — Bedingung 1 erfüllt (Register **C-064**, **C-066**)
- [`2026-08-24_archiv_goldset.md`](../../docs/messungen/2026-08-24_archiv_goldset.md) — Aufbau des Bewertungssatzes (Register **C-047** bis **C-050**)

## Warum getrennte Schritte

`miss.py` erhebt und legt die Trefferlisten **roh** ab. `werte_aus.py` rechnet
ausschliesslich aus diesen Dateien. Kein Zwischenwert wandert über den Kopf in eine
Kennzahl — dieselbe Trennung wie bei jeder anderen Messung im Haus.

Deshalb bleibt auch die **Zuordnung** auf der Auswertungsseite: `werte_aus.py::_schluessel`
löst den Rückweg einer Erinnerung auf ihre Quellzeile auf (`detail["quelle"]`, den die Suche
mitliefert). Ohne ihn trägt jeder Erinnerungs-Treffer denselben Schlüssel `memory:0` und ist
auf keinen Goldset-Schlüssel abbildbar — die zweite Schwelle wäre dann nicht messbar. Fehlt
der Rückweg, bleibt es bei `memory:0`; geraten wird nichts.

Ein Fehler beim Erheben wird **mitgeschrieben**, nicht verschluckt: In der Auswertung
erscheint er als „nicht vergleichbar", nie als „keine Treffer". Ein Netzfehler ist
kein Fehltreffer.

## Dateien

| Datei | Rolle |
|---|---|
| `goldset_anfragen.yaml` | 18 Anfragen mit Absicht — **ohne** Relevanzurteil |
| `bestand_flach.json` | der gelesene Bestand (36 Einträge), Grundlage der Beurteilung |
| `goldset.json` | die verdichteten Relevanzurteile — das eigentliche Goldset |
| `baue_goldset.py` | verdichtet mehrere unabhängige Urteile per Mehrheit |
| `miss.py` | erhebt (Schritt 1) |
| `werte_aus.py` | wertet aus und prüft beide Schwellen (Schritt 2) |
| `messung_*.json` | Rohdaten der Läufe — nach der Erhebung wird an ihnen nichts mehr geändert |

## Anwenden

```bash
export FOREMAN_DEMO_URL=https://…
export FOREMAN_DEMO_EMAIL=…
export FOREMAN_DEMO_PASSWORT=…

python miss.py baseline note,maintenance,alarm
python werte_aus.py messung_baseline.json
```

Zwei Läufe vergleichen — die Schwellen aus §15.10 werden dabei direkt geprüft:

```bash
python miss.py mit_gedaechtnis note,maintenance,alarm,memory
python werte_aus.py messung_baseline.json messung_mit_gedaechtnis.json
```

> **Ohne den Schalter misst der zweite Lauf dasselbe wie der erste.**
> `FOREMAN_ARCHIVE_SUBSTRATE_ENABLED` muss auf der gemessenen Instanz `true` sein. Steht er
> auf `false`, reicht `archive/router.py` den Substrat-Client gar nicht durch und setzt
> `substrate_k=0` — die vierte Quelle ist dann **strukturell still**, egal welche Quellen der
> Aufrufer anfordert, und die Messung meldet null Zusatztreffer. Im Regelbetrieb ist der
> Schalter aus; er wird für die Messung an- und danach wieder ausgeschaltet.
>
> **Prüfe ihn im laufenden Prozess, nicht in der Variablen** — nach dem Setzen dauert es, bis
> der neue Stand ausgerollt ist, und eine Messung dazwischen misst den alten:
>
> ```bash
> railway ssh 'python -c "from foreman.config import get_settings; print(get_settings().archive_substrate_enabled)"'
> ```

**Die Schwellen im Wortlaut** (§15.10, Fassung vom 27.08.2026):

1. Auf **keiner** Anfrage geht ein zutreffender Treffer **verloren**.
2. Auf **≥ 30 %** kommt ein zusätzlicher zutreffender Treffer hinzu.

Die Ranggüte wird erhoben und ausgewiesen, ist aber **keine** Schwelle: Eine gefallene
Ranggüte bei unverändertem Bestand an zutreffenden Treffern bedeutet, dass ein Treffer eine
Position gewechselt hat — nicht, dass einer fehlt. Warum das präzisiert wurde und was es für
das Urteil bedeutet, steht im Messbericht vom 27.08., Abschnitt 5.

## Das Goldset erneuern

Die Relevanz wird **getrennt von der Anfrageformulierung** und von **mehreren
voneinander unabhängigen Beurteilern** vergeben. Der Grund steht im Messbericht:
Ein Bewertungssatz aus einem einzigen Urteil misst dieses Urteil mit. Die
Übereinstimmungsquote, die `baue_goldset.py` ausweist, ist deshalb selbst eine
Kennzahl — fällt sie niedrig aus, ist nicht die Suche schlecht, sondern die
Aufgabe schlecht gestellt.

```bash
python baue_goldset.py urteile_roh.json
```

Aufgenommen wird eine Zuordnung ab zwei von drei Stimmen; die Stufe ist der Median.

## Bekannte Grenzen

Sie stehen ausführlich im Messbericht, Abschnitt 7. Die schwerwiegendste:

> **Im gemessenen Bestand wiederholt sich kein einziger Vorgang** — 19 Tage, jede
> Störungsgeschichte genau einmal. Die Frage „hatten wir das schon mal" hat dort
> keine Antwort, unabhängig von der Güte der Suche.

Das ist mit einem besseren Anfragesatz **nicht** heilbar. Wer die Aussagekraft
erhöhen will, braucht mehr und wiederkehrendes Material im Bestand — nicht mehr
Anfragen.

## Kein CI-Schritt

Bewusst nicht. Die Messung braucht eine laufende Instanz mit Daten und einen
Zugang; beides gehört nicht in einen Prüflauf. Sie wird angewandt, wenn jemand
etwas an der Suche ändert — und ihr Ergebnis landet im Register, nicht in einem
grünen Häkchen.
