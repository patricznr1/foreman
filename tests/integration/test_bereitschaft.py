# ============================================================
#  FOREMAN — tests/integration/test_bereitschaft.py
#  Zweck: Die beiden Sonden beantworten verschiedene Fragen, §4. /health sagt, ob
#         der Prozess lebt; /readyz, ob er arbeiten kann. Geprüft wird beides —
#         und vor allem, dass sie sich bei einem Datenbank-Ausfall UNTERSCHIEDLICH
#         verhalten. Täten sie das nicht, wäre die Trennung Zierde.
#  Architektur-Einordnung: Quality Gate §10.3 (Integration, braucht DB).
# ============================================================
from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy.exc import OperationalError

from foreman.db.session import get_session

pytestmark = pytest.mark.integration


class _ToteSitzung:
    """Sitzung, deren Ausführung so scheitert wie eine weggebrochene Datenbank.

    Kein Mock der Sonde, sondern der Gegenstelle: Der Endpunkt läuft unverändert
    und trifft auf eine Sitzung, die wirft — dieselbe Ausnahmeklasse, die SQLAlchemy
    bei einer unterbrochenen Verbindung liefert.
    """

    async def execute(self, *_args: object, **_kwargs: object) -> object:
        raise OperationalError("SELECT 1", {}, Exception("Verbindung weg"))


async def test_lebendigkeit_antwortet_ohne_datenbank(app: FastAPI, client: AsyncClient) -> None:
    """/health bleibt grün, auch wenn die Datenbank weg ist — das ist der Zweck.

    Hinge die Lebendigkeitssonde an der Datenbank, tötete der Orchestrierer einen
    gesunden Prozess, weil eine andere Komponente ausgefallen ist. Der Neustart
    behöbe nichts, weil der Prozess nie das Problem war.
    """
    app.dependency_overrides[get_session] = lambda: _ToteSitzung()
    try:
        antwort = await client.get("/health")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["status"] == "ok"


async def test_bereitschaft_meldet_den_datenbank_ausfall(app: FastAPI, client: AsyncClient) -> None:
    """/readyz wird 503, sobald die Datenbank nicht antwortet.

    Das ist die Frage, die vorher niemand stellte: Der einzige Prober zeigte auf
    /health und blieb bei einem Datenbank-Ausfall grün, während jede Anfrage in
    einen Fehler lief.
    """
    app.dependency_overrides[get_session] = lambda: _ToteSitzung()
    try:
        antwort = await client.get("/readyz")
    finally:
        app.dependency_overrides.pop(get_session, None)

    assert antwort.status_code == 503, antwort.text
    assert antwort.json()["status"] == "unavailable"


async def test_bereitschaft_nennt_den_grund_nicht(app: FastAPI, client: AsyncClient) -> None:
    """Der Grund steht im Log, nicht in der Antwort.

    Ein Prober braucht ihn nicht, und nach außen ginge sonst der Zustand der
    Infrastruktur heraus — dieselbe Linie wie bei den Gateway-Fehlern (§8).
    """
    app.dependency_overrides[get_session] = lambda: _ToteSitzung()
    try:
        antwort = await client.get("/readyz")
    finally:
        app.dependency_overrides.pop(get_session, None)

    rumpf = antwort.text.lower()
    for verraeter in ("select", "operational", "postgres", "asyncpg", "verbindung", "traceback"):
        assert verraeter not in rumpf, f"❌ Die Antwort verrät Infrastruktur-Interna: {verraeter}"


async def test_bereitschaft_ist_gruen_wenn_die_datenbank_antwortet(client: AsyncClient) -> None:
    """Kontroll-Zwilling: Gegen die echte Testdatenbank meldet die Sonde „bereit".

    Ohne ihn bliebe der Test darüber auch dann grün, wenn /readyz aus einem ganz
    anderen Grund immer 503 lieferte — etwa weil der Endpunkt gar nicht existiert.
    """
    antwort = await client.get("/readyz")

    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["status"] == "ready"


async def test_beide_sonden_brauchen_kein_token(client: AsyncClient) -> None:
    """Ein Prober hat kein Token und soll keines haben.

    Beide Sonden stehen deshalb in OPEN_PATHS. Der Test hält fest, dass sie dort
    BLEIBEN: Wandert eine hinter die Auth-Middleware, meldet der Prober von da an
    401 und die Plattform hält den Dienst für tot.
    """
    for pfad in ("/health", "/readyz"):
        antwort = await client.get(pfad)
        assert antwort.status_code != 401, (
            f"❌ {pfad} verlangt ein Token — ein Prober hat keines, und die Plattform "
            "läse das als Ausfall."
        )
