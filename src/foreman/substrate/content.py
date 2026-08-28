# ============================================================
#  FOREMAN — substrate/content.py
#  Zweck: Die Formulierung eines gespiegelten Ereignisses — EINE Quelle für den
#         Live-Pfad UND den nachträglichen Backfill.
#  Architektur-Einordnung: Vertrag der Substrat-Brücke (Schicht 2). Reine
#         Funktionen über der `payload`, keine Datenbank, kein Netz.
#  Warum es dieses Modul gibt (Befund 20.08.2026): Der Text stand zweimal im
#         Repository — einmal inline bei den Aufrufern von `record_semantic_event`,
#         einmal als Rekonstruktion im Backfill. Zusammengehalten wurden sie von
#         einem Kommentar ("wortgleich zu den ursprünglichen Aufrufern") und von
#         nichts sonst: KEIN Test verglich die beiden Fassungen. Wer eine Seite
#         ändert, lässt die andere still zurück — und der Backfill schreibt dann
#         einen anderen Satz ins Gedächtnis als der Live-Pfad, ohne dass es
#         auffällt. Jetzt gibt es nur noch eine Formulierung.
#  Invariante: Der Text ist VOLLSTÄNDIG aus der `payload` ableitbar. Was im Text
#         steht, muss dort drin sein — sonst kann der Backfill es nicht
#         rekonstruieren und überspringt die Zeile, statt Text zu erfinden.
# ============================================================
from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

__all__ = [
    "CONTENT_BUILDERS",
    "baue_inhalt",
]


def _freitext(wert: Any) -> str | None:
    """Normalisiert ein optionales Freitext-Feld für die Anhängung an einen Satz.

    EINE Stelle für alle Bauer, die Freitext führen — sonst entstehen zwei
    Auffassungen davon, was „leer" heisst, und eine Zeile bekommt je nach Bauer
    ein angehängtes Leerzeichen oder nicht. Genau diese Art stiller Abweichung
    war der Anlass, dieses Modul überhaupt anzulegen (Kopfkommentar).

    `None`, ein leerer Text und ein Text aus reinem Weissraum sind gleich zu
    behandeln: Sie tragen nichts bei und dürfen dem Satz kein Anhängsel geben.
    """
    if not isinstance(wert, str):
        return None
    geputzt = wert.strip()
    return geputzt or None


def _alarm_raised(payload: Mapping[str, Any]) -> str:
    """Alarm — mit Auslösezeitpunkt.

    DER ZEITPUNKT GEHÖRT HINEIN (Befund 20.08.2026, gemessen): Ohne ihn ist ein
    Alarm desselben Typs an derselben Maschine vom vorherigen nicht zu
    unterscheiden. Beim Nachtrag der 65 Ereignisse fielen deshalb sechs Paare
    über den Inhalts-Hash zusammen — aus 65 Spiegelungen wurden 59 Einträge:
    zweimal AXIS_VIB_WARN an Maschine 2, zweimal an Maschine 3, zweimal
    HYD_PRESS_LOW_WARN an Maschine 7, und drei weitere.
    Für die Frage "hatten wir das schon mal" ist die WIEDERHOLUNG die eigentliche
    Information — sie ging genau dort verloren, wo sie zählt. Die Wartungs- und
    Produktionslauf-Formulierungen führen den Zeitpunkt seit jeher.

    Harter Zugriff auf die Pflichtfelder: eine Zeile ohne sie ist defekt und wird
    übersprungen (KeyError → None), statt '?' zu erfinden. Nur `code` selbst darf
    regulär None sein.

    DIE MELDUNG GEHÖRT HINEIN (Befund 24.08.2026, gemessen): Der Code sagt, WELCHE
    Art Alarm anlag, die Meldung sagt, WORUM es ging — „Fügekraft über Erwartung,
    Werkzeugverschleiss vermutet" statt nur `TOOL_LOAD_HIGH`. Für die Frage
    „hatten wir das schon mal" ist der Sachverhalt die Antwort, nicht das Kürzel.
    Beleg: In der Goldset-Messung fand keine einzige Anfrage über die vierte
    Quelle einen zusätzlichen zutreffenden Treffer, solange nur die Struktur
    gespiegelt wurde (Register C-050).

    WEICHER ZUGRIFF, mit Absicht: Alt-Zeilen tragen das Feld nicht. Ein harter
    Zugriff liesse `baue_inhalt` werfen und der Nachtrag überspränge sie — der
    gesamte Bestand fiele aus der Spiegelung, um ein Feld zu gewinnen, das er
    ohnehin nicht hat. Ohne Meldung entsteht wortgleich der bisherige Satz.
    """
    kopf = (
        f"Alarm {payload['code'] or '?'} ({payload['severity']}/{payload['category']}) "
        f"an Maschine {payload['machine_id']} ausgelöst ({payload['raised_at']})."
    )
    meldung = _freitext(payload.get("message"))
    return f"{kopf} {meldung}" if meldung else kopf


