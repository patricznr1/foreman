# Was FOREMAN von NEXUS erreicht — und was nicht

**Datum:** 28.08.2026 · **Register:** C-100 · **Freigabe:** intern
**Erhoben:** aus dem Betriebsbehälter gegen die laufende NEXUS-Instanz, nur
lesende Aufrufe

---

## Kurzfassung

FOREMAN spricht NEXUS über eine **Substrat-Fassade** an (`/api/substrate/*`) und
authentifiziert sich mit einem Bearer-Token. Alles, was NEXUS von einem
Vektorspeicher unterscheidet — Kontextaufbau, Wissensnetz, ADWIN-Drift — liegt
hinter einer **anderen Zugangsgrenze**, die dieses Token nicht öffnet.

Das ist der Grund, aus dem FOREMAN diese Fähigkeiten nicht ruft. Nicht eine
Bauentscheidung, die anders hätte ausfallen können, sondern eine Grenze, die
zuerst verschoben werden müsste.

---

## 1. Was mit FOREMANs Token erreichbar ist

| Weg | Zustand |
|---|---|
| `POST /api/substrate/remember` | benutzt (4 Aufrufe) |
| `POST /api/substrate/recall` | benutzt (3 Aufrufe) |
| `DELETE /api/substrate/forget/{raum}/{id}` | benutzt (2 Aufrufe) |
| `POST /api/substrate/reflect` | erreichbar, **nie gerufen** |
| `POST /api/substrate/drift_status` | erreichbar, **nie gerufen** |
| `POST /api/substrate/reason` | erreichbar, aber **abgeschaltet** |
| `POST /api/substrate/consolidate` | erreichbar, **nie gerufen**, im Client **nicht bekannt** |

`reason` antwortet mit `active: false` und der Begründung, das Reasoning sei
SPARQL-basiert und laufe über `/api/ontology` — also hinter der Grenze.

`drift_status` antwortet mit `is_drifting: false, events: [], total_count: 0`.
Ob dahinter nichts liegt oder die Fassade nichts durchreicht, ist **nicht
entschieden** — beides sieht von hier aus gleich aus.

**`consolidate` ist der Fund dieser Aufstellung:** Er liegt in der Fassade, ist
mit FOREMANs Token erreichbar, und der Client kennt ihn nicht einmal.

## 2. Was hinter der Grenze liegt

Alle antworten auf FOREMANs Token mit `401 Ungültiges Token: Not enough
segments` — ein JWT-Parserfehler. Das Substrat-Token ist kein JWT; es ist ein
anderer Ausweis für einen anderen Bereich.

| Weg | Bedeutung |
|---|---|
| `POST /api/context/build` | **der Kontextaufbau** — die vier Schichten |
| `POST /api/context/reidentify` | Zuordnung im Kontext |
| `GET /api/admin/drift` | **ADWIN-Ereignisse** |
| `POST /api/admin/drift/scan` | einen Drift-Lauf anstossen |
| `GET /api/drift/status` | zweiter Drift-Kanal |
| `POST /api/admin/kg/reason` | Wissensnetz-Schlussfolgerung |
| `POST /api/ontology/query` · `GET /api/ontology/infer` | Ontologie |
| `POST /api/ontology/consistency` | Widerspruchsprüfung |

**Der Kontextaufbau existiert.** Er ist nicht ungebaut und nicht unerreichbar —
er ist für FOREMANs Ausweis geschlossen.

---

## 3. Was der Einzelabruf tatsächlich liefert

Das ist wichtiger, als es zunächst aussieht: `recall` gibt **keine rohen
Datensätze** zurück, sondern bereits zusammengesetzte Aussagen.

```
content:  "Schichtnotiz zu Maschine 3 (2026-05-28T07:20:00+00:00):
           AX-03 geht seit gestern in Schleppfehler. Gestern wurde das
           Programm angepasst, Beschleunigung höher. Zusammenhang liegt nahe."
relevance: 1.366
entry_type: observation
metadata:  machine_id, shift, source_type, source_id, created_at,
           temporal_label: "gestern"
occurred_at: 2026-08-27T12:34:37
```

Drei Dinge daran, die FOREMAN heute **nicht auswertet**:

**`relevance`** — ein Rangwert von NEXUS. FOREMANs Fusion wirft ihn weg und
benutzt nur die Reihenfolge.

