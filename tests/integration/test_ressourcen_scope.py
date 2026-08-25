# ============================================================
#  FOREMAN — tests/integration/test_ressourcen_scope.py
#  Zweck: Der Maschinen-Scope hält an der HTTP-Route, nicht erst im Frontend
#         (§20.4, Rollenmatrix 3.1). Geprüft wird die zweite Frage, die die
#         Auth-Middleware nie stellt: nicht „wer bist du", sondern „darfst du
#         GENAU DIESE Ressource sehen".
#  Architektur-Einordnung: Quality Gate §10.3 (Integration, braucht DB).
#  Aufbau (B2-Zwilling): Jede Sperre wird als PAAR geprüft — fremde Ressource
#         abgewiesen UND eigene Ressource durchgelassen. Ohne den zweiten Teil
#         bliebe der Sperr-Test auch dann grün, wenn die Testdatenbank die
#         fremde Maschine gar nicht kennt; er bewiese dann nichts.
# ============================================================
from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import asyncpg
import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

AuthHeaders = Callable[[str, str], Awaitable[dict[str, str]]]


# --- Testdaten: zwei Maschinen, von denen dem Werker genau eine gehört ---


async def _maschinen_paar(raw_conn: asyncpg.Connection) -> tuple[int, int]:
    """Legt zwei Maschinen an und liefert (eigene, fremde)."""
    eigene = await raw_conn.fetchval("INSERT INTO machines (label) VALUES ('M-eigen') RETURNING id")
    fremde = await raw_conn.fetchval("INSERT INTO machines (label) VALUES ('M-fremd') RETURNING id")
    return int(eigene), int(fremde)


async def _werker_mit(
    raw_conn: asyncpg.Connection,
    auth_headers_for: AuthHeaders,
    email: str,
    machine_id: int,
) -> dict[str, str]:
    """Werker, dem genau `machine_id` zugewiesen ist (Matrix 3.1: worker → Maschinen)."""
    headers = await auth_headers_for(email, "worker")
    await raw_conn.execute(
        "UPDATE users SET assigned_machine_ids = $1 WHERE email = $2", [machine_id], email
    )
    return headers


async def _notiz(raw_conn: asyncpg.Connection, machine_id: int) -> int:
    zeile = await raw_conn.fetchval(
        "INSERT INTO worker_notes (machine_id, text) VALUES ($1, 'Lager läuft warm') RETURNING id",
        machine_id,
    )
    return int(zeile)


async def _wartung(raw_conn: asyncpg.Connection, machine_id: int) -> int:
    zeile = await raw_conn.fetchval(
        "INSERT INTO maintenance_events (machine_id, type) VALUES ($1, 'lubrication') RETURNING id",
        machine_id,
    )
    return int(zeile)


async def _vorhersage(raw_conn: asyncpg.Connection, machine_id: int) -> int:
    zeile = await raw_conn.fetchval(
        """
        INSERT INTO failure_predictions (
            machine_id, reference_time, horizon_h, probability, decision_threshold,
            decision, validation_status, data_regime, model_version, top_factors
        ) VALUES ($1, $2, 24, 0.4, 0.5, 'normal', 'simulation_only', 'simulation', 'test', '[]')
        RETURNING id
        """,
        machine_id,
        datetime.now(UTC),
    )
    return int(zeile)


# Die drei Bestände dieser Etappe, je mit Listen-Pfad und Datensatz-Erzeuger.
BESTAENDE = [
    pytest.param("/api/v1/worker_notes", _notiz, id="worker_notes"),
    pytest.param("/api/v1/maintenance_events", _wartung, id="maintenance_events"),
    pytest.param("/api/v1/reasoners/failure/predictions", _vorhersage, id="failure_predictions"),
]


# --- Listen: der Ausschnitt folgt der Zuweisung ---


@pytest.mark.parametrize("pfad,erzeuger", BESTAENDE)
async def test_liste_zeigt_nur_die_eigenen_maschinen(
    client: AsyncClient,
    raw_conn: asyncpg.Connection,
    auth_headers_for: AuthHeaders,
    pfad: str,
    erzeuger: Callable[[asyncpg.Connection, int], Awaitable[int]],
) -> None:
    """Ungefilterte Liste: eigener Datensatz ist dabei, fremder nicht.

    Beide Hälften zählen. Nur „fremder fehlt" wäre auch bei einer leeren Antwort
    erfüllt — dann prüfte der Test die Sperre gar nicht.
    """
    eigene, fremde = await _maschinen_paar(raw_conn)
    eigener_satz = await erzeuger(raw_conn, eigene)
    fremder_satz = await erzeuger(raw_conn, fremde)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-liste@x.de", eigene)

    antwort = await client.get(pfad, headers=headers)

    assert antwort.status_code == 200, antwort.text
    kennungen = {eintrag["id"] for eintrag in antwort.json()}
    assert eigener_satz in kennungen, "Der eigene Datensatz fehlt — die Sperre greift zu weit."
    assert fremder_satz not in kennungen, "Ein Datensatz einer fremden Maschine ist sichtbar."


