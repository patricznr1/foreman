# ============================================================
#  FOREMAN — tests/unit/test_ereigniszeit.py
#  Zweck: Die Spiegelung schickt den Zeitpunkt des EREIGNISSES mit, nicht nur
#         den des Spiegelns.
#  Warum das eine eigene Datei wert ist: Die Fehlerklasse, gegen die sie
#         gebaut ist, wirft nicht und faellt nicht auf. Ohne eigenes Zeitfeld
#         traegt beim Substrat jeder Eintrag den Zeitpunkt des SPIEGELNS; ein
#         Nachtrag fuer Altbestand legt damit den halben Bestand in dieselbe
#         Stunde, und jede zeitliche Auswertung dort beschreibt den Stapellauf
#         statt den Betrieb.
#         Die Zeit in den Metadaten mitzufuehren genuegt nicht: Die Gegenstelle
#         wertet Metadaten nicht aus, sie liest `occurred_at`.
# ============================================================
from __future__ import annotations

from typing import Any

import pytest

from foreman.substrate.content import CONTENT_BUILDERS, ZEIT_FELDER, ereigniszeit

# Die beiden Erkenntnis-Arten. Bewusst als Literale und nicht aus ZEIT_FELDER
# abgeleitet: Der Test soll anschlagen, wenn jemand die Menge aendert, statt mit
# ihr mitzuwandern.
ERKENNTNIS_ARTEN = ("event_chain_reconstructed", "failure_recommendation")

# ──────────────────────────────────────────────────────────────────────
#  Die Abbildung — sie darf keine Felder nennen, die es nicht gibt
# ──────────────────────────────────────────────────────────────────────


def test_jede_zeitangabe_gehoert_zu_einer_bekannten_ereignisart() -> None:
    """Ein Eintrag fuer eine unbekannte Art waere still wirkungslos.

    `ereigniszeit` schlaegt ueber `.get` nach; ein Tippfehler im Schluessel
    liefert einfach None. Ohne diesen Fall waere das nicht zu bemerken.
    """
    unbekannt = set(ZEIT_FELDER) - set(CONTENT_BUILDERS)
    assert not unbekannt, (
        f"❌ ZEIT_FELDER nennt Ereignisarten, die es nicht gibt: {sorted(unbekannt)}. "
        "Der Eintrag waere wirkungslos, ohne dass etwas rot wird."
    )


def test_jede_ereignisart_hat_ein_zeitfeld() -> None:
    """DIE ANDERE RICHTUNG — und an ihr lag es (02.09.2026).

    Der Fall darueber prueft `ZEIT_FELDER - CONTENT_BUILDERS`: keine Zeitangabe
    fuer eine Art, die es nicht gibt. Die Gegenrichtung stand hier NICHT, und
    genau dort sass der Mangel — zwei von sieben Arten fuehrten kein Zeitfeld,
    und nichts wurde rot. Ein Deckungstest, der nur eine Richtung prueft, deckt
    nicht ab; er deckt zu.
    """
    ohne = set(CONTENT_BUILDERS) - set(ZEIT_FELDER)
    assert not ohne, (
        f"❌ Diese Ereignisarten tragen kein Zeitfeld: {sorted(ohne)}. Sie werden mit "
        "der Zeit des SPIEGELNS abgelegt. Solange der Dual-Write glueckt, faellt das "
        "nicht auf — scheitert er, spiegelt der Nachlauf Stunden spaeter, und der "
        "Eintrag traegt fuer immer die Laufzeit statt seiner Entstehungszeit."
    )


def test_erkenntnis_arten_tragen_die_zeit_ihrer_eigenen_zeile() -> None:
    """DER TRAGENDE FALL: Ereigniskette und Empfehlung fuehren `created_at`.

    Frueher stand hier das GEGENTEIL — eine Aufbau-Kontrolle, die einforderte,
    dass diese beiden Arten kein Zeitfeld haben, weil ihr Zeitpunkt der ihrer
    Entstehung SEI. Das stimmt nur, solange Entstehung und Spiegelung
    zusammenfallen, also auf dem Live-Weg. Auf dem Nachlauf-Weg fallen sie
    auseinander.

    ZUM ZWEITEN MAL AN DERSELBEN STELLE. Der geloeschte Fall trug im Docstring
    bereits die Lehre aus dem ersten Mal: „Dieser Test hat den Irrtum GEHALTEN,
    nicht aufgedeckt. Eine Aufbau-Kontrolle, die eine falsche Annahme
    festschreibt, ist so wirksam wie ein falscher Kommentar." Damals ging es um
    `drift_detected`, das faelschlich mit in der Ausnahmeliste stand. Die Lehre
    stand da — und die Liste behielt zwei weitere Eintraege, die aus demselben
    Grund falsch waren. Eine niedergeschriebene Lehre traegt nichts; der Fall
    darueber tut es.

    Warum `created_at` der eigenen Zeile statt der Zeit des Spiegelns: Bei der
    Gegenstelle wird die mitgeschickte Zeit zur Gueltigkeitszeit jedes Fakts, der
    aus dem Eintrag gewonnen wird. Ein Nachlauf-Zeitstempel verrueckt damit die
    Reihenfolge der Ursachen im Wissensgraphen — auf genau der Achse, auf der die
    naechste Ereignisketten-Rekonstruktion aufsetzt.
    """
    for art in ERKENNTNIS_ARTEN:
        assert ZEIT_FELDER[art] == "created_at", art
        nutzlast = {"machine_id": 1, "created_at": "2026-09-02T11:30:00+00:00"}
        assert ereigniszeit(art, nutzlast) == "2026-09-02T11:30:00+00:00", art


