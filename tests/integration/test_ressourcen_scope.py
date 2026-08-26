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
from fastapi import FastAPI
from httpx import AsyncClient

from foreman.api.deps import get_llm_gateway
from foreman.llm.errors import BackendUnavailable

pytestmark = pytest.mark.integration

AuthHeaders = Callable[[str, str], Awaitable[dict[str, str]]]


# --- Testdaten: zwei Maschinen, von denen dem Werker genau eine gehört ---


async def _maschinen_paar(raw_conn: asyncpg.Connection) -> tuple[int, int]:
    """Legt zwei Maschinen auf je eigener Linie an und liefert (eigene, fremde).

    Getrennte Linien, damit auch die Linien-Ebene prüfbar ist: Läge beides auf
    derselben Linie, sähe ein Werker über den abgeleiteten Linien-Ausschnitt die
    fremde Linie mit — und die Sperre wäre nicht mehr von einer Lücke zu
    unterscheiden.
    """
    eigene_linie, fremde_linie = await _linien_paar(raw_conn)
    eigene = await raw_conn.fetchval(
        "INSERT INTO machines (label, line_id) VALUES ('M-eigen', $1) RETURNING id", eigene_linie
    )
    fremde = await raw_conn.fetchval(
        "INSERT INTO machines (label, line_id) VALUES ('M-fremd', $1) RETURNING id", fremde_linie
    )
    return int(eigene), int(fremde)


async def _linien_paar(raw_conn: asyncpg.Connection) -> tuple[int, int]:
    """Legt zwei Linien an und liefert (eigene, fremde)."""
    eigene = await raw_conn.fetchval("INSERT INTO lines (label) VALUES ('L-eigen') RETURNING id")
    fremde = await raw_conn.fetchval("INSERT INTO lines (label) VALUES ('L-fremd') RETURNING id")
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


async def _alarm(raw_conn: asyncpg.Connection, machine_id: int) -> int:
    zeile = await raw_conn.fetchval(
        """
        INSERT INTO alarms (machine_id, severity, category, message)
        VALUES ($1, 'warning', 'process', 'Vibration erhöht') RETURNING id
        """,
        machine_id,
    )
    return int(zeile)


async def _komponente(raw_conn: asyncpg.Connection, machine_id: int) -> int:
    zeile = await raw_conn.fetchval(
        "INSERT INTO components (machine_id, label) VALUES ($1, 'Spindel') RETURNING id",
        machine_id,
    )
    return int(zeile)


async def _datenpunkt(raw_conn: asyncpg.Connection, machine_id: int) -> int:
    zeile = await raw_conn.fetchval(
        "INSERT INTO data_points (machine_id, name, kind) VALUES ($1, 'vib', 'analog') RETURNING id",
        machine_id,
    )
    return int(zeile)