@pytest.mark.parametrize("pfad,erzeuger", BESTAENDE)
async def test_liste_einer_fremden_maschine_wird_abgewiesen(
    client: AsyncClient,
    raw_conn: asyncpg.Connection,
    auth_headers_for: AuthHeaders,
    pfad: str,
    erzeuger: Callable[[asyncpg.Connection, int], Awaitable[int]],
) -> None:
    """Ausdrücklich nach einer fremden Maschine gefragt → 403."""
    eigene, fremde = await _maschinen_paar(raw_conn)
    await erzeuger(raw_conn, fremde)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-fremd@x.de", eigene)

    antwort = await client.get(pfad, params={"machine_id": fremde}, headers=headers)

    assert antwort.status_code == 403, antwort.text


@pytest.mark.parametrize("pfad,erzeuger", BESTAENDE)
async def test_liste_der_eigenen_maschine_antwortet(
    client: AsyncClient,
    raw_conn: asyncpg.Connection,
    auth_headers_for: AuthHeaders,
    pfad: str,
    erzeuger: Callable[[asyncpg.Connection, int], Awaitable[int]],
) -> None:
    """Zwilling zum Test darüber: dieselbe Rolle, eigene Maschine → 200 mit Inhalt."""
    eigene, _ = await _maschinen_paar(raw_conn)
    eigener_satz = await erzeuger(raw_conn, eigene)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-eigen@x.de", eigene)

    antwort = await client.get(pfad, params={"machine_id": eigene}, headers=headers)

    assert antwort.status_code == 200, antwort.text
    assert {eintrag["id"] for eintrag in antwort.json()} == {eigener_satz}


# --- Einzelabruf: eine fremde Ressource ist nicht vorhanden ---


@pytest.mark.parametrize("pfad,erzeuger", BESTAENDE)
async def test_fremder_datensatz_ist_nicht_abrufbar(
    client: AsyncClient,
    raw_conn: asyncpg.Connection,
    auth_headers_for: AuthHeaders,
    pfad: str,
    erzeuger: Callable[[asyncpg.Connection, int], Awaitable[int]],
) -> None:
    """404 statt 403 beim Einzelabruf über eine Datensatz-Kennung.

    Die Zugehörigkeit steht erst nach dem Laden fest; ein 403 würde die Existenz
    der Zeile bestätigen und die Kennungen durchprobierbar machen.
    """
    eigene, fremde = await _maschinen_paar(raw_conn)
    fremder_satz = await erzeuger(raw_conn, fremde)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-detail@x.de", eigene)

    antwort = await client.get(f"{pfad}/{fremder_satz}", headers=headers)

    assert antwort.status_code == 404, antwort.text


@pytest.mark.parametrize("pfad,erzeuger", BESTAENDE)
async def test_eigener_datensatz_ist_abrufbar(
    client: AsyncClient,
    raw_conn: asyncpg.Connection,
    auth_headers_for: AuthHeaders,
    pfad: str,
    erzeuger: Callable[[asyncpg.Connection, int], Awaitable[int]],
) -> None:
    """Zwilling: derselbe Weg auf die eigene Maschine liefert die Zeile."""
    eigene, _ = await _maschinen_paar(raw_conn)
    eigener_satz = await erzeuger(raw_conn, eigene)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-detail-ok@x.de", eigene)

    antwort = await client.get(f"{pfad}/{eigener_satz}", headers=headers)

    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["id"] == eigener_satz


# --- Schreibpfade: der Scope gilt auch beim Anlegen ---


