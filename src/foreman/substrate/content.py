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


def _datensatz(payload: Mapping[str, Any]) -> str:
    """Die eigene Nummer des Quelldatensatzes, als Vorsatz für den Satz.

    DAS IST DIE BILLIGSTE POSITION MIT DER GRÖSSTEN WIRKUNG (Befund der
    Gegenstelle, 28.08.2026): Ihre Knotenidentität entsteht aus dem Namen, und
    weil bisher JEDER gespiegelte Satz einer Art mit derselben Wortfolge begann,
    fielen alle Einträge dieser Art auf EINEN Knoten zusammen — 168 Notizen auf
    einen einzigen „Schichtnotiz"-Knoten. Über den lief anschliessend die
    Vererbung, und daraus entstanden rund 1.684 falsche Aussagen.

    Der zweite Grund wiegt schwerer und trifft uns unabhängig von ihrem Graphen:
    DER SATZ IST AUCH DIE GRUNDLAGE DER EINBETTUNG. Einträge, die alle mit
    derselben Wortfolge beginnen, teilen einen Anteil ihres Vektors, der nichts
    mit ihrem Inhalt zu tun hat — sie rücken zusammen, und zwar alle. Das trifft
    jeden Abruf.

    Leerer Rückgabewert, wenn die Nummer fehlt — Altbestand aus der Zeit vor dem
    Rückweg trägt sie nicht. Der Satz bleibt dann lesbar; wortgleich zum
    bisherigen ist er NICHT, denn die Notiz beginnt seit dem 29.08.2026 mit
    „Notiz" statt „Schichtnotiz". Das ist gewollt: Der Neuspiegel-Lauf schreibt
    ohnehin jeden Eintrag neu, und zwei Formulierungen nebeneinander wären
    schlimmer als eine geänderte.
    """
    nummer = payload.get("source_id")
    return f"{nummer} " if isinstance(nummer, int) and nummer > 0 else ""


def _gegenstand(
    payload: Mapping[str, Any], *, zusatz: str | None = None, maschine_optional: bool = False
) -> str:
    """Benennt den Gegenstand: die Anlagenkennung, sonst die Maschinennummer.

    `maschine_optional` entscheidet über die HÄRTE des Zugriffs auf
    `machine_id`, und das ist keine Geschmacksfrage: Bei Alarm und Wartung ist
    die Spalte in der Datenbank `NOT NULL` — eine Nutzlast ohne sie ist defekt,
    und der Nachtrag soll sie ÜBERSPRINGEN statt „ohne Maschinenbezug" zu
    schreiben. Nur die Schichtnotiz darf regulär ohne Maschine bestehen.

    Der erste Entwurf las immer weich und hat damit den harten Zugriff der
    Alarm-Formulierung stillschweigend aufgehoben; `test_pflichtfelder_werfen_
    weiterhin` hat es gefangen.

    `zusatz` wandert in dieselbe Klammer wie die Maschinennummer. Das braucht
    genau ein Bauer — die Notiz, deren Satz den Zeitpunkt unmittelbar hinter dem
    Gegenstand führt. Ohne die gemeinsame Klammer stünden dort zwei Klammern
    hintereinander.

    WARUM DIE KENNUNG UND NICHT DIE NUMMER (Anforderung der Gegenstelle,
    29.08.2026): „Maschine 9" ist eine Zeilennummer unserer Datenbank. Der
    Werker nennt die Anlage „PR-03", der Freitext daneben auch, und das
    Gedächtnis bildet seine Knoten aus dem SATZ. Steht dort nur die Nummer,
    entsteht kein Knoten für die Anlage, den ein anderer Eintrag treffen könnte.

    Die Nummer bleibt trotzdem im Satz — sie ist der Rückweg in unsere eigene
    Datenbank, und ohne sie müsste ein Leser sie nachschlagen.

    WEICHER ZUGRIFF: Altbestand trägt `machine_external_id` nicht. Ohne sie
    entsteht wortgleich die bisherige Formulierung. Das ist Absicht: Der
    Nachtrag reichert die Nutzlast erst an; bis dahin darf der Satz nicht
    zerfallen.
    """
    maschine = payload.get("machine_id") if maschine_optional else payload["machine_id"]
    kennung = _freitext(payload.get("machine_external_id"))
    if maschine is None:
        kopf, klammer = "ohne Maschinenbezug", []
    elif kennung:
        kopf, klammer = kennung, [f"Maschine {maschine}"]
    else:
        kopf, klammer = f"Maschine {maschine}", []
    if zusatz:
        klammer.append(zusatz)
    return f"{kopf} ({', '.join(klammer)})" if klammer else kopf


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