@pytest.mark.parametrize(
    ("art", "nutzlast", "erwartet"),
    [
        (
            "worker_note",
            {"created_at": "2026-05-28T07:20:00+00:00", "machine_id": 3, "text": "x"},
            "2026-05-28T07:20:00+00:00",
        ),
        (
            "alarm_raised",
            {"raised_at": "2026-06-01T12:00:00+00:00", "code": "X", "machine_id": 1},
            "2026-06-01T12:00:00+00:00",
        ),
        (
            "maintenance_performed",
            {"performed_at": "2026-06-02T08:00:00+00:00", "type": "y", "machine_id": 1},
            "2026-06-02T08:00:00+00:00",
        ),
        (
            "production_run",
            {"started_at": "2026-06-03T06:00:00+00:00", "line_id": 1},
            "2026-06-03T06:00:00+00:00",
        ),
        # Die ABWEICHUNG ist eine Ableitung und traegt trotzdem eine echte
        # Hallenzeit: `detected_at` ist `sample.bucket` aus `readings_1m`.
        (
            "drift_detected",
            {"detected_at": "2026-06-04T09:00:00+00:00", "machine_id": 3, "data_point_id": 42},
            "2026-06-04T09:00:00+00:00",
        ),
    ],
)
def test_die_zeit_kommt_aus_dem_richtigen_feld(art: str, nutzlast: dict, erwartet: str) -> None:
    """Jede Ereignisart traegt ihren Zeitpunkt unter einem ANDEREN Namen.

    Genau darin lag der Fehler: Wer nur `created_at` liest, verliert Alarm,
    Wartung und Produktionslauf — und zwar lautlos, weil die Spiegelung
    weiterlaeuft und nur die Zeit fehlt.
    """
    assert ereigniszeit(art, nutzlast) == erwartet


# ──────────────────────────────────────────────────────────────────────
#  Wo es keine Zeit gibt, wird keine erfunden
# ──────────────────────────────────────────────────────────────────────


def test_erkenntnis_arten_erfinden_keine_zeit() -> None:
    """AUFBAU-KONTROLLE zum Fall oben: Fehlt `created_at`, wird nichts erfunden.

    Ohne diesen Fall bliebe der tragende Fall auch dann gruen, wenn
    `ereigniszeit` fuer diese Arten irgendeinen Wert lieferte. Und die Spiegelung
    darf an einer unvollstaendigen Nutzlast nicht scheitern: Sie laeuft dann mit
    der Eingangszeit weiter, so wie bisher.
    """
    for art in ERKENNTNIS_ARTEN:
        assert ereigniszeit(art, {"machine_id": 1, "prediction_id": 7}) is None, art


def test_die_abweichung_traegt_die_hallenzeit_nicht_die_laufzeit() -> None:
    """Der Fall, an dem es haengt.

    Der einzige Einstieg in den Drift-Reasoner ist ein Wiederholungslauf ueber
    einen historischen Zeitraum (`drift/runner.py::replay_machine`). Ohne
    `detected_at` bekaemen ALLE Befunde eines Laufs denselben Zeitstempel — den
    des Laufs — und der gesamte Drift-Bestand laege auf einem Punkt der
    Zeitachse. Genau dieses Muster hat beim Nachtrag schon einmal den halben
    Bestand in dieselbe Stunde gelegt.
    """
    assert ZEIT_FELDER["drift_detected"] == "detected_at"
    nutzlast = {
        "reasoner": "drift",
        "source_type": "drift",
        "source_id": None,
        "machine_id": 3,
        "data_point_id": 42,
        "detected_at": "2026-06-04T09:00:00+00:00",
        "effect_size": 1.83,
    }
    assert ereigniszeit("drift_detected", nutzlast) == "2026-06-04T09:00:00+00:00", (
        "❌ Die Abweichung traegt die Zeit des Rechnens statt der Halle. Bei einem "
        "Wiederholungslauf liegt damit jeder Drift-Befund auf demselben Zeitpunkt."
    )


