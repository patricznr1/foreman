# ============================================================
#  FOREMAN — tests/integration/test_dashboard_routes.py
#  Zweck: Die HTTP-Read-Routen des Dashboards (F5): /overview (Flotten-Lagebild,
#         manager/shift_lead) und /machines/{id}/trend (Sensortrend + Normalband).
#         Verifiziert die mit dem WS-Push geteilte Autorisierung — der PII-/Scope-
#         Strich hält auch auf HTTP (Worker → 403).
# ============================================================
from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

_PW = "supersecret1"


async def _auth(client: AsyncClient, email: str, role: str) -> dict[str, str]:
    await client.post("/auth/register", json={"email": email, "password": _PW, "role": role})
    response = await client.post("/auth/login", json={"email": email, "password": _PW})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def _seed_machine_with_data_point(
    client: AsyncClient, auth: dict[str, str]
) -> tuple[int, int]:
    line = (await client.post("/api/v1/lines", json={"label": "L"}, headers=auth)).json()
    machine = (
        await client.post(
            "/api/v1/machines", json={"label": "M", "line_id": line["id"]}, headers=auth
        )
    ).json()
    data_point = (
        await client.post(
            "/api/v1/data_points",
            json={"machine_id": machine["id"], "name": "vib", "kind": "analog"},
            headers=auth,
        )
    ).json()
    return int(machine["id"]), int(data_point["id"])


async def test_overview_returns_fleet_for_manager(client: AsyncClient) -> None:
    auth = await _auth(client, "ovw-mgr@x.de", "manager")
    machine_id, _ = await _seed_machine_with_data_point(client, auth)

    response = await client.get("/api/v1/overview", headers=auth)

    assert response.status_code == 200, response.text
    body = response.json()
    assert "by_status" in body and "open_alarm_total" in body
    assert any(machine["id"] == machine_id for machine in body["machines"])


async def test_overview_forbidden_for_worker(client: AsyncClient) -> None:
    auth = await _auth(client, "ovw-wrk@x.de", "worker")
    response = await client.get("/api/v1/overview", headers=auth)
    assert response.status_code == 403


async def test_overview_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/overview")
    assert response.status_code == 401


async def test_machine_trend_returns_metadata_for_manager(client: AsyncClient) -> None:
    auth = await _auth(client, "trd-mgr@x.de", "manager")
    machine_id, _ = await _seed_machine_with_data_point(client, auth)

    response = await client.get(
        f"/api/v1/machines/{machine_id}/trend?datapoint=vib&hours=48", headers=auth
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["data_point_name"] == "vib"
    assert isinstance(body["points"], list)
    assert body["profile_band"] is None


async def test_machine_trend_unknown_datapoint_404(client: AsyncClient) -> None:
    auth = await _auth(client, "trd-mgr2@x.de", "manager")
    machine_id, _ = await _seed_machine_with_data_point(client, auth)

    response = await client.get(f"/api/v1/machines/{machine_id}/trend?datapoint=nope", headers=auth)
    assert response.status_code == 404


async def test_machine_trend_forbidden_for_worker(client: AsyncClient) -> None:
    manager_auth = await _auth(client, "trd-mgr3@x.de", "manager")
    machine_id, _ = await _seed_machine_with_data_point(client, manager_auth)
    worker_auth = await _auth(client, "trd-wrk@x.de", "worker")

    response = await client.get(
        f"/api/v1/machines/{machine_id}/trend?datapoint=vib", headers=worker_auth
    )
    assert response.status_code == 403


# --------------------------------------------------------------------------- #
#  F4-Eigenprofil-Overlay: beide Transport-Einstiege (HTTP + WS) tragen das Band
# --------------------------------------------------------------------------- #
async def test_machine_trend_returns_profile_band_for_manager(
    client: AsyncClient, raw_conn: object
) -> None:
    # HTTP-Einstieg: liegt ein persistiertes Profil vor, trägt das Erstbild das Band.
    import json
    from datetime import UTC, datetime

    auth = await _auth(client, "trd-prof@x.de", "manager")
    machine_id, dp_id = await _seed_machine_with_data_point(client, auth)
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    await raw_conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO drift_profiles (data_point_id, machine_id, state_medians, noise_sigma, "
        "effect_size_k, window_samples, warmup_samples, total_samples, computed_at) "
        "VALUES ($1, $2, $3::jsonb, 1.0, 3.0, 1440, 100, 200, $4)",
        dp_id,
        machine_id,
        json.dumps({str(now.hour): {"median": 10.0, "sample_count": 50}}),
        now,
    )
    await raw_conn.execute(  # type: ignore[attr-defined]
        "INSERT INTO readings (data_point_id, time, value) VALUES ($1, $2, 10.5)", dp_id, now
    )

    response = await client.get(
        f"/api/v1/machines/{machine_id}/trend?datapoint=vib&hours=24", headers=auth
    )

    assert response.status_code == 200, response.text
    band = response.json()["profile_band"]
    assert band is not None
    assert band["effect_size_k"] == 3.0
    assert (band["points"][0]["lower"], band["points"][0]["mid"], band["points"][0]["upper"]) == (
        7.0,
        10.0,
        13.0,
    )


# --------------------------------------------------------------------------- #
#  Kanonische lebende Maschinenkarte: Detail-Erstbild, Grid, WS-Snapshot
# --------------------------------------------------------------------------- #
async def test_machine_card_returns_steifbrief_and_datapoints_for_manager(
    client: AsyncClient,
) -> None:
    auth = await _auth(client, "card-mgr@x.de", "manager")
    machine_id, _ = await _seed_machine_with_data_point(client, auth)

    response = await client.get(f"/api/v1/machines/{machine_id}/card", headers=auth)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == machine_id
    assert isinstance(body["components"], list)
    point = next(dp for dp in body["data_points"] if dp["name"] == "vib")
    # Ohne Readings: ehrlich unbekannt, kein erfundener Wert.
    assert point["last_value"] is None
    assert point["status"] == "unknown"
    assert "stream" in body


async def test_machine_card_forbidden_for_worker(client: AsyncClient) -> None:
    manager_auth = await _auth(client, "card-mgr2@x.de", "manager")
    machine_id, _ = await _seed_machine_with_data_point(client, manager_auth)
    worker_auth = await _auth(client, "card-wrk@x.de", "worker")

    response = await client.get(f"/api/v1/machines/{machine_id}/card", headers=worker_auth)
    assert response.status_code == 403


async def test_machine_card_unknown_machine_404(client: AsyncClient) -> None:
    auth = await _auth(client, "card-mgr3@x.de", "manager")
    response = await client.get("/api/v1/machines/999999/card", headers=auth)
    assert response.status_code == 404


async def test_machine_card_requires_auth(client: AsyncClient) -> None:
    response = await client.get("/api/v1/machines/1/card")
    assert response.status_code == 401


async def test_cards_returns_fleet_for_manager(client: AsyncClient) -> None:
    auth = await _auth(client, "cards-mgr@x.de", "manager")
    machine_id, _ = await _seed_machine_with_data_point(client, auth)

    response = await client.get("/api/v1/cards", headers=auth)

    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list)
    assert any(card["id"] == machine_id for card in body)