**`temporal_label: "gestern"`** — NEXUS ordnet den Eintrag zeitlich ein, relativ
zum Ereignis. Das ist ein Stück der Zeitrahmung, die sonst im Kontextaufbau
steckt, und es kommt hier schon mit.

**`entry_type`** — heute durchgehend `observation`. Verdichtete Einträge
bekämen einen anderen Typ; über dieses Feld wären sie unterscheidbar.

Der Bestand zählt laut `reflect`: **302 Einträge, 291 plastisch, 11 stabil.**
Die Verdichtung läuft also auf FOREMANs Namensraum, und die stabilen Einträge
sind über `recall` erreichbar — nur nicht als solche erkennbar, weil FOREMAN
`entry_type` nicht liest.

---

## 4. Der qualitative Unterschied — was belegt ist und was nicht

**Belegt:** Der Einzelabruf liefert eine bewertete, zeitlich eingeordnete,
zusammengesetzte Trefferliste mit Rückweg auf die Quellzeile. Er ist deutlich
mehr als eine Vektorsuche.

**Nicht belegt, weil nicht erreichbar:** was der Kontextaufbau darüber hinaus
liefert. Aus der NEXUS-Beschreibung sind es vier Schichten mit Zeitkopf und
Gesprächspuffer — das ist eine **Fremdangabe** und in diesem Dokument nicht
nachgeprüft. Solange FOREMANs Ausweis dort nicht öffnet, bleibt der Vergleich
eine Behauptung.

**Struktureller Unterschied, unabhängig vom Inhalt:** Der Abruf liefert
*Kandidaten mit Rängen* — fusionierbar. Der Kontextaufbau liefert eine
*Zusammenstellung* — nicht fusionierbar, ohne sie vorher zu zerlegen. Für die
Archiv-Suche, die vier Ranglisten verschmilzt, ist das kein Detail. Für eine
Frühwarnung oder ein „Hatten wir das schon mal" wäre es eines.

---

## 5. Wie FOREMAN künftig an ADWIN-Ereignisse käme

Drei Wege, keiner heute gangbar:

**Über die Fassade.** `POST /api/substrate/drift_status` ist erreichbar und
liefert die richtige Form (`is_drifting`, `events`, `total_count`) — heute leer.
Wenn NEXUS dort die ADWIN-Befunde durchreicht, braucht FOREMAN **keine neue
Berechtigung**, nur einen Aufrufer. Das ist der kürzeste Weg, und er hängt an
NEXUS.

**Über den Verwaltungsbereich.** `GET /api/admin/drift` liefert die Ereignisse
direkt. FOREMAN bräuchte dafür einen JWT-Ausweis — also Zugang zu einem Bereich,
der ausdrücklich Verwaltung heisst. Das ist eine Rechtefrage, keine technische.

**Als Zustellung statt Abholung.** NEXUS meldet eine erkannte Verschiebung an
FOREMAN, statt darauf zu warten, gefragt zu werden. Passt zur Sache: Eine
Frühwarnung, die man abholen muss, ist keine.

**Zu klären, bevor irgendetwas gebaut wird:** ob `total_count: 0` bedeutet
„nichts erkannt" oder „nichts durchgereicht". Das ist eine Frage an die
NEXUS-Seite und von hier aus nicht zu beantworten.

---

## 6. Was daraus folgt

**Die Grundstufe von FOREMAN ist vollständig gebaut** — Archiv-Suche ohne
NEXUS, mit NEXUS als vierter Quelle. Das war die Konzeptentscheidung, und sie
ist eingehalten.

**Die Ausbaustufe ist nicht halb gebaut, sondern nicht begonnen** — und der
erste Schritt liegt nicht in FOREMAN. Er liegt an der Grenze zwischen den beiden
Systemen: Welchen Ausweis bekommt FOREMAN, und was reicht die Fassade durch.

**Was ohne jede Grenzverschiebung heute möglich wäre**, in dieser Reihenfolge:

1. `entry_type` und `relevance` aus dem Abruf auswerten, statt sie wegzuwerfen —
   verdichtete Einträge würden dadurch als solche erkennbar.
2. `substrate_k` kalibrieren. Der Wert 5 ist nie erhoben worden und bestimmt,
   wie viel Gedächtnis überhaupt bis zum Werker durchkommt.
3. `reflect` als Betriebskennzahl führen — 302 Einträge, 11 stabil, ist heute
   nirgends sichtbar.
4. `consolidate` überhaupt in den Client aufnehmen. Er ist erreichbar und
   unbekannt.
