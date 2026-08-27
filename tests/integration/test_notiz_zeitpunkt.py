# ============================================================
#  FOREMAN — tests/integration/test_notiz_zeitpunkt.py
#  Zweck: Eine über HTTP nachgetragene Schichtnotiz trägt die Zeit der SCHICHT,
#         nicht die des Eintragens.
#  ANLASS (27.08.2026): `WorkerNoteCreate` führte kein Zeitfeld. Der Adapter-Weg
#         setzt die historische Zeit seit jeher von Hand (`ingestion/service.py`,
#         „created_at sonst server-default now()"), die HTTP-Schicht konnte es
#         nicht — dieselbe Klasse wie die fehlende Spiegelung in den CRUD-Wegen.
#         Wirkung: Wer eine Notiz für die gestrige Schicht einträgt, bekam den
#         Eintragungszeitpunkt. Das Archiv ordnet Notiz-Treffer nach
#         `created_at`; die Reihenfolge eines Störungsvorgangs bricht damit
#         STILL — kein Fehler, keine Meldung, nur eine falsche Chronologie.
#  Architektur-Einordnung: Quality Gate §10.3, Schreibpfad §4.
# ============================================================
from __future__ import annotations

import datetime as dt
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from foreman.config import Settings
from foreman.db.models import SemanticEvent, WorkerNote

pytestmark = pytest.mark.integration

# Eine Schicht aus dem Februar — weit genug weg, dass eine Verwechslung mit
# „jetzt" nicht durch Zufall durchgeht.
SCHICHT = dt.datetime(2026, 2, 9, 7, 15, tzinfo=dt.timezone(dt.timedelta(hours=1)))