async def test_notiz_fuer_fremde_maschine_wird_nicht_angelegt(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    """Ein Schichtbericht an einer fremden Maschine ist kein zulässiger Beitrag."""
    eigene, fremde = await _maschinen_paar(raw_conn)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-post@x.de", eigene)

    antwort = await client.post(
        "/api/v1/worker_notes",
        json={"machine_id": fremde, "text": "Fremdeintrag"},
        headers=headers,
    )

    assert antwort.status_code == 403, antwort.text
    assert (
        await raw_conn.fetchval("SELECT count(*) FROM worker_notes WHERE machine_id = $1", fremde)
        == 0
    )


async def test_notiz_fuer_eigene_maschine_wird_angelegt(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    """Zwilling: derselbe Werker schreibt an seiner eigenen Maschine weiter."""
    eigene, _ = await _maschinen_paar(raw_conn)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-post-ok@x.de", eigene)

    antwort = await client.post(
        "/api/v1/worker_notes",
        json={"machine_id": eigene, "text": "Eigener Eintrag"},
        headers=headers,
    )

    assert antwort.status_code == 201, antwort.text


async def test_wartung_fuer_fremde_maschine_wird_nicht_angelegt(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    eigene, fremde = await _maschinen_paar(raw_conn)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-wartung@x.de", eigene)

    antwort = await client.post(
        "/api/v1/maintenance_events",
        json={"machine_id": fremde, "type": "lubrication"},
        headers=headers,
    )

    assert antwort.status_code == 403, antwort.text
    assert (
        await raw_conn.fetchval(
            "SELECT count(*) FROM maintenance_events WHERE machine_id = $1", fremde
        )
        == 0
    )


async def test_wartung_fuer_eigene_maschine_wird_angelegt(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    """Zwilling zum Test darüber."""
    eigene, _ = await _maschinen_paar(raw_conn)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-wartung-ok@x.de", eigene)

    antwort = await client.post(
        "/api/v1/maintenance_events",
        json={"machine_id": eigene, "type": "lubrication"},
        headers=headers,
    )

    assert antwort.status_code == 201, antwort.text


async def test_vorhersage_fuer_fremde_maschine_wird_nicht_ausgeloest(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    """Der Auslöser trägt eine Maschinen-Kennung im Rumpf — auch sie folgt dem Scope.

    Die Rolle allein genügt hier nicht: `shift_lead` darf auslösen, aber nur auf
    den Maschinen seiner Linien. Ohne zugewiesene Linie ist jede Maschine fremd.
    """
    _, fremde = await _maschinen_paar(raw_conn)
    headers = await auth_headers_for("scope-trigger@x.de", "shift_lead")

    antwort = await client.post(
        "/api/v1/reasoners/failure/predict",
        json={"machine_id": fremde},
        headers=headers,
    )

    assert antwort.status_code == 403, antwort.text


# --- Gegenprobe: unbeschränkte Rollen bleiben unbeschränkt ---


@pytest.mark.parametrize("pfad,erzeuger", BESTAENDE)
async def test_manager_sieht_die_ganze_flotte(
    client: AsyncClient,
    raw_conn: asyncpg.Connection,
    auth_headers_for: AuthHeaders,
    pfad: str,
    erzeuger: Callable[[asyncpg.Connection, int], Awaitable[int]],
) -> None:
    """Belegt, dass die Sperre die Rollenmatrix trifft und nicht einfach alles zumauert.

    Ohne diese Gegenprobe wäre jeder Sperr-Test oben auch dann grün, wenn der
    Scope-Resolver pauschal einen leeren Ausschnitt lieferte.
    """
    eine, andere = await _maschinen_paar(raw_conn)
    erster = await erzeuger(raw_conn, eine)
    zweiter = await erzeuger(raw_conn, andere)
    headers = await auth_headers_for("scope-mgr@x.de", "manager")

    antwort = await client.get(pfad, headers=headers)

    assert antwort.status_code == 200, antwort.text
    kennungen = {eintrag["id"] for eintrag in antwort.json()}
    assert {erster, zweiter} <= kennungen


async def test_empfehlung_zu_fremder_vorhersage_ist_nicht_abrufbar(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    """Die Empfehlung erbt den Ausschnitt ihrer Vorhersage.

    Sie hängt an keiner eigenen Maschinen-Kennung — ohne die geerbte Prüfung wäre
    sie der offene Nebeneingang zu genau der Vorhersage, die die Route darüber sperrt.
    """
    eigene, fremde = await _maschinen_paar(raw_conn)
    fremde_vorhersage = await _vorhersage(raw_conn, fremde)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-empfehlung@x.de", eigene)

    antwort = await client.get(
        f"/api/v1/reasoners/failure/predictions/{fremde_vorhersage}/recommendation",
        headers=headers,
    )

    assert antwort.status_code == 404, antwort.text


async def test_empfehlung_zur_eigenen_vorhersage_meldet_nur_ihr_fehlen(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    """Zwilling: dieselbe Antwort für die eigene Maschine hat einen anderen Grund.

    Beide Wege enden mit 404 — deshalb prüft dieser Test die MELDUNG. Ohne ihn
    bliebe der Test darüber auch dann grün, wenn die Empfehlung generell nie
    gefunden würde und die Sperre gar nicht griffe.
    """
    eigene, _ = await _maschinen_paar(raw_conn)
    eigene_vorhersage = await _vorhersage(raw_conn, eigene)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-empfehlung-ok@x.de", eigene)

    antwort = await client.get(
        f"/api/v1/reasoners/failure/predictions/{eigene_vorhersage}/recommendation",
        headers=headers,
    )

    assert antwort.status_code == 404, antwort.text
    assert antwort.json()["detail"] == "Empfehlung nicht gefunden"
