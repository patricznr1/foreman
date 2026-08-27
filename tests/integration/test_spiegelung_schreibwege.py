# ============================================================
#  FOREMAN — tests/integration/test_spiegelung_schreibwege.py
#  Zweck: Die HTTP-Schreibwege für Wartung und Alarm spiegeln ins Gedächtnis —
#         wie der Notiz-Schreibweg und wie der Adapter-Weg (§12.4).
#  ANLASS (27.08.2026): Sie taten es nicht. Die Spiegelung kam am 24.08. mit der
#         Schichtnotiz; `maintenance_events.py` und `alarms.py` wurden nie
#         nachgezogen — `record_semantic_event` kam dort null-mal vor. Wirkung
#         an der laufenden Instanz: Alles, was ein Mensch von Hand einträgt,
#         blieb für die vierte Archiv-Quelle unsichtbar. Gespiegelt war nur, was
#         der Adapter geschrieben hatte.
#  Architektur-Einordnung: Quality Gate §10.3, Dual-Write-Vertrag §12.4.
# ============================================================
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from foreman.config import Settings
from foreman.db.models import MaintenanceEvent, SemanticEvent

pytestmark = pytest.mark.integration


async def _maschine(c: AsyncClient) -> int:
    r = await c.post(
        "/api/v1/machines",
        json={"label": "Servo-Achse 9", "line_id": None, "machine_class": "servo_axis"},
    )
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


@asynccontextmanager
async def _lese_sitzung(settings: Settings) -> AsyncIterator[AsyncSession]:
    """Eigene Lese-Sitzung gegen dieselbe Datenbank.

    BEWUSST NICHT die `db_session`-Fixture: Die haengt an `clean_db` und leert
    die Datenbank — damit waere der Testnutzer fort, den `auth_client` vorher
    angelegt hat, und jede Anfrage liefe in ein 401. Zwei Fixtures, die beide
    den Bestand bestimmen wollen, vertragen sich nicht.
    """
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with maker() as session:
            yield session
    finally:
        await engine.dispose()


async def _spiegel(settings: Settings, event_type: str) -> list[SemanticEvent]:
    async with _lese_sitzung(settings) as session:
        ergebnis = await session.execute(
            select(SemanticEvent)
            .where(SemanticEvent.event_type == event_type)
            .order_by(SemanticEvent.id)
        )
        return list(ergebnis.scalars().all())


async def _quellzeilen(settings: Settings) -> list[MaintenanceEvent]:
    async with _lese_sitzung(settings) as session:
        ergebnis = await session.execute(select(MaintenanceEvent))
        return list(ergebnis.scalars().all())


# ──────────────────────────────────────────────────────────────────────
#  Die Sache: was von Hand eingetragen wird, kommt im Gedächtnis an
# ──────────────────────────────────────────────────────────────────────


async def test_wartung_ueber_http_wird_gespiegelt(
    auth_client: AsyncClient, test_settings: Settings
) -> None:
    """Ohne diese Spiegelung ist die vierte Archiv-Quelle blind für Handeingaben.

    Der Rückweg (`source_type`/`source_id`) wird mitgeprüft und nicht nur die
    Existenz der Zeile: Ohne ihn trägt der spätere Treffer `id=0`, ist keiner
    Quellzeile zuzuordnen, und weder die Doppelfund-Auflösung noch eine
    Gütemessung können mit ihm etwas anfangen (§15.10).
    """
    machine_id = await _maschine(auth_client)

    r = await auth_client.post(
        "/api/v1/maintenance_events",
        json={
            "machine_id": machine_id,
            "type": "lubrication",
            "description": "Nachschmierung Achslager, Intervall verkürzt.",
        },
    )
    assert r.status_code == 201, r.text
    wartungs_id = int(r.json()["id"])

    zeilen = await _spiegel(test_settings, "maintenance_performed")
    assert len(zeilen) == 1, "der HTTP-Schreibweg hat nicht gespiegelt"
    payload: dict[str, Any] = dict(zeilen[0].payload or {})
    assert zeilen[0].machine_id == machine_id
    assert payload["source_type"] == "maintenance"
    assert payload["source_id"] == wartungs_id
    assert payload["type"] == "lubrication"
    # Der Zeitpunkt des Vorgangs gehört hinein — ohne ihn ist eine Wiederholung
    # desselben Vorgangs an derselben Maschine nicht unterscheidbar.
    assert "performed_at" in payload