def _zeitanhang(payload: Mapping[str, Any]) -> str:
    """Der Erkennungszeitpunkt einer Abweichung, als Anhang in der Klammer.

    WEICH, obwohl `drift/service.py` das Feld immer schreibt: Ein harter Zugriff
    liesse `baue_inhalt` werfen, und der Nachtrag überspränge die Zeile — der
    Befund verschwände aus dem Gedächtnis, um einen Zeitstempel zu gewinnen, den
    er nicht hat. Dieselbe Abwägung wie bei der Alarm-Meldung.
    """
    wert = _freitext(payload.get("detected_at"))
    return f", {wert}" if wert else ""


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
        f"Alarm {_datensatz(payload)}{payload['code'] or '?'} "
        f"({payload['severity']}/{payload['category']}) "
        f"an {_gegenstand(payload)} ausgelöst ({payload['raised_at']})."
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
    bauteil = _freitext(payload.get("component_label"))
    am_bauteil = f", {bauteil}" if bauteil else ""
    kopf = (
        f"Wartung {_datensatz(payload)}({payload['type']}) "
        f"an {_gegenstand(payload)}{am_bauteil} "
        f"durchgeführt ({payload['performed_at']})."
    )
    beschreibung = _freitext(payload.get("description"))
    return f"{kopf} {beschreibung}" if beschreibung else kopf


def _drift_detected(payload: Mapping[str, Any]) -> str:
    # Der Reasoner speichert bereits round(effect_size, 4); die Anzeige mit
    # zwei Nachkommastellen trifft ihn damit exakt.
    return (
        f"Verhaltens-Drift an {_gegenstand(payload)}, Datenpunkt "
        f"{payload['data_point_id']} erkannt "
        f"(Effektgröße {float(payload['effect_size']):.2f}{_zeitanhang(payload)})."
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
    return (
        f"Notiz {_datensatz(payload)}zu "
        f"{_gegenstand(payload, zusatz=payload['created_at'], maschine_optional=True)}: "
        f"{payload['text']}"
    )


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
# WELCHE ARTEN HIER STEHEN, entscheidet die NUTZLAST — nicht die Kategorie.
# Der erste Entwurf schloss alle drei Erkenntnis-Arten aus, mit der Begründung,
# sie trügen „Kennungen statt Zeiten". Für zwei stimmt das: Ereigniskette und
# Ausfalleinschätzung führen `anchor_alarm_id` bzw. `prediction_id` und keinen
# Zeitpunkt — ihre Zeit IST die ihrer Entstehung.
#
# FÜR DIE ABWEICHUNG STIMMT ES NICHT. `drift_detected` führt `detected_at`, und
# das ist `sample.bucket` aus `readings_1m` — der Zeitpunkt in der Halle, an dem
# die Abweichung auftrat, nicht der des Rechnens. `reasoners/failure/service.py`
# sagt das seit jeher ausdrücklich („historische Drift-Zeit, korrekt auch bei
# Backfill") und liest das Feld als Merkmal.
#
# WARUM DAS BESONDERS SCHWER WIEGT: Der einzige Einstieg in den Drift-Reasoner
# ist `drift/runner.py::replay_machine` — ein Wiederholungslauf über einen
# historischen Zeitraum. Ohne dieses Feld bekämen ALLE Abweichungen eines Laufs
# denselben Zeitstempel, den des Laufs. Ein Wiederholungslauf über vier Wochen
# legt damit den gesamten Drift-Bestand auf einen Punkt der Zeitachse — genau
# das Muster, das beim Nachtrag schon einmal den halben Bestand in dieselbe
# Stunde gelegt hat, nur an anderer Stelle.
ZEIT_FELDER: dict[str, str] = {
    "worker_note": "created_at",
    "alarm_raised": "raised_at",
    "production_run": "started_at",
    "maintenance_performed": "performed_at",
    "drift_detected": "detected_at",
}


def ereigniszeit(event_type: str, payload: Mapping[str, Any]) -> str | None:
    """Der Zeitpunkt, zu dem das Ereignis STATTFAND — nicht der des Spiegelns.

    WARUM DAS EIN EIGENER WEG IST: Das Gedächtnis führt eine Ereigniszeit
    (`occurred_at`). Wird sie nicht mitgegeben, setzt es den Zeitpunkt des
    Eingangs — und dann beschreibt dort jede zeitliche Auswertung den
    Spiegel-Lauf statt den Betrieb. Ein Nachtrag für Altbestand legt so den
    halben Bestand in dieselbe Stunde, und ein Zeitfilter über die Ereigniszeit
    greift ins Leere.

    Die Zeit in der Nutzlast mitzuführen genügt dafür NICHT: Dort ist sie ein
    Metadatum, und Metadaten wertet die Gegenstelle nicht aus. Sie liest dieses
    Feld.

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