def _production_run(payload: Mapping[str, Any]) -> str:
    return (
        f"Produktionslauf {payload['product_code']} auf Linie {payload['line_id']} "
        f"gestartet ({payload['started_at']})."
    )


def _maintenance_performed(payload: Mapping[str, Any]) -> str:
    """Wartungsvorgang — mit Beschreibung.

    DIE BESCHREIBUNG GEHÖRT HINEIN (Befund 24.08.2026, gemessen), und zwar aus
    einem Grund, der über Bequemlichkeit hinausgeht: Der *Grund* eines
    Degradationsverlaufs lebt ausschliesslich im Freitext — nie als Datenpunkt
    (GROUND_TRUTH §12.5, „Beobachtungsgrenze"). Ein Sensor sieht nicht, dass ein
    Ersatzfett mit zu niedriger Grundölviskosität eingefüllt wurde; das steht in
    der Beschreibung oder nirgends. Wird sie nicht gespiegelt, kann das Gedächtnis
    die Ursache eines Vorgangs grundsätzlich nicht kennen — und „hatten wir das
    schon mal" bleibt unbeantwortbar, egal wie gut abgerufen wird.

    Gemessen: `type=lubrication` allein brachte über die vierte Quelle auf keiner
    von 18 Anfragen einen zusätzlichen zutreffenden Treffer (Register C-050).

    WEICHER ZUGRIFF wie bei `_alarm_raised` — Begründung dort.
    """
    kopf = (
        f"Wartung ({payload['type']}) an Maschine {payload['machine_id']} "
        f"durchgeführt ({payload['performed_at']})."
    )
    beschreibung = _freitext(payload.get("description"))
    return f"{kopf} {beschreibung}" if beschreibung else kopf


def _drift_detected(payload: Mapping[str, Any]) -> str:
    # Der Reasoner speichert bereits round(effect_size, 4); die Anzeige mit
    # zwei Nachkommastellen trifft ihn damit exakt.
    return (
        f"Verhaltens-Drift an Datenpunkt {payload['data_point_id']} erkannt "
        f"(Effektgröße {float(payload['effect_size']):.2f})."
    )


def _event_chain(payload: Mapping[str, Any]) -> str:
    hint = " (Hypothese)" if payload["is_hypothesis"] else ""
    return (
        f"Ereigniskette zu Alarm {payload['anchor_alarm_id']} an Maschine "
        f"{payload['machine_id']}: {payload['event_count']} Ereignisse, "
        f"Konfidenz {payload['confidence']}{hint}."
    )


def _failure_recommendation(payload: Mapping[str, Any]) -> str:
    return (
        f"Werker-Empfehlung zu Vorhersage {payload['prediction_id']} an Maschine "
        f"{payload['machine_id']}: Entscheidung {payload['decision']}, Horizont "
        f"{payload['horizon_h']} h (simulationsbasiert, nicht validiert)."
    )


# Registry event_type → Formulierung. Deckt ALLE Typen ab, die je über
# `record_semantic_event` entstehen.
def _worker_note(payload: Mapping[str, Any]) -> str:
    """Schichtnotiz — hier IST der Freitext der Inhalt.

    BEWUSSTE AUSNAHME von der Linie "kein Freitext ins Gedaechtnis" (§12.4):
    Bei Alarm, Wartung und Produktionslauf traegt die STRUKTUR die Information —
    Code, Typ, Zeitpunkt. Der zugehoerige Freitext ist Beiwerk und bleibt
    draussen. Bei einer Schichtnotiz ist es umgekehrt: "mahlendes Geraeusch beim
    Hochlauf, letzte Woche noch nicht da" IST die Information. Ohne den Text
    bekaeme das Gedaechtnis einen leeren Merkzettel — es wuesste, DASS jemand
    etwas notiert hat, aber nicht was.

    DATENSCHUTZ: Der Text ist an dieser Stelle bereits NER-maskiert. Beide
    Schreibwege maskieren VOR dem Insert (api/routers/worker_notes.py,
    ingestion/service.py), der Dual-Write setzt danach an. Das Restrisiko bleibt
    und wird nirgends als Anonymitaet ausgegeben (§8, Modell-Docstring).

    SICHERHEIT: Kommt der Text ueber einen Abruf zurueck, fuehrt ihn FOREMAN als
    untrusted (`trusted=False`, grounding_sources.py) und markiert ihn im Prompt.
    Diese Zusicherung liegt bei FOREMAN, nicht beim Gedaechtnis-Dienst.

    `machine_id` ist bei Notizen nullable — ohne Bezug wird das benannt statt
    "Maschine None" zu schreiben.
    """
    maschine = payload["machine_id"]
    bezug = f"zu Maschine {maschine}" if maschine is not None else "ohne Maschinenbezug"
    return f"Schichtnotiz {bezug} ({payload['created_at']}): {payload['text']}"