def test_fehlendes_feld_wirft_nicht() -> None:
    """Eine unvollstaendige Nutzlast darf die Spiegelung nicht verhindern.

    Anders als `baue_inhalt`, das auf dem Schreibweg absichtlich wirft: Ohne
    Zeitangabe ist der Eintrag weiterhin brauchbar, er landet nur mit der
    Eingangszeit — also so wie vor dieser Aenderung.
    """
    assert ereigniszeit("worker_note", {"machine_id": 1}) is None
    assert ereigniszeit("worker_note", {"created_at": ""}) is None
    assert ereigniszeit("unbekannte_art", {"created_at": "2026-01-01T00:00:00+00:00"}) is None


# ──────────────────────────────────────────────────────────────────────
#  Und der eigentliche Punkt: Sie muss beim Substrat ANKOMMEN
# ──────────────────────────────────────────────────────────────────────


class _Mitschrift:
    """Merkt sich, WAS beim Substrat ankam — nicht nur, DASS etwas ankam."""

    def __init__(self) -> None:
        self.aufrufe: list[dict[str, Any]] = []

    async def remember(
        self,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
        occurred_at: str | None = None,
    ) -> dict[str, Any]:
        self.aufrufe.append({"content": content, "metadata": metadata, "occurred_at": occurred_at})
        return {"id": "ref-1"}


@pytest.mark.asyncio
async def test_die_ereigniszeit_erreicht_das_substrat(monkeypatch: pytest.MonkeyPatch) -> None:
    """DER TRAGENDE FALL.

    Die vorigen Faelle pruefen die Abbildung. Dieser prueft den WEG: Kaeme die
    Zeit richtig aus der Nutzlast und ginge dann nicht mit, waere alles darueber
    gruen und der Fehler unveraendert da. Genau so war der Zustand bis heute —
    `created_at` stand in den Metadaten und erreichte das Feld nie.
    """
    from foreman.ingestion import semantic

    substrat = _Mitschrift()

    class _Sitzung:
        def add(self, _obj: object) -> None: ...
        async def flush(self) -> None: ...

    monkeypatch.setattr(semantic, "SemanticEvent", lambda **k: object())

    await semantic.record_semantic_event(
        _Sitzung(),  # type: ignore[arg-type]
        machine_id=3,
        event_type="worker_note",
        payload={
            "machine_id": 3,
            "text": "AX-03 laeuft unruhig",
            "created_at": "2026-05-28T07:20:00+00:00",
        },
        substrate=substrat,  # type: ignore[arg-type]
    )

    assert len(substrat.aufrufe) == 1
    assert substrat.aufrufe[0]["occurred_at"] == "2026-05-28T07:20:00+00:00", (
        "❌ Die Ereigniszeit erreicht das Substrat nicht. Dann traegt dort jeder "
        "Eintrag den Zeitpunkt des Spiegelns, und jede zeitliche Auswertung "
        "beschreibt den Spiegel-Lauf statt den Betrieb."
    )


# ──────────────────────────────────────────────────────────────────────
#  Ohne Zeitzone wird nichts gesendet
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("wert", "erwartet"),
    [
        ("2026-06-04T09:00:00+00:00", "2026-06-04T09:00:00+00:00"),
        ("2026-06-04T09:00:00+02:00", "2026-06-04T09:00:00+02:00"),
        # `Z` ist eine gueltige Zonenangabe. Ein Muster haette sie leicht
        # uebersehen — und dann verloere der Eintrag still seine Zeit.
        ("2026-06-04T09:00:00Z", "2026-06-04T09:00:00Z"),
        ("2026-06-04T09:00:00", None),
        ("vorgestern", None),
        ("", None),
    ],
)
def test_nur_zeiten_mit_zone_gehen_hinaus(wert: str, erwartet: str | None) -> None:
    """Die Gegenstelle weist eine Zeitangabe ohne Zone mit 422 ab.

    WAS DAS KOSTET, und es ist mehr als die Zeit: `_post` wirft,
    `record_semantic_event` faengt, und die Zeile bekommt `substrate_ref=NULL`.
    Das Ereignis fehlt dann im Gedaechtnis VOLLSTAENDIG — wegen eines fehlenden
    Zonen-Anhaengsels. Lieber ohne Zeitangabe gespiegelt als gar nicht.

    Heute ist der Fall theoretisch: Alle Quellspalten sind
    `DateTime(timezone=True)`. Die Pruefung steht da, weil die Nutzlast auch aus
    dem Altbestand kommt und niemand nachsehen wird, bevor er ein neues Zeitfeld
    eintraegt.
    """
    assert ereigniszeit("drift_detected", {"detected_at": wert}) == erwartet
