# ============================================================
#  FOREMAN — tests/core/test_sanitize.py
#  Zweck: Output-Sanitisierung untrusted Freitexts (core/sanitize.py, LLM05).
#  Kontext: dieselbe Funktion bedient ab der Substrat-Veredelung den Reasoner-
#         UND den Archiv-Pfad. Die Reihenfolge-Zusicherung im Docstring ist
#         hier eingefordert, nicht nur behauptet.
# ============================================================
from __future__ import annotations

import pytest

from foreman.core.sanitize import EXCERPT_MAX_LEN, clean_excerpt


def test_html_markdown_und_url_verschwinden() -> None:
    roh = "Lager <script>alert(1)</script> heiß, siehe [Doku](https://x.test/a) und http://y.test/b"
    aus = clean_excerpt(roh)
    assert "<script>" not in aus
    assert "alert(1)" in aus  # der Tag geht, sein Textinhalt bleibt lesbar
    assert "https://x.test/a" not in aus
    assert "Doku" in aus  # Markdown-Link auf den Linktext reduziert
    assert aus.count("[link entfernt]") == 1


@pytest.mark.parametrize(
    "schema",
    ["javascript:", "data:text/html;base64,", "vbscript:", "file:///etc/passwd", "ftp://x.test/a"],
)
def test_gefaehrliche_schemata_werden_ersetzt(schema: str) -> None:
    aus = clean_excerpt(f"Hinweis {schema}payload hier")
    assert schema.split(":")[0] not in aus.lower()
    assert "[link entfernt]" in aus


def test_reihenfolge_markdown_vor_url_haelt_die_zieladresse_raus() -> None:
    """Die tragende Zusicherung des Docstrings.

    Würde erst die URL ersetzt und dann der Markdown-Link aufgelöst, bliebe aus
    `[Klick](javascript:steal())` die Zieladresse als Klartext im Auszug stehen.
    Der Test hält die Reihenfolge fest, nicht nur ihre Beschreibung.
    """
    aus = clean_excerpt("[Klick mich](javascript:steal())")
    assert aus == "Klick mich"
    assert "javascript" not in aus.lower()
    assert "steal" not in aus


def test_kuerzung_mit_ellipsis() -> None:
    aus = clean_excerpt("a" * 500, max_len=50)
    assert len(aus) == 50
    assert aus.endswith("…")


def test_whitespace_wird_normalisiert() -> None:
    assert clean_excerpt("a  \n\t b") == "a b"


def test_ner_marker_bleiben_stehen() -> None:
    """`[PERSON]` ist kein Markdown-Link und darf nicht verschwinden —
    er ist das Ergebnis der Maskierung, nicht ihr Gegenstand."""
    assert "[PERSON]" in clean_excerpt("Notiz von [PERSON] zur Achse")


def test_standardlaenge_ist_die_geteilte_konstante() -> None:
    assert len(clean_excerpt("b" * (EXCERPT_MAX_LEN + 100))) == EXCERPT_MAX_LEN


@pytest.mark.parametrize(
    ("roh", "erwartet"),
    [
        ("[Klick](javascript:steal())", "Klick"),
        ("[Wiki](https://x.test/Sembach_(Pfalz))", "Wiki"),
        ("[a](http://x.test/p(1)/q)", "a"),
        ("![Bild](https://x.test/b.png)", "Bild"),
    ],
)
def test_klammern_im_linkziel_lassen_keinen_rest(roh: str, erwartet: str) -> None:
    """Befund 20.08.2026: `[^)]*` endete an der ERSTEN schließenden Klammer.

    Die Zieladresse verschwand zwar, aber ein Klammer-Rest blieb im Auszug —
    bei jedem Link mit Klammern im Ziel. Eine Verschachtelungsebene reicht für
    alle real vorkommenden Formen.
    """
    assert clean_excerpt(roh) == erwartet
