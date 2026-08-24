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
    """
    return (
        f"Alarm {payload['code'] or '?'} ({payload['severity']}/{payload['category']}) "
        f"an Maschine {payload['machine_id']} ausgelöst ({payload['raised_at']})."
    )


def _production_run(payload: Mapping[str, Any]) -> str:
    return (
        f"Produktionslauf {payload['product_code']} auf Linie {payload['line_id']} "
        f"gestartet ({payload['started_at']})."
    )


def _maintenance_performed(payload: Mapping[str, Any]) -> str:
    return (
        f"Wartung ({payload['type']}) an Maschine {payload['machine_id']} "
        f"durchgeführt ({payload['performed_at']})."
    )


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