# Alle Bestände, die an einer MASCHINE hängen — je mit Listen-Pfad und Erzeuger.
BESTAENDE = [
    pytest.param("/api/v1/worker_notes", _notiz, id="worker_notes"),
    pytest.param("/api/v1/maintenance_events", _wartung, id="maintenance_events"),
    pytest.param("/api/v1/reasoners/failure/predictions", _vorhersage, id="failure_predictions"),
    pytest.param("/api/v1/alarms", _alarm, id="alarms"),
    pytest.param("/api/v1/components", _komponente, id="components"),
    pytest.param("/api/v1/data_points", _datenpunkt, id="data_points"),
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


# Jeder Schreibpfad mit Maschinen-Kennung im Rumpf, mit Tabelle für die Gegenprobe.
SCHREIBPFADE = [
    pytest.param(
        "/api/v1/worker_notes",
        "worker_notes",
        {"text": "Eintrag"},
        id="worker_notes",
    ),
    pytest.param(
        "/api/v1/maintenance_events",
        "maintenance_events",
        {"type": "inspection"},
        id="maintenance_events",
    ),
    pytest.param(
        "/api/v1/alarms",
        "alarms",
        {"severity": "warning", "category": "process", "message": "Vibration"},
        id="alarms",
    ),
]
# NICHT hier: `components` und `data_points`. Sie gehören zur Anlagenstruktur und
# sind der Verwaltungsrolle vorbehalten (tests/integration/test_stammdaten_pflege.py).
# Für eine beschränkte Rolle käme dort ein 403 aus der ROLLENREGEL, nicht aus dem
# Ausschnitt — der Fall sähe bestanden aus und prüfte die falsche Sperre.
# Was hier steht, sind Bestände, die im Betrieb entstehen: Berichte, Nachweise, Alarme.


@pytest.mark.parametrize("pfad,tabelle,rumpf", SCHREIBPFADE)
async def test_anlegen_an_fremder_maschine_wird_abgelehnt(
    client: AsyncClient,
    raw_conn: asyncpg.Connection,
    auth_headers_for: AuthHeaders,
    pfad: str,
    tabelle: str,
    rumpf: dict[str, object],
) -> None:
    """Der Ausschnitt gilt auch beim Schreiben — sonst wäre er nur eine Leseregel.

    Geprüft wird nicht nur die Absage, sondern auch, dass NICHTS in der Tabelle
    landet: Eine 403-Antwort über einer erfolgten Zeile wäre die schlechteste
    aller Varianten.
    """
    eigene, fremde = await _maschinen_paar(raw_conn)
    headers = await _werker_mit(raw_conn, auth_headers_for, f"scope-w-{tabelle}@x.de", eigene)

    antwort = await client.post(pfad, json={**rumpf, "machine_id": fremde}, headers=headers)

    assert antwort.status_code == 403, antwort.text
    verblieben = await raw_conn.fetchval(
        f"SELECT count(*) FROM {tabelle} WHERE machine_id = $1",
        fremde,
    )
    assert verblieben == 0


@pytest.mark.parametrize("pfad,tabelle,rumpf", SCHREIBPFADE)
async def test_anlegen_an_eigener_maschine_gelingt(
    client: AsyncClient,
    raw_conn: asyncpg.Connection,
    auth_headers_for: AuthHeaders,
    pfad: str,
    tabelle: str,
    rumpf: dict[str, object],
) -> None:
    """Zwilling: derselbe Werker schreibt an seiner eigenen Maschine weiter."""
    eigene, _ = await _maschinen_paar(raw_conn)
    headers = await _werker_mit(raw_conn, auth_headers_for, f"scope-wok-{tabelle}@x.de", eigene)

    antwort = await client.post(pfad, json={**rumpf, "machine_id": eigene}, headers=headers)

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


# --- Die Anlagenstruktur selbst: Maschine und Linie ---


async def _linie_von(raw_conn: asyncpg.Connection, machine_id: int) -> int:
    """Die Linie, an der eine Maschine hängt."""
    line_id = await raw_conn.fetchval("SELECT line_id FROM machines WHERE id = $1", machine_id)
    assert line_id is not None, f"❌ Maschine {machine_id} hängt an keiner Linie."
    return int(line_id)


async def test_maschinenliste_zeigt_nur_die_eigenen(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    """Hier ist die Maschine nicht der Bezug, sondern die Ressource selbst."""
    eigene, fremde = await _maschinen_paar(raw_conn)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-mliste@x.de", eigene)

    antwort = await client.get("/api/v1/machines", headers=headers)

    assert antwort.status_code == 200, antwort.text
    kennungen = {eintrag["id"] for eintrag in antwort.json()}
    assert eigene in kennungen
    assert fremde not in kennungen


async def test_fremde_maschine_wird_abgewiesen(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    """403 statt 404: Die Maschinen-Kennung ist ein Stammdatum, keine geheime Zeile.

    Der Anfragende kennt sie aus seiner eigenen Liste; zu verschweigen gäbe es
    nichts, und die klare Absage ist die ehrlichere Antwort. Anders als beim
    Einzelabruf über eine Datensatz-Kennung, wo ein 403 die Existenz verriete.
    """
    eigene, fremde = await _maschinen_paar(raw_conn)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-mdet@x.de", eigene)

    antwort = await client.get(f"/api/v1/machines/{fremde}", headers=headers)

    assert antwort.status_code == 403, antwort.text


async def test_eigene_maschine_ist_abrufbar(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    """Zwilling zum Test darüber."""
    eigene, _ = await _maschinen_paar(raw_conn)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-mdet-ok@x.de", eigene)

    antwort = await client.get(f"/api/v1/machines/{eigene}", headers=headers)

    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["id"] == eigene


async def test_linienliste_folgt_den_eigenen_maschinen(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    """Der Linien-Ausschnitt eines Werkers ist aus seinen Maschinen abgeleitet.

    Er hat kein eigenes Zuweisungsfeld für Linien — er sieht genau die Linien, an
    denen seine Maschinen hängen. Das prüft dieser Test in beide Richtungen.
    """
    eigene_maschine, fremde_maschine = await _maschinen_paar(raw_conn)
    eigene_linie = await _linie_von(raw_conn, eigene_maschine)
    fremde_linie = await _linie_von(raw_conn, fremde_maschine)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-lliste@x.de", eigene_maschine)

    antwort = await client.get("/api/v1/lines", headers=headers)

    assert antwort.status_code == 200, antwort.text
    kennungen = {eintrag["id"] for eintrag in antwort.json()}
    assert eigene_linie in kennungen, "Die Linie der eigenen Maschine fehlt."
    assert fremde_linie not in kennungen, "Eine fremde Linie ist sichtbar."


async def test_fremde_linie_wird_abgewiesen(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    eigene_maschine, fremde_maschine = await _maschinen_paar(raw_conn)
    fremde_linie = await _linie_von(raw_conn, fremde_maschine)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-ldet@x.de", eigene_maschine)

    antwort = await client.get(f"/api/v1/lines/{fremde_linie}", headers=headers)

    assert antwort.status_code == 403, antwort.text


async def test_eigene_linie_ist_abrufbar(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    """Zwilling zum Test darüber."""
    eigene_maschine, _ = await _maschinen_paar(raw_conn)
    eigene_linie = await _linie_von(raw_conn, eigene_maschine)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-ldet-ok@x.de", eigene_maschine)

    antwort = await client.get(f"/api/v1/lines/{eigene_linie}", headers=headers)

    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["id"] == eigene_linie


# --- Produktionskontext: hängt an der Linie, nicht an einer Maschine ---


async def _produktionslauf(raw_conn: asyncpg.Connection, line_id: int) -> int:
    zeile = await raw_conn.fetchval(
        "INSERT INTO production_runs (line_id, product_code) VALUES ($1, 'P-1') RETURNING id",
        line_id,
    )
    return int(zeile)


async def test_produktionslaeufe_folgen_der_linie(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    eigene_maschine, fremde_maschine = await _maschinen_paar(raw_conn)
    eigener = await _produktionslauf(raw_conn, await _linie_von(raw_conn, eigene_maschine))
    fremder = await _produktionslauf(raw_conn, await _linie_von(raw_conn, fremde_maschine))
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-prod@x.de", eigene_maschine)

    antwort = await client.get("/api/v1/production_runs", headers=headers)

    assert antwort.status_code == 200, antwort.text
    kennungen = {eintrag["id"] for eintrag in antwort.json()}
    assert eigener in kennungen
    assert fremder not in kennungen


async def test_fremder_produktionslauf_ist_nicht_abrufbar(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    """404 wie bei jeder Datensatz-Kennung — kein Existenz-Orakel."""
    eigene_maschine, fremde_maschine = await _maschinen_paar(raw_conn)
    fremder = await _produktionslauf(raw_conn, await _linie_von(raw_conn, fremde_maschine))
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-proddet@x.de", eigene_maschine)

    antwort = await client.get(f"/api/v1/production_runs/{fremder}", headers=headers)

    assert antwort.status_code == 404, antwort.text


async def test_eigener_produktionslauf_ist_abrufbar(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    """Zwilling zum Test darüber."""
    eigene_maschine, _ = await _maschinen_paar(raw_conn)
    eigener = await _produktionslauf(raw_conn, await _linie_von(raw_conn, eigene_maschine))
    headers = await _werker_mit(
        raw_conn, auth_headers_for, "scope-proddet-ok@x.de", eigene_maschine
    )

    antwort = await client.get(f"/api/v1/production_runs/{eigener}", headers=headers)

    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["id"] == eigener


async def test_produktionslauf_an_fremder_linie_wird_abgelehnt(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    eigene_maschine, fremde_maschine = await _maschinen_paar(raw_conn)
    fremde_linie = await _linie_von(raw_conn, fremde_maschine)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-prodpost@x.de", eigene_maschine)

    antwort = await client.post(
        "/api/v1/production_runs",
        json={"line_id": fremde_linie, "product_code": "P-2"},
        headers=headers,
    )

    assert antwort.status_code == 403, antwort.text


async def test_produktionslauf_an_eigener_linie_gelingt(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    """Zwilling zum Test darüber."""
    eigene_maschine, _ = await _maschinen_paar(raw_conn)
    eigene_linie = await _linie_von(raw_conn, eigene_maschine)
    headers = await _werker_mit(
        raw_conn, auth_headers_for, "scope-prodpost-ok@x.de", eigene_maschine
    )

    antwort = await client.post(
        "/api/v1/production_runs",
        json={"line_id": eigene_linie, "product_code": "P-2"},
        headers=headers,
    )

    assert antwort.status_code == 201, antwort.text


# --- Reasoner-Bestände: erzeugte Warnungen und Erklärungen ---


async def _drift_warnung(raw_conn: asyncpg.Connection, machine_id: int) -> int:
    """Eine Warnung mit dem Kennzeichen des Abweichungs-Reasoners."""
    zeile = await raw_conn.fetchval(
        """
        INSERT INTO alarms (machine_id, severity, category, code, message)
        VALUES ($1, 'warning', 'process', 'DRIFT', 'Abweichung erkannt') RETURNING id
        """,
        machine_id,
    )
    return int(zeile)


async def _erklaerung(raw_conn: asyncpg.Connection, machine_id: int) -> int:
    """Eine Ereignisketten-Erklärung samt Anker-Warnung."""
    anker = await _alarm(raw_conn, machine_id)
    zeile = await raw_conn.fetchval(
        """
        INSERT INTO reasoner_explanations (
            anchor_alarm_id, machine_id, reasoner, narrative,
            referenced_source_ids, flagged_unsupported, is_hypothesis, confidence
        ) VALUES ($1, $2, 'event_chain', 'Kette', '[]', '[]', false, 'low')
        RETURNING id
        """,
        anker,
        machine_id,
    )
    return int(zeile)


@pytest.mark.parametrize(
    "pfad,erzeuger",
    [
        pytest.param("/api/v1/reasoners/drift/alarms", _drift_warnung, id="drift_alarms"),
        pytest.param("/api/v1/reasoners/event_chain/explanations", _erklaerung, id="event_chain"),
    ],
)
async def test_reasoner_liste_zeigt_nur_die_eigenen_maschinen(
    client: AsyncClient,
    raw_conn: asyncpg.Connection,
    auth_headers_for: AuthHeaders,
    pfad: str,
    erzeuger: Callable[[asyncpg.Connection, int], Awaitable[int]],
) -> None:
    """Was ein Reasoner erzeugt, folgt der Sichtbarkeit der Maschine, über die er es sagt."""
    eigene, fremde = await _maschinen_paar(raw_conn)
    eigener = await erzeuger(raw_conn, eigene)
    fremder = await erzeuger(raw_conn, fremde)
    headers = await _werker_mit(raw_conn, auth_headers_for, f"scope-r-{pfad[-6:]}@x.de", eigene)

    antwort = await client.get(pfad, headers=headers)

    assert antwort.status_code == 200, antwort.text
    kennungen = {eintrag["id"] for eintrag in antwort.json()}
    assert eigener in kennungen, "Der eigene Datensatz fehlt — die Sperre greift zu weit."
    assert fremder not in kennungen


@pytest.mark.parametrize(
    "pfad,erzeuger",
    [
        pytest.param("/api/v1/reasoners/drift/alarms", _drift_warnung, id="drift_alarms"),
        pytest.param("/api/v1/reasoners/event_chain/explanations", _erklaerung, id="event_chain"),
    ],
)
async def test_reasoner_liste_fremder_maschine_wird_abgewiesen(
    client: AsyncClient,
    raw_conn: asyncpg.Connection,
    auth_headers_for: AuthHeaders,
    pfad: str,
    erzeuger: Callable[[asyncpg.Connection, int], Awaitable[int]],
) -> None:
    eigene, fremde = await _maschinen_paar(raw_conn)
    await erzeuger(raw_conn, fremde)
    headers = await _werker_mit(raw_conn, auth_headers_for, f"scope-rf-{pfad[-6:]}@x.de", eigene)

    antwort = await client.get(pfad, params={"machine_id": fremde}, headers=headers)

    assert antwort.status_code == 403, antwort.text


async def test_fremde_erklaerung_ist_nicht_abrufbar(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    eigene, fremde = await _maschinen_paar(raw_conn)
    fremde_erklaerung = await _erklaerung(raw_conn, fremde)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-erk@x.de", eigene)

    antwort = await client.get(
        f"/api/v1/reasoners/event_chain/explanations/{fremde_erklaerung}", headers=headers
    )

    assert antwort.status_code == 404, antwort.text


async def test_eigene_erklaerung_ist_abrufbar(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    """Zwilling zum Test darüber."""
    eigene, _ = await _maschinen_paar(raw_conn)
    eigene_erklaerung = await _erklaerung(raw_conn, eigene)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-erk-ok@x.de", eigene)

    antwort = await client.get(
        f"/api/v1/reasoners/event_chain/explanations/{eigene_erklaerung}", headers=headers
    )

    assert antwort.status_code == 200, antwort.text
    assert antwort.json()["id"] == eigene_erklaerung


async def test_schwestern_einer_fremden_erklaerung_bleiben_verborgen(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    """Die Schwester-Referenzen erben den Ausschnitt ihrer Erklärung.

    Sie tragen keine eigene Maschinen-Kennung — ohne die geerbte Prüfung wären sie
    der Nebeneingang zu genau der Erklärung, die die Route darüber sperrt.
    """
    eigene, fremde = await _maschinen_paar(raw_conn)
    fremde_erklaerung = await _erklaerung(raw_conn, fremde)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-schwester@x.de", eigene)

    antwort = await client.get(
        f"/api/v1/reasoners/event_chain/explanations/{fremde_erklaerung}/siblings",
        headers=headers,
    )

    assert antwort.status_code == 404, antwort.text


async def test_schwestern_der_eigenen_erklaerung_sind_abrufbar(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    """Zwilling: derselbe Weg auf die eigene Maschine antwortet mit der Liste.

    Sie ist leer, weil dieser Aufbau keine Schwestern einfriert — geprüft wird der
    Weg dorthin, nicht der Inhalt. Ohne diesen Zwilling bliebe der Test darüber
    auch dann grün, wenn die Route grundsätzlich nie antwortete.
    """
    eigene, _ = await _maschinen_paar(raw_conn)
    eigene_erklaerung = await _erklaerung(raw_conn, eigene)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-schwester-ok@x.de", eigene)

    antwort = await client.get(
        f"/api/v1/reasoners/event_chain/explanations/{eigene_erklaerung}/siblings",
        headers=headers,
    )

    assert antwort.status_code == 200, antwort.text
    assert antwort.json() == []


# --- Aufnahme von Messwerten: der Ausschnitt gilt vor dem Schreiben ---


async def test_messwerte_fuer_fremde_maschine_werden_nicht_aufgenommen(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    """Ein Batch erreicht die Maschinen über seine Datenpunkte — auch das ist Zugriff."""
    eigene, fremde = await _maschinen_paar(raw_conn)
    fremder_punkt = await _datenpunkt(raw_conn, fremde)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-mess@x.de", eigene)

    antwort = await client.post(
        "/api/v1/readings",
        json={
            "readings": [
                {"time": "2026-08-26T10:00:00Z", "data_point_id": fremder_punkt, "value": 1.5}
            ]
        },
        headers=headers,
    )

    assert antwort.status_code == 403, antwort.text
    assert (
        await raw_conn.fetchval(
            "SELECT count(*) FROM readings WHERE data_point_id = $1", fremder_punkt
        )
        == 0
    )


async def test_messwerte_fuer_eigene_maschine_werden_aufgenommen(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    """Zwilling zum Test darüber."""
    eigene, _ = await _maschinen_paar(raw_conn)
    eigener_punkt = await _datenpunkt(raw_conn, eigene)
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-mess-ok@x.de", eigene)

    antwort = await client.post(
        "/api/v1/readings",
        json={
            "readings": [
                {"time": "2026-08-26T10:00:00Z", "data_point_id": eigener_punkt, "value": 1.5}
            ]
        },
        headers=headers,
    )

    assert antwort.status_code == 201, antwort.text
    assert antwort.json()["written"] == 1


# --- Die Suche findet nur im eigenen Ausschnitt ---

SUCHPFADE = [
    pytest.param("/api/v1/worker_notes/search", id="notiz_suche"),
    pytest.param("/api/v1/archive/search", id="archiv_suche"),
]


@pytest.mark.parametrize("pfad", SUCHPFADE)
async def test_suche_findet_nur_die_eigenen_maschinen(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders, pfad: str
) -> None:
    """Der Ausschnitt gilt auch für die Suche — sonst wäre sie der Weg daran vorbei.

    Beide Hälften zählen: Fände der Werker seine eigene Notiz nicht, griffe die
    Sperre zu weit, und der Test könnte das nicht von einer wirkenden Sperre
    unterscheiden.
    """
    eigene, fremde = await _maschinen_paar(raw_conn)
    eigene_notiz = await _notiz(raw_conn, eigene)
    fremde_notiz = await _notiz(raw_conn, fremde)
    headers = await _werker_mit(raw_conn, auth_headers_for, f"scope-s-{pfad[-6:]}@x.de", eigene)

    antwort = await client.get(pfad, params={"q": "Lager"}, headers=headers)

    assert antwort.status_code == 200, antwort.text
    kennungen = {eintrag["id"] for eintrag in antwort.json()}
    assert eigene_notiz in kennungen, "Die eigene Notiz fehlt — die Sperre greift zu weit."
    assert fremde_notiz not in kennungen, "Eine Notiz einer fremden Maschine ist auffindbar."


@pytest.mark.parametrize("pfad", SUCHPFADE)
async def test_suche_auf_fremder_maschine_wird_abgewiesen(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders, pfad: str
) -> None:
    """Ausdrücklich nach einer fremden Maschine gesucht → 403, keine leere Liste.

    Eine leere Trefferliste wäre hier die schlechtere Antwort: Sie sähe aus wie
    „dazu gibt es nichts" und verschleierte, dass die Anfrage abgewiesen wurde.
    """
    eigene, fremde = await _maschinen_paar(raw_conn)
    await _notiz(raw_conn, fremde)
    headers = await _werker_mit(raw_conn, auth_headers_for, f"scope-sf-{pfad[-6:]}@x.de", eigene)

    antwort = await client.get(pfad, params={"q": "Lager", "machine_id": fremde}, headers=headers)

    assert antwort.status_code == 403, antwort.text


@pytest.mark.parametrize("pfad", SUCHPFADE)
async def test_suche_auf_eigener_maschine_antwortet(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders, pfad: str
) -> None:
    """Zwilling zum Test darüber."""
    eigene, _ = await _maschinen_paar(raw_conn)
    eigene_notiz = await _notiz(raw_conn, eigene)
    headers = await _werker_mit(raw_conn, auth_headers_for, f"scope-so-{pfad[-6:]}@x.de", eigene)

    antwort = await client.get(pfad, params={"q": "Lager", "machine_id": eigene}, headers=headers)

    assert antwort.status_code == 200, antwort.text
    assert eigene_notiz in {eintrag["id"] for eintrag in antwort.json()}


@pytest.mark.parametrize("pfad", SUCHPFADE)
async def test_suche_ohne_zuweisung_findet_nichts(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders, pfad: str
) -> None:
    """Ein leerer Ausschnitt ist „nichts erlaubt", nicht „kein Filter".

    Der gefährlichste Fehler an dieser Stelle wäre, eine leere Zuweisungsliste als
    „keine Einschränkung" zu lesen — dann sähe ausgerechnet die Rolle ohne jede
    Zuweisung die ganze Flotte. Der Test hält die Richtung fest.
    """
    _, fremde = await _maschinen_paar(raw_conn)
    await _notiz(raw_conn, fremde)
    headers = await auth_headers_for(f"scope-leer-{pfad[-6:]}@x.de", "worker")

    antwort = await client.get(pfad, params={"q": "Lager"}, headers=headers)

    assert antwort.status_code == 200, antwort.text
    assert antwort.json() == []


@pytest.mark.parametrize("pfad", SUCHPFADE)
async def test_manager_findet_die_ganze_flotte(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders, pfad: str
) -> None:
    """Gegenprobe: Ohne sie wären die Tests darüber auch dann grün, wenn die Suche
    grundsätzlich nichts mehr fände."""
    eine, andere = await _maschinen_paar(raw_conn)
    erste = await _notiz(raw_conn, eine)
    zweite = await _notiz(raw_conn, andere)
    headers = await auth_headers_for(f"scope-smgr-{pfad[-6:]}@x.de", "manager")

    antwort = await client.get(pfad, params={"q": "Lager"}, headers=headers)

    assert antwort.status_code == 200, antwort.text
    assert {erste, zweite} <= {eintrag["id"] for eintrag in antwort.json()}


async def test_archivsuche_findet_auch_wartung_nur_im_ausschnitt(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    """Die Archiv-Suche bedient mehrere Quellen — jede einzeln muss den Strich halten.

    Ohne diesen Test bliebe die Wartungs-Quelle offen, während die Notiz-Quelle
    gefiltert wird: Die Gesamtantwort sähe plausibel aus, und der Durchgriff läge
    in der Quelle, die niemand einzeln geprüft hat.
    """
    eigene, fremde = await _maschinen_paar(raw_conn)
    fremde_wartung = await raw_conn.fetchval(
        """
        INSERT INTO maintenance_events (machine_id, type, description)
        VALUES ($1, 'lubrication', 'Lager nachgefettet') RETURNING id
        """,
        fremde,
    )
    eigene_wartung = await raw_conn.fetchval(
        """
        INSERT INTO maintenance_events (machine_id, type, description)
        VALUES ($1, 'lubrication', 'Lager nachgefettet') RETURNING id
        """,
        eigene,
    )
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-arch-wartung@x.de", eigene)

    antwort = await client.get(
        "/api/v1/archive/search", params={"q": "Lager", "sources": "maintenance"}, headers=headers
    )

    assert antwort.status_code == 200, antwort.text
    kennungen = {eintrag["id"] for eintrag in antwort.json()}
    assert int(eigene_wartung) in kennungen
    assert int(fremde_wartung) not in kennungen


async def test_archivsuche_findet_auch_alarme_nur_im_ausschnitt(
    client: AsyncClient, raw_conn: asyncpg.Connection, auth_headers_for: AuthHeaders
) -> None:
    """Dieselbe Prüfung für die Alarm-Quelle — jede Quelle einzeln belegt."""
    eigene, fremde = await _maschinen_paar(raw_conn)
    fremder_alarm = await raw_conn.fetchval(
        """
        INSERT INTO alarms (machine_id, severity, category, message)
        VALUES ($1, 'warning', 'process', 'Lager heiß gelaufen') RETURNING id
        """,
        fremde,
    )
    eigener_alarm = await raw_conn.fetchval(
        """
        INSERT INTO alarms (machine_id, severity, category, message)
        VALUES ($1, 'warning', 'process', 'Lager heiß gelaufen') RETURNING id
        """,
        eigene,
    )
    headers = await _werker_mit(raw_conn, auth_headers_for, "scope-arch-alarm@x.de", eigene)

    antwort = await client.get(
        "/api/v1/archive/search", params={"q": "Lager", "sources": "alarm"}, headers=headers
    )

    assert antwort.status_code == 200, antwort.text
    kennungen = {eintrag["id"] for eintrag in antwort.json()}
    assert int(eigener_alarm) in kennungen
    assert int(fremder_alarm) not in kennungen


# --- Reasoner-Auslöser: die Kennung kommt indirekt, der Ausschnitt gilt trotzdem ---
#
# Beide Auslöser bekommen keine Maschinen-Kennung, sondern eine Alarm-Kennung. Die
# Maschine ergibt sich erst aus dem geladenen Alarm — und genau deshalb ist die
# Prüfung hier leicht zu übersehen: Es sieht nicht nach einer Maschinen-Route aus.
# Sie sind je als Paar geprüft, wie alle Sperren in dieser Datei: fremd abgewiesen,
# eigen durchgelassen. Ohne den zweiten Teil bliebe der Sperr-Test auch dann grün,
# wenn der Alarm in der Testdatenbank gar nicht existierte.


async def _drift_alarm(raw_conn: asyncpg.Connection, machine_id: int) -> int:
    """Ein Alarm mit code=DRIFT — nur solche lassen sich quittieren."""
    zeile = await raw_conn.fetchval(
        """
        INSERT INTO alarms (machine_id, severity, category, code, message)
        VALUES ($1, 'warning', 'process', 'DRIFT', 'Kennwert driftet') RETURNING id
        """,
        machine_id,
    )
    return int(zeile)


async def test_kette_zu_fremdem_anker_wird_nicht_rekonstruiert(
    client: AsyncClient,
    raw_conn: asyncpg.Connection,
    auth_headers_for: AuthHeaders,
    grant_machine_scope,
) -> None:
    """Der Anker benennt einen Alarm, nicht die Maschine — der Ausschnitt gilt trotzdem.

    Die Rolle allein genügt nicht: `shift_lead` darf rekonstruieren, aber nur für
    Maschinen seiner Linien. Der Lauf trüge sonst Alarme, Werker-Notizen und
    Wartungsereignisse einer fremden Maschine zusammen und gäbe sie in der Antwort
    heraus.

    404 statt 403, wie beim Einzelabruf eines Alarms: Ein 403 würde bestätigen,
    dass der Alarm existiert.
    """
    eigene, fremde = await _maschinen_paar(raw_conn)
    headers = await auth_headers_for("scope-kette-fremd@x.de", "shift_lead")
    await grant_machine_scope("scope-kette-fremd@x.de", eigene)
    fremder_anker = await _alarm(raw_conn, fremde)

    antwort = await client.post(
        "/api/v1/reasoners/event_chain/reconstruct",
        json={"anchor_alarm_id": fremder_anker},
        headers=headers,
    )

    assert antwort.status_code == 404, antwort.text
    # Und nichts davon ist gespeichert worden: Ein abgewiesener Auslöser darf keine
    # Erklärung hinterlassen, auch keine leere.
    erklaerungen = await raw_conn.fetchval(
        "SELECT count(*) FROM reasoner_explanations WHERE machine_id = $1", fremde
    )
    assert erklaerungen == 0, "❌ Trotz Abweisung wurde eine Erklärung persistiert."


class _StummesGateway:
    """Gateway-Stub, der jeden Aufruf als bekannten Betriebsfehler beantwortet.

    Gebraucht für den Kontroll-Zwilling unten: Der prüft, ob der Ausschnitt
    DURCHLÄSST — nicht, ob der Reasoner etwas zustande bringt. Ohne Stub hinge das
    Ergebnis daran, ob gerade ein lokales Modell läuft, und im ungünstigen Fall
    ginge aus einem Pflichttest ein echter, kostenpflichtiger Aufruf hinaus.
    """

    async def complete(self, *_args: object, **_kwargs: object) -> object:
        raise BackendUnavailable("Stub für den Scope-Test", attempted=("stub",))


async def test_kette_zum_eigenen_anker_kommt_durch_den_ausschnitt(
    app: FastAPI,
    client: AsyncClient,
    raw_conn: asyncpg.Connection,
    auth_headers_for: AuthHeaders,
    grant_machine_scope: Callable[[str, int], Awaitable[None]],
) -> None:
    """Kontroll-Zwilling: derselbe Aufruf auf eigener Maschine wird NICHT abgewiesen.

    Geprüft wird ausschließlich, dass der Ausschnitt durchlässt. Die Antwort ist
    503, und ein 503 kann nur entstehen, wenn die Route bis zum Gateway gekommen
    ist — der Ausschnitt hat sie also passieren lassen. Das ist ein schärferer
    Beleg als „irgendetwas außer 404", weil es die Stelle benennt, bis zu der die
    Anfrage gekommen sein muss.

    Ohne diesen Zwilling bliebe der Test darüber auch dann grün, wenn jede
    Rekonstruktion an irgendetwas anderem scheiterte.
    """
    eigene, _ = await _maschinen_paar(raw_conn)
    headers = await auth_headers_for("scope-kette-eigen@x.de", "shift_lead")
    await grant_machine_scope("scope-kette-eigen@x.de", eigene)
    eigener_anker = await _alarm(raw_conn, eigene)

    app.dependency_overrides[get_llm_gateway] = lambda: _StummesGateway()
    try:
        antwort = await client.post(
            "/api/v1/reasoners/event_chain/reconstruct",
            json={"anchor_alarm_id": eigener_anker},
            headers=headers,
        )
    finally:
        # Der Override gehört diesem Test. Bliebe er stehen, liefe der nächste Test
        # gegen ein Gateway, das er nie bestellt hat.
        app.dependency_overrides.pop(get_llm_gateway, None)

    assert antwort.status_code == 503, (
        "❌ Erwartet war der Gateway-Fehler (503) — die Route muss also bis zum "
        f"Gateway gekommen sein. Bekommen: {antwort.status_code} {antwort.text[:200]}"
    )


async def test_fremde_drift_warnung_wird_nicht_quittiert(
    client: AsyncClient,
    raw_conn: asyncpg.Connection,
    auth_headers_for: AuthHeaders,
    grant_machine_scope,
) -> None:
    """Quittieren heißt „ein Mensch hat das behandelt" — das darf nur, wer sie sieht.

    Für Manager und Techniker fallen Rolle und Ausschnitt zusammen, für einen
    Schichtleiter nicht: Er sieht seine Linien. Ohne Ausschnitts-Prüfung könnte er
    die Meldung einer fremden Linie als erledigt markieren, und die Meldung wäre für
    die Zuständigen aus der Liste der offenen Punkte verschwunden.
    """
    eigene, fremde = await _maschinen_paar(raw_conn)
    headers = await auth_headers_for("scope-ack-fremd@x.de", "shift_lead")
    await grant_machine_scope("scope-ack-fremd@x.de", eigene)
    fremde_warnung = await _drift_alarm(raw_conn, fremde)

    antwort = await client.post(
        f"/api/v1/reasoners/drift/alarms/{fremde_warnung}/acknowledge", headers=headers
    )

    assert antwort.status_code == 404, antwort.text
    # Der eigentliche Schaden wäre die Schreibwirkung, nicht die Antwort: Die Warnung
    # muss unquittiert geblieben sein.
    quittiert_am = await raw_conn.fetchval(
        "SELECT acknowledged_at FROM alarms WHERE id = $1", fremde_warnung
    )
    assert quittiert_am is None, "❌ Trotz Abweisung wurde die fremde Warnung quittiert."


async def test_eigene_drift_warnung_laesst_sich_quittieren(
    client: AsyncClient,
    raw_conn: asyncpg.Connection,
    auth_headers_for: AuthHeaders,
    grant_machine_scope,
) -> None:
    """Kontroll-Zwilling: auf eigener Linie geht die Quittierung durch und wirkt.

    Ohne ihn bliebe der Test darüber auch dann grün, wenn Quittieren generell
    scheiterte — an der Rolle, am Alarmcode, an der Testdatenbank.
    """
    eigene, _ = await _maschinen_paar(raw_conn)
    headers = await auth_headers_for("scope-ack-eigen@x.de", "shift_lead")
    await grant_machine_scope("scope-ack-eigen@x.de", eigene)
    eigene_warnung = await _drift_alarm(raw_conn, eigene)

    antwort = await client.post(
        f"/api/v1/reasoners/drift/alarms/{eigene_warnung}/acknowledge", headers=headers
    )

    assert antwort.status_code == 200, antwort.text
    quittiert_am = await raw_conn.fetchval(
        "SELECT acknowledged_at FROM alarms WHERE id = $1", eigene_warnung
    )
    assert quittiert_am is not None, "❌ Die Quittierung kam durch, wirkte aber nicht."