CONTENT_BUILDERS: dict[str, Callable[[Mapping[str, Any]], str]] = {
    "worker_note": _worker_note,
    "alarm_raised": _alarm_raised,
    "production_run": _production_run,
    "maintenance_performed": _maintenance_performed,
    "drift_detected": _drift_detected,
    "event_chain_reconstructed": _event_chain,
    "failure_recommendation": _failure_recommendation,
}


def baue_inhalt(event_type: str, payload: Mapping[str, Any]) -> str:
    """Baut den Text für ein Ereignis — der Weg des Live-Pfads.

    Wirft, wenn der Typ unbekannt ist oder die payload ein Feld nicht trägt: Auf
    dem Schreibweg ist beides ein Programmierfehler, der sofort auffallen soll.
    Der Backfill geht denselben Weg, fängt die Ausnahme aber ab und überspringt
    die Zeile — dort ist unvollständiger Altbestand ein zu erwartender Fall.
    """
    builder = CONTENT_BUILDERS[event_type]
    return builder(payload)


# Welches Feld der Nutzlast den ZEITPUNKT DES EREIGNISSES trägt — je Ereignisart
# ein anderes. Neben CONTENT_BUILDERS und aus demselben Grund: Der Text und die
# Zeit beschreiben dasselbe Ereignis, und wer den einen Weg ändert, sieht den
# anderen daneben stehen.
# NUR die vier Ereignisarten, die einen Zeitpunkt WIRKLICH mitführen. Die
# Erkenntnis-Arten (Abweichung, Ereigniskette, Ausfalleinschätzung) tragen
# Kennungen statt Zeiten — für sie bleibt es bei der Eingangszeit, und das ist
# richtig so: Ihr Zeitpunkt IST der ihrer Entstehung.
ZEIT_FELDER: dict[str, str] = {
    "worker_note": "created_at",
    "alarm_raised": "raised_at",
    "production_run": "started_at",
    "maintenance_performed": "performed_at",
}


def ereigniszeit(event_type: str, payload: Mapping[str, Any]) -> str | None:
    """Der Zeitpunkt, zu dem das Ereignis STATTFAND — nicht der des Spiegelns.

    WARUM DAS EIN EIGENER WEG IST: Das Gedächtnis führt eine Ereigniszeit
    (`occurred_at`). Wird sie nicht mitgegeben, setzt es den Zeitpunkt des
    Eingangs. Am 28.08.2026 trugen dadurch 248 von 302 gespiegelten Einträgen
    dieselbe Stunde — die des Nachtrags. Jede zeitliche Auswertung auf der
    Gegenseite hätte den Stapellauf beschrieben statt den Betrieb, und ein
    Zeitfilter über die Ereigniszeit wäre wirkungslos gewesen.

    Der Fehler war nicht, dass die Zeit fehlte: Sie steht in jeder Nutzlast, nur
    als Metadatum. Metadaten wertet die Gegenstelle nicht aus.

    GIBT `None` STATT ZU WERFEN, anders als `baue_inhalt`: Eine fehlende
    Ereigniszeit macht den Eintrag nicht wertlos — er landet dann mit der
    Eingangszeit, also so wie bisher. Ein Wurf würde die Spiegelung eines sonst
    brauchbaren Ereignisses verhindern, und der Schreibpfad ist best-effort.
    """
    feld = ZEIT_FELDER.get(event_type)
    if feld is None:
        return None
    wert = payload.get(feld)
    return wert if isinstance(wert, str) and wert else None
