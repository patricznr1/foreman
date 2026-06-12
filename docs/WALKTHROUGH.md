# WALKTHROUGH — FOREMAN in Klartext

> **Wozu dieses Dokument?** Die `GROUND_TRUTH.md` sagt, *was gilt*. Dieses Dokument erklärt, *warum und wie* — in verständlichem Deutsch, auch für Nicht-Coder. Ziel: Ich (und jeder Prüfer) kann zu jedem Baustein sagen, was er tut, warum er existiert und wie er sich verteidigen lässt.
>
> **Spielregel:** Dieses Dokument wächst mit dem Code. Jeder Commit, der etwas baut, ergänzt hier den passenden Abschnitt — im selben Commit.

**Stand:** 2026-06-12 · Fundament-Phase, noch kein Anwendungscode.

---

## Wie man dieses Dokument liest

Jeder Baustein bekommt denselben Dreiklang:

- **Was tut es?** — in einem Satz, ohne Fachjargon.
- **Warum existiert es / wo sitzt es?** — die Rolle in der Gesamtarchitektur.
- **Prüfer-Frage & Antwort** — eine wahrscheinliche Nachfrage und wie ich sie beantworte.

---

## Das große Bild (in drei Sätzen)

1. Eine Produktionsanlage erzeugt ständig Messdaten und Ereignisse — FOREMAN sammelt sie ein.
2. Fünf spezialisierte "Denker" (Reasoner) werten diese Daten mit Hilfe eines Langzeitgedächtnisses aus und beantworten Fragen, die ein normales Dashboard nicht beantworten kann.
3. Die Antworten landen entweder im Werker-Dashboard oder werden über eine standardisierte Schnittstelle an andere Systeme weitergereicht.

---

## Bausteine

*(Wird befüllt, sobald die ersten Module stehen — Skeleton, Datenbank, Ingestion, Drift-Reasoner, Dashboard. Pro Modul ein Abschnitt nach dem Dreiklang oben.)*

### Beispiel-Schablone (zum Kopieren pro neuem Modul)

```
### <Modulname>

**Was tut es?**
…

**Warum existiert es / wo sitzt es?**
…

**Prüfer-Frage & Antwort**
> Frage: …
> Antwort: …
```
