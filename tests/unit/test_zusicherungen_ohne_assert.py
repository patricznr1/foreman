# ══════════════════════════════════════════════════════════════
# FOREMAN — Zusicherungen im heißen Pfad überleben `python -O`
# Was der Betrieb braucht, darf nicht wegoptimierbar sein.
# ══════════════════════════════════════════════════════════════
"""Belegt, dass zwei Prüfungen im heißen Pfad als `raise` und nicht als `assert`
formuliert sind.

WARUM DAS ZÄHLT. Unter `python -O` bzw. gesetztem `PYTHONOPTIMIZE` werden
`assert`-Anweisungen nicht ausgeführt — ersatzlos. Eine Prüfung, die dort eine
klare Meldung liefern soll, liefert dann gar nichts, und der Fehler taucht später
und schwerer lesbar auf. Heute setzt weder das Image noch die Plattform diesen
Schalter; das ist eine Falle für später, kein aktueller Mangel.

WIE HIER GEPRÜFT WIRD. Nicht über den Quelltext — eine Textsuche fände das Wort
`assert` auch im Kommentar, der es erklärt. Geprüft wird das VERHALTEN: Die
Prüfung wird verletzt und die erwartete Ausnahme eingefordert.
"""

from __future__ import annotations

import pytest

from foreman.db import session as db_session
from foreman.llm.errors import RateLimited
from foreman.main import _gateway_rate_limited_handler


def test_fehlende_session_factory_meldet_sich_klar(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bleibt die Factory nach dem Aufbau leer, endet der Zugriff mit klarer Meldung."""
    monkeypatch.setattr(db_session, "_sessionmaker", None)
    monkeypatch.setattr(db_session, "init_engine", lambda *_a, **_k: None)

    with pytest.raises(RuntimeError, match="nicht initialisiert"):
        db_session.get_sessionmaker()


def test_vorhandene_session_factory_wird_geliefert(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zwilling: Der Regelfall bleibt unberührt.

    Ohne ihn wäre der Test darüber auch dann grün, wenn die Funktion IMMER
    aufgäbe — und der gesamte Datenzugriff läge still.
    """
    attrappe = object()
    monkeypatch.setattr(db_session, "_sessionmaker", attrappe)

    assert db_session.get_sessionmaker() is attrappe


async def test_drosselungs_handler_weist_einen_fremden_typ_ab() -> None:
    """Der Handler ist für genau einen Ausnahmetyp registriert und sagt das auch."""
    with pytest.raises(TypeError, match="RateLimited"):
        await _gateway_rate_limited_handler(None, ValueError("fremd"))  # type: ignore[arg-type]


async def test_drosselungs_handler_antwortet_auf_den_eigenen_typ() -> None:
    """Zwilling: Der eigentliche Fall liefert weiter 429 samt Wartehinweis."""
    antwort = await _gateway_rate_limited_handler(
        None,  # type: ignore[arg-type]
        RateLimited("gedrosselt", retry_after_s=2.4),
    )

    assert antwort.status_code == 429