async def test_alarm_ueber_http_wird_gespiegelt(
    auth_client: AsyncClient, test_settings: Settings
) -> None:
    """Dieselbe Sache für den zweiten Schreibweg — und der Alarm braucht die Zeit.

    Ein Alarm desselben Typs an derselben Maschine ist ohne Auslösezeitpunkt vom
    vorherigen nicht unterscheidbar. Für „hatten wir das schon mal" ist die
    WIEDERHOLUNG aber die eigentliche Information (Befund 20.08.2026: beim
    Nachtrag fielen sechs Alarm-Paare über den Inhalts-Hash zusammen).
    """
    machine_id = await _maschine(auth_client)

    r = await auth_client.post(
        "/api/v1/alarms",
        json={
            "machine_id": machine_id,
            "code": "AXIS_VIB_WARN",
            "message": "Lagerschwingung über Warnschwelle.",
            "severity": "warning",
            "category": "hardware",
        },
    )
    assert r.status_code == 201, r.text
    alarm_id = int(r.json()["id"])

    zeilen = await _spiegel(test_settings, "alarm_raised")
    assert len(zeilen) == 1, "der HTTP-Schreibweg hat nicht gespiegelt"
    payload: dict[str, Any] = dict(zeilen[0].payload or {})
    assert payload["source_type"] == "alarm"
    assert payload["source_id"] == alarm_id
    assert payload["code"] == "AXIS_VIB_WARN"
    assert payload["raised_at"], "ohne Auslösezeitpunkt ist eine Wiederholung nicht erkennbar"


# ──────────────────────────────────────────────────────────────────────
#  Datenschutz: der Spiegel darf nicht die schwächere Grenze sein
# ──────────────────────────────────────────────────────────────────────


async def test_der_gespiegelte_freitext_ist_maskiert(
    auth_client: AsyncClient, test_settings: Settings
) -> None:
    """Was das System verlässt, wird behandelt wie der Notiz-Freitext (§15.9).

    `maintenance_events.description` läuft im Schreibpfad NICHT durch die
    Maskierung — ein gemeldeter und weiterhin offener Befund. Solange das Feld
    nur in der eigenen Datenbank lag, war das eine Inkonsistenz. Ab dem Moment,
    wo es gespiegelt wird, verlässt es das System.
    """
    machine_id = await _maschine(auth_client)

    r = await auth_client.post(
        "/api/v1/maintenance_events",
        json={
            "machine_id": machine_id,
            "type": "inspection",
            "description": "Rücksprache mit Schmidt: Lager bleibt drin.",
        },
    )
    assert r.status_code == 201, r.text

    payload = dict((await _spiegel(test_settings, "maintenance_performed"))[0].payload or {})
    assert "Schmidt" not in str(payload["description"])
    assert "[PERSON]" in str(payload["description"])


async def test_die_quellzeile_bleibt_unmaskiert(
    auth_client: AsyncClient, test_settings: Settings
) -> None:
    """AUFBAU-KONTROLLE: Die Maskierung greift NUR auf dem Spiegelweg.

    Ohne diesen Fall liesse sich die Maskierung unbemerkt in den Schreibpfad
    ziehen. Das wäre ein Eingriff in den Bestand und in den Rückweg zur Quelle,
    den dieser Weg nicht braucht — und der offene Befund §15.9 wäre still
    „erledigt", ohne dass ihn jemand entschieden hätte.
    """
    machine_id = await _maschine(auth_client)
    await auth_client.post(
        "/api/v1/maintenance_events",
        json={
            "machine_id": machine_id,
            "type": "inspection",
            "description": "Rücksprache mit Schmidt: Lager bleibt drin.",
        },
    )

    quellzeilen = await _quellzeilen(test_settings)
    assert len(quellzeilen) == 1
    assert "Schmidt" in str(quellzeilen[0].description), (
        "die Quellzeile wurde mitmaskiert — §15.9 wäre damit still entschieden"
    )


# ──────────────────────────────────────────────────────────────────────
#  Der Fehlerzweig: eine gestörte Gegenstelle darf den Eintrag nicht kosten
# ──────────────────────────────────────────────────────────────────────


class _KaputtesSubstrat:
    """Gegenstelle, die bei jedem Versuch wirft."""

    async def remember(self, content: str, metadata: dict[str, Any] | None = None) -> dict:
        raise RuntimeError("❌ Gegenstelle nicht erreichbar (Test)")


async def test_gestoerte_gegenstelle_kostet_den_wartungseintrag_nicht(
    app: Any, auth_client: AsyncClient, test_settings: Settings
) -> None:
    """Der Kernpfad der Halle hängt nicht am Gedächtnis (§9-Fallback).

    Ein Schichtleiter, der eine Wartung einträgt, darf keinen Fehler sehen, weil
    ein nachgelagerter Dienst klemmt. Die Zeile entsteht, die Spiegelzeile
    entsteht, nur die Referenz bleibt leer — und der nächste Backfill holt sie.
    """
    from foreman.api.deps import get_substrate_client

    app.dependency_overrides[get_substrate_client] = lambda: _KaputtesSubstrat()
    try:
        machine_id = await _maschine(auth_client)
        r = await auth_client.post(
            "/api/v1/maintenance_events",
            json={"machine_id": machine_id, "type": "lubrication", "description": "Ein Grund."},
        )
    finally:
        app.dependency_overrides.pop(get_substrate_client, None)

    assert r.status_code == 201, "die gestörte Gegenstelle hat den Eintrag gekostet"
    zeilen = await _spiegel(test_settings, "maintenance_performed")
    assert len(zeilen) == 1, "ohne Spiegelzeile findet auch der Backfill sie nie"
    assert zeilen[0].substrate_ref is None
