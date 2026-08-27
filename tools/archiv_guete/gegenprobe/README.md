# Gegenprobe am Störungsmaterial — Verfahren und Belege

**Erhoben am 27.08.2026.** Register: **C-075** (Relevanz-Definition), **C-076** (Güte des Materials).

## Wozu

Für die Frage „hatten wir das schon mal" braucht der Bewertungssatz Material, in dem sich
Vorgänge **wiederholen**. Der bisherige Bestand hatte das nicht — 19 Tage, jede
Störungsgeschichte genau einmal (C-050). Ein Autor hat daraufhin 327 Einträge geschrieben und
behauptet, darin wiederholten sich zwanzig Störungsbilder je dreimal.

Diese Behauptung wird hier geprüft. Zweimal, auf zwei verschiedene Arten.

## Prüfung 1 — maschinell: gibt es eine Stichwort-Brücke?

Die Forderung an das Material war, dass zwei Vorkommen desselben Störungsbildes sich **nicht
über gleiche Wörter** finden lassen. Sonst fände die Volltextsuche sie allein, und die vierte
Quelle (das Gedächtnis) belegte nichts.

Der naheliegende Test — Jaccard-Ähnlichkeit der Wortmengen — taugt dafür **nicht**: Er schlägt
schon bei Fachwörtern an, die im ganzen Bestand vorkommen (*Druck* in 22 Einträgen, *Teile* in
28). Solche Wörter bilden keine Brücke, weil sie zu allem passen.

Der schärfere Test lautet: **Gibt es ein Wort, das alle drei Vorkommen verbindet UND im übrigen
Bestand selten ist?** Ergebnis:

| | |
|---|---|
| Störungsbilder ohne Brückenwort | **17 von 20** |
| mit Brückenwort | V3 („motor", 6 Notizen) · S2 („bild", 4) · S3 („ausschuss", 6) |

Die drei Ausnahmen sind kein Mangel — das sind Wörter, die ein Werker natürlich benutzt. Sie
gehören aber in jeden Messbericht: **Für diese drei Störungsbilder belegt ein Treffer der
vierten Quelle weniger**, weil ihn die Volltextsuche womöglich allein gefunden hätte.

## Prüfung 2 — durch einen Fachmann, blind

40 Paare von Schichtnotizen, beurteilt von jemandem mit Berufserfahrung als Inbetriebnehmer und
Anlagen-Fehlersucher. Die Frage je Paar: **Beschreiben diese beiden Einträge dasselbe Problem?**

**Was der Beurteiler nicht sah:** die Typ-Zuordnung des Autors, die Zahl der zusammengehörigen
Paare, die späteren Suchanfragen. Kein Wort aus dem Lösungsschlüssel stand im Katalog
(nachgeprüft). Ein Urteil, das die Vorlage kennt, bestätigt sie nur.

### Die Aufbau-Kontrolle

Fünf der 40 Paare stammten aus **demselben** Vorgang — dieselbe Maschine, wenige Tage
auseinander. Sie mussten „ja" ergeben. **Alle fünf getroffen.**

Ohne diese Kontrolle wäre kein Ergebnis deutbar: Eine niedrige Zustimmung liesse sich nicht von
einem missverständlichen Fragebogen unterscheiden.

### Ergebnis

| Sorte | n | Urteil | erwartet |
|---|---|---|---|
| Aufbau-Kontrolle | 5 | 5× ja | ja ✅ |
| echte Wiederholung | 12 | 10× ja | ja ✅ |
| **Ablenker** | 8 | **6× ja** | nein ❌ |
| verschiedene Störungsbilder | 12 | 8× nein | nein ✅ |
| Grundrauschen | 3 | 2× nein | nein ✅ |

## Der Befund, der die Messung ändert

Ein **Ablenker** ist ein Fall mit gleichem Symptom und anderer Ursache — nach der Definition des
Autors ausdrücklich **kein** Treffer. Der Beurteiler wertete sechs von acht als dasselbe Problem.

**Er urteilt nach dem Symptombild, der Autor nach der Ursache.** Und für „hatten wir das schon
mal" ist die erste Lesart die tragfähige: Wer an der Anlage steht, kennt die Ursache noch nicht.
Gerade die Fälle, in denen es am Ende etwas anderes war, sparen die halbe Fehlersuche.

Folge: Das Goldset führt **zwei Relevanz-Stufen** (GROUND_TRUTH §15.10). Stufe 2 = gleiche
Ursache, Stufe 1 = gleiches Symptombild bei anderer Ursache. Beide Sichtweisen sind abgebildet;
wer die engere bevorzugt, rechnet denselben Lauf gegen nur Stufe 2 nach.

**Grenze:** ein Beurteiler, acht Ablenkerpaare. Das trägt eine Entscheidung über die Definition,
keine Aussage über Fehlersucher im Allgemeinen.

## Wo das Material nicht überzeugt hat

Zwei behauptete Wiederholungen wurden verneint: F1 („Klemmzylinder schaltet verzögert" — Schaltzeit
gegen Ruckeln) und P5 („Werkzeug sitzt nicht fest" — Kraft gegen Versatz). Beide betreffen Notizen
mit der Wendung **„Kraft steht oben"**, die der Beurteiler ausdrücklich als unüblich bezeichnete:

> „Ausdrücke wie *Kraft oben* sind nicht gebräuchlich. Der Rest passt meistens."

Das ist kein Fehler in der Sache, sondern in der Sprache — und es trifft ausgerechnet die beiden
Störungsbilder, bei denen die Zustimmung fehlt.

## Die Anfragen des Goldsets

Zehn Anfragen stammen aus derselben Erhebung: Zu je einem Störungsanfang schrieb der Beurteiler
auf, **was er wirklich ins Suchfeld tippen würde**. Er sah dabei je Störungsbild nur **ein**
Vorkommen — wer alle drei sieht, formuliert auf sie hin, und die Messung misst dann
Formulierungskunst statt Suche.

Sie werden **wörtlich** übernommen, samt Tippfehler („Durckabfall Hydraulik"). Eine geglättete
Anfrage wäre nicht mehr die, die in der Halle getippt würde.

## Was diese Gegenprobe NICHT belegt

- **Nicht, dass eine Messung auf diesem Material die Bewährung in einer echten Halle zeigt.** Die
  Wiederholungen sind **gepflanzt**. Wer misst, ob die Suche sie findet, misst den Mechanismus.
- **Nicht, dass die Relevanz-Definition allgemein gilt.** Sie stammt von einem Beurteiler.
- **Nicht, dass die drei Störungsbilder mit Brückenwort für die vierte Quelle sprechen.**

## Dateien

| | |
|---|---|
| `AUSWERTUNG_Vorgangstypen.md` | Wahrheitsgrundlage des Autors — gehört **nicht** in den durchsuchten Bestand |
| `FRAGENKATALOG_schluessel.json` | welches Paar welcher Sorte war (fester Startwert 20260827, reproduzierbar) |
| `urteile_2026-08-27.json` | die Urteile, Anmerkungen, Anfragen und offenen Antworten — wörtlich |
