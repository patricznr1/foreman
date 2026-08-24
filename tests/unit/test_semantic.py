# ============================================================
#  FOREMAN — tests/unit/test_semantic.py
#  Zweck: Pflicht-Test-Block für die Substrat-Referenz-Extraktion (F3).
#  Prüft: extract_substrate_ref deckt die Antwort-Varianten ab (id/memory_id/
#  result/int) und liefert None bei fehlender/leerer Referenz.
#  Architektur-Einordnung: Quality Gate §10.3.
# ============================================================
from __future__ import annotations

from typing import Any

import pytest

from foreman.ingestion.semantic import extract_substrate_ref, record_semantic_event


def test_extract_ref_aus_id() -> None:
    assert extract_substrate_ref({"id": "abc-123"}) == "abc-123"


def test_extract_ref_priorisiert_id_vor_result() -> None:
    assert extract_substrate_ref({"result": "r", "id": "primary"}) == "primary"


def test_extract_ref_aus_alternativen_schluesseln() -> None:
    assert extract_substrate_ref({"memory_id": "m1"}) == "m1"
    assert extract_substrate_ref({"entry_id": "e1"}) == "e1"
    assert extract_substrate_ref({"uuid": "u1"}) == "u1"
    assert extract_substrate_ref({"result": "res"}) == "res"


def test_extract_ref_int_wird_zu_string() -> None:
    assert extract_substrate_ref({"id": 42}) == "42"


def test_extract_ref_none_bei_fehlender_oder_leerer_referenz() -> None:
    assert extract_substrate_ref({}) is None
    assert extract_substrate_ref({"id": ""}) is None  # leerer String zählt nicht
    assert extract_substrate_ref({"foo": "bar"}) is None


def test_extract_ref_ignoriert_bool() -> None:
    # bool ist int-Subtyp — eine True/False-"Referenz" ist Unsinn, wird übersprungen.
    assert extract_substrate_ref({"id": True}) is None
    assert extract_substrate_ref({"id": False, "memory_id": "m1"}) == "m1"


# ------------------------------------------------------------
#  Die Spiegel-Zeile entsteht IMMER — auch wenn die Formulierung scheitert
# ------------------------------------------------------------


class _SammelSession:
    """Minimale Session: merkt sich nur, was hinzugefügt wurde."""

    def __init__(self) -> None:
        self.hinzugefuegt: list[Any] = []

    def add(self, obj: Any) -> None:
        self.hinzugefuegt.append(obj)


async def test_unbekannter_event_type_verhindert_die_db_zeile_nicht() -> None:
    """Ein Formulierungsfehler darf den Aufrufer nicht mitreißen.

    ANLASS: `baue_inhalt` lag VOR dem try. Ein unbekannter event_type oder ein
    fehlendes Pflichtfeld in der payload warf damit aus `record_semantic_event`
    heraus — und riss den Insert des Aufrufers mit. Beim Werker-Notiz-Pfad wäre
    das der Kernpfad der Halle: Der Werker bekäme einen Fehler, weil eine
    Spiegelung nicht formulierbar ist.

    Die Zusage lautet "Die DB-Zeile entsteht IMMER". Sie gilt jetzt auch hier.
    """
    session = _SammelSession()
    ereignis = record_semantic_event(
        session,  # type: ignore[arg-type]
        machine_id=7,
        event_type="gibt_es_nicht",
        payload={"machine_id": 7},
    )
    ergebnis = await ereignis
    assert len(session.hinzugefuegt) == 1
    assert ergebnis.event_type == "gibt_es_nicht"
    assert ergebnis.substrate_ref is None


async def test_unvollstaendige_payload_verhindert_die_db_zeile_nicht() -> None:
    """Aufbau-Kontrolle: derselbe Schutz für den zweiten Fehlerweg.

    Der event_type ist hier bekannt — es fehlt ein Pflichtfeld. `baue_inhalt`
    greift hart auf die Felder zu (bewusst, statt '?' zu erfinden), wirft also
    KeyError. Ohne diesen Test wäre nur der Registry-Weg abgedeckt.
    """
    session = _SammelSession()
    ergebnis = await record_semantic_event(
        session,  # type: ignore[arg-type]
        machine_id=3,
        event_type="alarm_raised",
        payload={"machine_id": 3},  # code/severity/category/raised_at fehlen
    )
    assert len(session.hinzugefuegt) == 1
    assert ergebnis.substrate_ref is None