async def test_cards_empty_scope_for_unassigned_worker(client: AsyncClient) -> None:
    manager_auth = await _auth(client, "cards-mgr2@x.de", "manager")
    await _seed_machine_with_data_point(client, manager_auth)
    worker_auth = await _auth(client, "cards-wrk@x.de", "worker")

    response = await client.get("/api/v1/cards", headers=worker_auth)

    assert response.status_code == 200, response.text
    # Werker ohne zugewiesene Maschinen sieht ehrlich nichts (kein fremdes Lagebild).
    assert response.json() == []


async def test_ws_machine_snapshot_carries_living_card(
    db_session: object, raw_conn: object
) -> None:
    # WS-Einstieg: der machine:{id}-Snapshot trägt jetzt die ganze lebende Karte
    # (Steckbrief + Datenpunkte mit Wert + Status), nicht nur den Status — dieselbe
    # Quelle wie das HTTP-Erstbild.
    from datetime import UTC, datetime

    from foreman.db.models import DataPoint, Machine, User
    from foreman.ingestion.service import copy_readings
    from foreman.realtime.topics import machine_topic
    from foreman.realtime.ws import _load_topic

    machine = Machine(label="PR-02", machine_class="servo_press")
    db_session.add(machine)  # type: ignore[attr-defined]
    await db_session.flush()  # type: ignore[attr-defined]
    data_point = DataPoint(machine_id=machine.id, name="press_force", kind="analog", unit="kN")
    db_session.add(data_point)  # type: ignore[attr-defined]
    await db_session.flush()  # type: ignore[attr-defined]
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    manager = User(email="ws-card@x.de", password_hash="x", role="manager")
    db_session.add(manager)  # type: ignore[attr-defined]
    await copy_readings(db_session, [(now, data_point.id, 212.0, None)])  # type: ignore[arg-type]
    await db_session.commit()  # type: ignore[attr-defined]

    payload = await _load_topic(db_session, manager, machine_topic(machine.id))  # type: ignore[arg-type]

    assert payload is not None
    assert payload["label"] == "PR-02"
    assert payload["data_points"][0]["name"] == "press_force"
    assert payload["data_points"][0]["last_value"] == 212.0
    assert "stream" in payload


async def test_ws_trend_snapshot_carries_profile_band(db_session: object, raw_conn: object) -> None:
    # WS-Einstieg: der Snapshot beim Abo (echter Pfad _load_topic -> build_trend_by_id)
    # trägt dasselbe Band wie der HTTP-Einstieg — EINE Wahrheit für beide Transporte.
    from datetime import UTC, datetime

    from foreman.db.models import DataPoint, DriftProfile, Machine, User
    from foreman.ingestion.service import copy_readings
    from foreman.realtime.topics import trend_topic
    from foreman.realtime.ws import _load_topic

    machine = Machine(label="M")
    db_session.add(machine)  # type: ignore[attr-defined]
    await db_session.flush()  # type: ignore[attr-defined]
    data_point = DataPoint(machine_id=machine.id, name="vib", kind="analog")
    db_session.add(data_point)  # type: ignore[attr-defined]
    await db_session.flush()  # type: ignore[attr-defined]
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    db_session.add(  # type: ignore[attr-defined]
        DriftProfile(
            data_point_id=data_point.id,
            machine_id=machine.id,
            state_medians={str(now.hour): {"median": 10.0, "sample_count": 50}},
            noise_sigma=1.0,
            effect_size_k=3.0,
            window_samples=1440,
            warmup_samples=100,
            total_samples=200,
            computed_at=now,
        )
    )
    manager = User(email="ws-prof@x.de", password_hash="x", role="manager")
    db_session.add(manager)  # type: ignore[attr-defined]
    await copy_readings(db_session, [(now, data_point.id, 10.5, None)])  # type: ignore[arg-type]
    await db_session.commit()  # type: ignore[attr-defined]

    payload = await _load_topic(db_session, manager, trend_topic(data_point.id))  # type: ignore[arg-type]

    assert payload is not None
    band = payload["profile_band"]
    assert band is not None
    assert band["effect_size_k"] == 3.0
    assert band["points"][0]["mid"] == 10.0
