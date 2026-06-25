# ============================================================
#  FOREMAN — tests/unit/test_semantic.py
#  Zweck: Pflicht-Test-Block für die Substrat-Referenz-Extraktion (F3).
#  Prüft: extract_substrate_ref deckt die Antwort-Varianten ab (id/memory_id/
#  result/int) und liefert None bei fehlender/leerer Referenz.
#  Architektur-Einordnung: Quality Gate §10.3.
# ============================================================
from __future__ import annotations

from foreman.ingestion.semantic import extract_substrate_ref


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
