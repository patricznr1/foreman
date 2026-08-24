# Güte-Messung der Archiv-Suche

Werkzeuge für **Freigabe-Bedingung 1** aus `GROUND_TRUTH.md` §15.10: ein Bewertungssatz,
gegen den sich Änderungen an der Archiv-Suche belegen lassen, statt sie zu behaupten.

Der zugehörige Messbericht: [`docs/messungen/2026-08-24_archiv_goldset.md`](../../docs/messungen/2026-08-24_archiv_goldset.md)
Die daraus abgeleiteten Aussagen: Register **C-047** bis **C-050**.

## Warum getrennte Schritte

`miss.py` erhebt und legt die Trefferlisten **roh** ab. `werte_aus.py` rechnet
ausschliesslich aus diesen Dateien. Kein Zwischenwert wandert über den Kopf in eine
Kennzahl — dieselbe Trennung wie bei jeder anderen Messung im Haus.

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
| `messung_*.json` | Rohdaten der Läufe vom 24.08.2026 |

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
