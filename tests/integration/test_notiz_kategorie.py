# ============================================================
#  FOREMAN — tests/integration/test_notiz_kategorie.py
#  Zweck: Die Werker-Kategorie einer Schichtnotiz kommt an — in der Zeile UND
#         in der Spiegelung ans Gedächtnis.
#  ANLASS: `classification` war ein markierter Anschlusspunkt (§21.16): Das
#         Frontend erfasst die Kategorie mehrkanalig und sendet sie im POST mit,
#         die Datenbankspalte gibt es. Nur nahm `WorkerNoteCreate` das Feld nicht
#         an, und unbekannte Felder verfallen dort still (Pydantic-Vorgabe
#         `ignore`). Ergebnis: In der Halle wurde klassifiziert, gespeichert
#         wurde nichts — ohne Fehler, ohne Meldung, mit 201 als Antwort.
#         Die Kategorie ist die einzige Angabe der Notiz, die eine Verteilung
#         über die Zeit bildet; die Drift-Überwachung des Gedächtnisses setzt
#         darauf auf.
#  Architektur-Einordnung: Quality Gate §10.3, Schreibpfad §4, Spiegelung §12.4.
# ============================================================
from __future__ import annotations

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

# Die drei Kategorien der Halle, wortgleich zu `frontend/lib/capture/
# classification.ts`. Sie stehen hier als Literale und werden NICHT importiert:
# Der Test soll anschlagen, wenn eine Seite die Menge ändert, statt beide
# Seiten aus derselben Quelle grün zu halten.
HALLEN_KATEGORIEN = ("routine", "auffaellig", "kritisch")