@asynccontextmanager
async def _lese_sitzung(test_settings: Settings) -> AsyncIterator[AsyncSession]:
    """Eigene Lese-Sitzung — nicht `db_session`, die hängt an `clean_db`.

    Dieselbe Begründung wie in `test_spiegelung_schreibwege.py`: Zwei Fixturen,
    die beide den Bestand bestimmen wollen, vertragen sich nicht — `clean_db`
    nähme den Testnutzer mit, den `auth_client` angelegt hat.
    """
    engine = create_async_engine(test_settings.database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            yield session
    finally:
        await engine.dispose()


async def _maschine(c: AsyncClient) -> int:
    r = await c.post(
        "/api/v1/machines",
        json={"label": "Handling-Achse 7", "line_id": None, "machine_class": "servo_axis"},
    )
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


async def _notiz(test_settings: Settings, notiz_id: int) -> WorkerNote:
    async with _lese_sitzung(test_settings) as session:
        obj = await session.get(WorkerNote, notiz_id)
        assert obj is not None
        return obj


# ──────────────────────────────────────────────────────────────────────
#  Die Sache
# ──────────────────────────────────────────────────────────────────────


async def test_nachgetragene_notiz_traegt_die_schichtzeit(
    auth_client: AsyncClient, test_settings: Settings
) -> None:
    """Der eigentliche Fall: eine Notiz für eine vergangene Schicht."""
    machine_id = await _maschine(auth_client)

    r = await auth_client.post(
        "/api/v1/worker_notes",
        json={
            "text": "AX-02 hat beim Verfahren einen hohen Ton drauf.",
            "machine_id": machine_id,
            "shift": "frueh",
            "occurred_at": SCHICHT.isoformat(),
        },
    )
    assert r.status_code == 201, r.text

    obj = await _notiz(test_settings, int(r.json()["id"]))
    assert obj.created_at.astimezone(dt.UTC) == SCHICHT.astimezone(dt.UTC), (
        "Die Notiz trägt den Eintragungszeitpunkt statt der Schichtzeit"
    )


async def test_ohne_zeitangabe_gilt_weiterhin_jetzt(
    auth_client: AsyncClient, test_settings: Settings
) -> None:
    """AUFBAU-KONTROLLE: Das neue Feld darf den Regelfall nicht verändern.

    Aus der Halle kommt die Notiz OHNE Zeitangabe, und dann muss der
    Server-Default greifen. Ohne diesen Fall liesse sich später ein Pflichtfeld
    daraus machen, ohne dass es jemandem auffiele — und jeder Werker bekäme eine
    422 für eine Notiz, die er gerade schreibt.
    """
    machine_id = await _maschine(auth_client)
    vorher = dt.datetime.now(dt.UTC)

    r = await auth_client.post(
        "/api/v1/worker_notes",
        json={"text": "Schicht ohne Auffälligkeiten.", "machine_id": machine_id},
    )
    assert r.status_code == 201, r.text

    obj = await _notiz(test_settings, int(r.json()["id"]))
    assert obj.created_at.astimezone(dt.UTC) >= vorher - dt.timedelta(seconds=5)
    assert obj.created_at.astimezone(dt.UTC) <= dt.datetime.now(dt.UTC) + dt.timedelta(seconds=5)


async def test_naive_zeitangabe_wird_abgewiesen(auth_client: AsyncClient) -> None:
    """Eine Zeit ohne Zone wird nicht gedeutet, sondern zurückgewiesen.

    Die Anlage rechnet in Ortszeit mit Offset, und `shift` benennt eine
    Ortszeit-Schicht. Eine naive Frühschicht-Notiz als UTC gelesen liegt im
    Sommer zwei Stunden daneben — sie passt dann nicht mehr zu ihrem eigenen
    `shift`-Feld, und das fällt niemandem auf. Eine abgewiesene Eingabe ist
    besser als eine stillschweigend verschobene.
    """
    machine_id = await _maschine(auth_client)

    r = await auth_client.post(
        "/api/v1/worker_notes",
        json={
            "text": "Frühschicht, Achse läuft rau.",
            "machine_id": machine_id,
            "occurred_at": "2026-02-09T07:15:00",  # ohne Zone
        },
    )
    assert r.status_code == 422, r.text


async def test_die_spiegelung_traegt_dieselbe_zeit_wie_die_zeile(
    auth_client: AsyncClient, test_settings: Settings
) -> None:
    """Zwei Zeiten für denselben Vorgang wären schlimmer als eine falsche.

    `notiz_payload` liest `note.created_at`, und daraus wird im Archiv die
    Zeitangabe des Erinnerungs-Treffers. Würde der Zeitpunkt erst NACH dem flush
    gesetzt, trüge die Zeile die Schichtzeit und die Erinnerung den
    Ladezeitpunkt — derselbe Vorgang mit zwei Daten, die niemand mehr
    zusammenbringt. Genau diese Sorte Widerspruch stand am 27.08. schon einmal
    im Archiv (19 von 19 Erinnerungs-Treffer mit falschem Datum).
    """
    machine_id = await _maschine(auth_client)

    r = await auth_client.post(
        "/api/v1/worker_notes",
        json={
            "text": "Lagerschwingung an der Senkrechten, nimmt zu.",
            "machine_id": machine_id,
            "shift": "nacht",
            "occurred_at": SCHICHT.isoformat(),
        },
    )
    assert r.status_code == 201, r.text

    async with _lese_sitzung(test_settings) as session:
        ergebnis = await session.execute(
            select(SemanticEvent)
            .where(SemanticEvent.event_type == "worker_note")
            .order_by(SemanticEvent.id.desc())
        )
        spiegel = ergebnis.scalars().first()

    assert spiegel is not None, "keine Spiegelung angelegt"
    aus_nutzlast = dt.datetime.fromisoformat(str(spiegel.payload["created_at"]))
    assert aus_nutzlast.astimezone(dt.UTC) == SCHICHT.astimezone(dt.UTC), (
        "Die Erinnerung trägt eine andere Zeit als ihre Quellzeile"
    )
