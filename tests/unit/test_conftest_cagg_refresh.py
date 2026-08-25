# ============================================================
#  FOREMAN — tests/unit/test_conftest_cagg_refresh.py
#  Zweck: Pflicht-Test-Block für die Wiederholung des CAGG-Refresh in der
#         Test-Infrastruktur (tests/conftest.py). Der Docstring dort sichert drei
#         Dinge zu — dass ein Sperrkonflikt wiederholt wird, dass jede andere
#         Ursache SOFORT durchschlägt, und dass nach den Versuchen geworfen statt
#         verschluckt wird. Zusicherungen im Kommentar sind Behauptungen; hier
#         werden sie eingefordert.
#  Architektur-Einordnung: Quality Gate §10.3 (Test-Infrastruktur).
#  KEIN Integrationstest: Die Wiederholung wird gegen ein Verbindungs-Doppel
#         geprüft. Ein echter Wettlauf mit dem Hintergrund-Scheduler liesse sich
#         nicht verlässlich herstellen — und ein Test, der ihn nur manchmal
#         auslöst, belegt nichts.
# ============================================================
from __future__ import annotations

from typing import Any

import pytest
from sqlalchemy.exc import DBAPIError
from tests.conftest import _CAGG_VERSUCHE, _refresh_mit_wiederholung


class _SperrkonfliktError(Exception):
    """Steht für den Originalfehler des Treibers; nur `sqlstate` zählt."""

    def __init__(self, sqlstate: str) -> None:
        super().__init__(f"Fehler {sqlstate}")
        self.sqlstate = sqlstate


def _fehler(sqlstate: str) -> DBAPIError:
    return DBAPIError("CALL refresh…", {}, _SperrkonfliktError(sqlstate))


class _Verbindung:
    """Verbindungs-Doppel: scheitert die ersten `scheitert_oft` Male."""

    def __init__(self, *, scheitert_oft: int, sqlstate: str = "55P03") -> None:
        self.versuche = 0
        self._scheitert_oft = scheitert_oft
        self._sqlstate = sqlstate

    async def execute(self, _anweisung: Any) -> None:
        self.versuche += 1
        if self.versuche <= self._scheitert_oft:
            raise _fehler(self._sqlstate)


async def test_sperrkonflikt_wird_wiederholt_und_gelingt_dann() -> None:
    """Der Regelfall: Der fremde Lauf ist fertig, der zweite Anlauf greift durch."""
    conn = _Verbindung(scheitert_oft=2)
    await _refresh_mit_wiederholung(conn, "readings_1m")  # type: ignore[arg-type]
    assert conn.versuche == 3, "es wurde nicht bis zum Erfolg wiederholt"


async def test_dauerhafter_sperrkonflikt_wirft_statt_zu_verschlucken() -> None:
    """Nach den Versuchen fliegt die Ausnahme weiter.

    Ein still übersprungener Reset hinterliesse materialisierte Buckets, und die
    tauchen später als Geister-Werte eines fremden Datenpunkts auf — ein Fehler,
    der weit schwerer zu finden wäre als ein roter Aufbau.
    """
    conn = _Verbindung(scheitert_oft=_CAGG_VERSUCHE + 5)
    with pytest.raises(DBAPIError):
        await _refresh_mit_wiederholung(conn, "readings_1m")  # type: ignore[arg-type]
    assert conn.versuche == _CAGG_VERSUCHE, "es wurde öfter versucht als vorgesehen"


@pytest.mark.parametrize("sqlstate", ["42P01", "23505", "57014", "08006"])
async def test_andere_ursachen_schlagen_sofort_durch(sqlstate: str) -> None:
    """AUFBAU-KONTROLLE zur Wiederholung — die wichtigere Hälfte.

    Ohne diesen Fall wäre „ein Sperrkonflikt wird wiederholt" auch mit „alles wird
    wiederholt" erklärbar. Eine fehlende Tabelle oder ein abgebrochener Befehl
    wird durch Warten nicht besser; die Wiederholung verzögerte nur den Befund
    und verwischte seine Ursache.
    """
    conn = _Verbindung(scheitert_oft=99, sqlstate=sqlstate)
    with pytest.raises(DBAPIError):
        await _refresh_mit_wiederholung(conn, "readings_1m")  # type: ignore[arg-type]
    assert conn.versuche == 1, f"SQLSTATE {sqlstate} wurde fälschlich wiederholt"


async def test_gelingt_der_erste_anlauf_wird_nicht_wiederholt() -> None:
    """Der Normalfall kostet keinen zusätzlichen Aufruf."""
    conn = _Verbindung(scheitert_oft=0)
    await _refresh_mit_wiederholung(conn, "readings_1m")  # type: ignore[arg-type]
    assert conn.versuche == 1
