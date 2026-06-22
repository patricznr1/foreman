# ============================================================
#  FOREMAN — tests/reasoners/event_chain/test_siblings.py
#  Zweck: Reine Logik der ehrlichen Schwester-Referenzen (§21-D) — Extraktion
#         strukturierter Recall-Metadaten + Form der SiblingReference. Ohne Netz,
#         ohne DB. Kern-Invariante: KEINE erfundenen Geschwister — nur was der
#         Recall real hergibt; fehlende Bezüge bleiben None.
# ============================================================
from __future__ import annotations

from foreman.db.models import Alarm, Machine
from foreman.reasoners.event_chain.recall import (
    RecallItem,
    build_sibling_references,
    clean_excerpt,
    map_recall_response,
    sibling_similarity_basis,
)


# ----------------------------------------------------------------
#  map_recall_response — strukturierte Metadaten (defensiv, nur wenn real da)
# ----------------------------------------------------------------
def test_map_recall_response_zieht_metadaten_aus_metadata_container() -> None:
    data = {
        "results": [
            {
                "content": "Schwesterfall A",
                "id": "mem-1",
                "metadata": {"machine_id": 7, "machine_class": "cnc", "explanation_id": 42},
            }
        ]
    }
    items = map_recall_response(data, max_results=5)
    assert len(items) == 1
    assert items[0].machine_id == 7
    assert items[0].machine_class == "cnc"
    assert items[0].explanation_id == 42
    assert items[0].ref == "mem-1"


def test_map_recall_response_flach_und_payload_und_numerische_strings() -> None:
    flach = {"memories": [{"text": "Fall B", "machine_id": 9}]}
    assert map_recall_response(flach, max_results=5)[0].machine_id == 9
    payload = {
        "items": [{"summary": "Fall C", "payload": {"machine_id": "11", "explanation_id": "5"}}]
    }
    item = map_recall_response(payload, max_results=5)[0]
    assert item.machine_id == 11
    assert item.explanation_id == 5


def test_map_recall_response_ohne_metadaten_bleibt_alles_none() -> None:
    data = {"results": [{"content": "nur Text"}, "reiner String"]}
    items = map_recall_response(data, max_results=5)
    assert len(items) == 2
    for item in items:
        assert item.machine_id is None
        assert item.machine_class is None
        assert item.explanation_id is None


def test_map_recall_response_bool_nie_als_id() -> None:
    # bool ist ein int-Subtyp — darf nie als Maschinen-/Erklärungs-ID durchgehen.
    data = {"results": [{"content": "x", "machine_id": True, "explanation_id": False}]}
    item = map_recall_response(data, max_results=5)[0]
    assert item.machine_id is None
    assert item.explanation_id is None


# ----------------------------------------------------------------
#  build_sibling_references — ehrliche Form, keine Erfindung
# ----------------------------------------------------------------
def test_build_sibling_references_leer_bei_keinen_treffern() -> None:
    # Kern: kein Recall → leere strukturierte Liste, KEIN Platzhalter.
    assert build_sibling_references([], basis="x") == []


def test_build_sibling_references_ehrlich_null_wenn_keine_bezuege() -> None:
    items = [RecallItem(content="Fall ohne Bezug", ref="m1")]
    siblings = build_sibling_references(items, basis="Ähnlich anhand: Maschinenklasse cnc")
    assert len(siblings) == 1
    sibling = siblings[0]
    assert sibling.machine_id is None
    assert sibling.machine_class is None
    assert sibling.explanation_id is None
    assert sibling.recall_ref == "m1"
    assert sibling.similarity_basis == "Ähnlich anhand: Maschinenklasse cnc"
    assert sibling.excerpt == "Fall ohne Bezug"


def test_build_sibling_references_loest_klasse_und_erklaerung_auf() -> None:
    items = [RecallItem(content="Schwesterfall", ref="m2", machine_id=7)]
    siblings = build_sibling_references(
        items, basis="b", class_by_machine={7: "cnc"}, explanation_by_machine={7: 99}
    )
    assert siblings[0].machine_id == 7
    assert siblings[0].machine_class == "cnc"
    assert siblings[0].explanation_id == 99


def test_build_sibling_references_treffer_metadaten_haben_vorrang() -> None:
    # Trägt der Treffer selbst die Felder, überschreibt die DB-Auflösung sie NICHT.
    items = [RecallItem(content="x", machine_id=7, machine_class="laser", explanation_id=5)]
    siblings = build_sibling_references(
        items, basis="b", class_by_machine={7: "cnc"}, explanation_by_machine={7: 99}
    )
    assert siblings[0].machine_class == "laser"
    assert siblings[0].explanation_id == 5


def test_build_sibling_references_anzahl_entspricht_treffern() -> None:
    # ⊆ reale Recall-Treffer: genau eine Referenz je Treffer, keine zusätzliche.
    items = [RecallItem(content=f"Fall {i}") for i in range(3)]
    assert len(build_sibling_references(items, basis="b")) == 3


# ----------------------------------------------------------------
#  clean_excerpt — Output-Sanitisierung des untrusted Auszugs
# ----------------------------------------------------------------
def test_clean_excerpt_sanitisiert_html_markdown_url() -> None:
    raw = "Hinweis <b>x</b> ![bild](http://evil.example/leak) siehe http://evil.example   Ende"
    out = clean_excerpt(raw)
    assert "<b>" not in out
    assert "http://evil.example" not in out
    assert "](http" not in out
    assert "  " not in out  # Whitespace normalisiert


def test_clean_excerpt_kuerzt_mit_ellipsis() -> None:
    out = clean_excerpt("a" * 500, max_len=50)
    assert len(out) <= 50
    assert out.endswith("…")


# ----------------------------------------------------------------
#  sibling_similarity_basis — ehrliche, PII-freie Ähnlichkeits-Basis
# ----------------------------------------------------------------
def test_sibling_similarity_basis_komposition() -> None:
    machine = Machine(label="M", machine_class="cnc")
    anchor = Alarm(machine_id=1, severity="warning", category="process", code="DRIFT")
    basis = sibling_similarity_basis(anchor, machine)
    assert "Maschinenklasse cnc" in basis
    assert "DRIFT" in basis
    assert "process" in basis


def test_sibling_similarity_basis_fallback_ohne_merkmale() -> None:
    anchor = Alarm(machine_id=1, severity="warning", category="")
    assert sibling_similarity_basis(anchor, None) == "ähnliches Vorfall-Muster"