@asynccontextmanager
async def _lese_sitzung(test_settings: Settings) -> AsyncIterator[AsyncSession]:
    """Eigene Lese-Sitzung — Begründung wie in `test_notiz_zeitpunkt.py`.

    Nicht `db_session`: Die hängt an `clean_db`, und zwei Fixturen, die beide den
    Bestand bestimmen wollen, nähmen einander den Testnutzer weg.
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
        json={"label": "Fügestation 3", "line_id": None, "machine_class": "servo_axis"},
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


async def test_die_kategorie_landet_in_der_zeile(
    auth_client: AsyncClient, test_settings: Settings
) -> None:
    """Der eigentliche Fall — und die Gegenprobe zum stillen Verfallen.

    Ein `201` allein belegt hier nichts: Genau das kam vorher auch zurück, ohne
    dass der Wert gespeichert wurde. Geprüft wird deshalb die ZEILE.
    """
    machine_id = await _maschine(auth_client)

    r = await auth_client.post(
        "/api/v1/worker_notes",
        json={
            "text": "Fügekraft schwankt, Werkzeug sieht angegriffen aus.",
            "machine_id": machine_id,
            "shift": "frueh",
            "classification": "kritisch",
        },
    )
    assert r.status_code == 201, r.text

    obj = await _notiz(test_settings, int(r.json()["id"]))
    assert obj.classification == "kritisch", (
        "Die Kategorie verfällt still — der Werker bekommt 201 und die Spalte bleibt leer."
    )


async def test_die_antwort_gibt_die_kategorie_zurueck(auth_client: AsyncClient) -> None:
    """Der Client muss die Wirkung seiner Eingabe SEHEN können.

    `WorkerNoteRead` führt das Feld; ein Tippfehler im gesendeten Feldnamen
    ergäbe sonst ein 201 mit leerer Kategorie, das wie ein Erfolg aussieht.
    Genau darauf weist der Router-Kopfkommentar hin — hier wird es eingefordert.
    """
    machine_id = await _maschine(auth_client)

    r = await auth_client.post(
        "/api/v1/worker_notes",
        json={
            "text": "Nichts Besonderes, läuft.",
            "machine_id": machine_id,
            "classification": "routine",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["classification"] == "routine"


@pytest.mark.parametrize("kategorie", HALLEN_KATEGORIEN)
async def test_jede_hallenkategorie_wird_angenommen(
    auth_client: AsyncClient, test_settings: Settings, kategorie: str
) -> None:
    """AUFBAU-KONTROLLE gegen die Menge, die das Frontend wirklich anbietet.

    Ein einzelner geprüfter Wert liesse offen, ob eine Längen- oder
    Wertgrenze einen der übrigen abschneidet. `auffaellig` ist der längste
    der drei — er ist der Grund, dass dieser Fall nicht nur Zierde ist.
    """
    machine_id = await _maschine(auth_client)

    r = await auth_client.post(
        "/api/v1/worker_notes",
        json={"text": "Schichtende.", "machine_id": machine_id, "classification": kategorie},
    )
    assert r.status_code == 201, r.text

    obj = await _notiz(test_settings, int(r.json()["id"]))
    assert obj.classification == kategorie


async def test_ohne_kategorie_bleibt_die_notiz_gueltig(
    auth_client: AsyncClient, test_settings: Settings
) -> None:
    """AUFBAU-KONTROLLE: Das Feld darf nicht zur Pflicht werden.

    Der Adapter-Weg kennt keine Kategorie, und aus der Halle kommt sie nur,
    wenn der Werker sie wählt. Ohne diesen Fall liesse sich später ein
    Pflichtfeld daraus machen, ohne dass es auffiele — und jede Notiz ohne
    Kategorie bekäme eine 422.
    """
    machine_id = await _maschine(auth_client)

    r = await auth_client.post(
        "/api/v1/worker_notes",
        json={"text": "Schicht ohne Auffälligkeiten.", "machine_id": machine_id},
    )
    assert r.status_code == 201, r.text

    obj = await _notiz(test_settings, int(r.json()["id"]))
    assert obj.classification is None


async def test_zu_langer_wert_wird_abgewiesen(auth_client: AsyncClient) -> None:
    """Die Längengrenze ist die Spaltenbreite — sie muss VOR der Datenbank greifen.

    Ohne die Grenze im Schema schlüge erst der Insert fehl, und zwar als 500
    statt als 422: eine Eingabefrage, die wie ein Serverfehler aussieht.
    """
    machine_id = await _maschine(auth_client)

    r = await auth_client.post(
        "/api/v1/worker_notes",
        json={"text": "Test.", "machine_id": machine_id, "classification": "x" * 33},
    )
    assert r.status_code == 422, r.text


async def test_die_spiegelung_traegt_die_kategorie_mit(
    auth_client: AsyncClient, test_settings: Settings
) -> None:
    """DER TRAGENDE FALL — die Kategorie muss beim Gedächtnis ANKOMMEN.

    Der gespiegelte SATZ nennt sie nicht (`_worker_note` in substrate/content.py
    baut ihn aus Bezug, Zeit und Text). Sie geht ausschliesslich über die
    Nutzlast mit. Stünde sie dort nicht, wäre alles oben grün, in der Zeile
    stünde der richtige Wert — und die Drift-Überwachung des Gedächtnisses hätte
    trotzdem nichts zu sehen.

    Absichtlich wird hier die gespiegelte Nutzlast geprüft, nicht `notiz_payload`
    selbst: Der Weg vom Router bis in die `semantic_events`-Zeile ist der, der
    brechen kann.
    """
    machine_id = await _maschine(auth_client)

    r = await auth_client.post(
        "/api/v1/worker_notes",
        json={
            "text": "Hydraulik zieht beim Anfahren Luft.",
            "machine_id": machine_id,
            "shift": "nacht",
            "classification": "auffaellig",
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
    assert spiegel.payload.get("classification") == "auffaellig", (
        "Die Kategorie fehlt in der Spiegel-Nutzlast — im Gedächtnis ist sie damit "
        "nicht auswertbar, obwohl die Zeile sie trägt."
    )
