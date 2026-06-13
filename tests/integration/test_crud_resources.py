# ============================================================
#  FOREMAN — tests/integration/test_crud_resources.py
#  Zweck: CRUD aller acht Ressourcen (§4) + Datenschutz-Schreibpfad (§8):
#         HMAC-Tokenisierung der Personen-Felder + NER-Maskierung des Freitexts.
#  Pflicht-Test-Block: Happy-Path, 404, Auth-Fall, Validierung.
# ============================================================
from __future__ import annotations

from httpx import AsyncClient

from foreman.core.pseudonymize import Pseudonymizer

# Muss zu conftest (FOREMAN_PSEUDO_KEY_v1 = "11"*32) + test_settings (v1/default) passen.
_EXPECTED = Pseudonymizer(
    active_version="v1", keys={"v1": bytes.fromhex("11" * 32)}, tenant="default"
)


# --- kleine Helfer, um die Hierarchie aufzubauen ---
async def _create_line(c: AsyncClient) -> int:
    r = await c.post("/api/v1/lines", json={"label": "Linie 1", "location": "Halle A"})
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


async def _create_machine(c: AsyncClient, line_id: int | None = None) -> int:
    r = await c.post(
        "/api/v1/machines",
        json={"label": "Drehmaschine", "line_id": line_id, "machine_class": "lathe"},
    )
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


async def _create_component(c: AsyncClient, machine_id: int) -> int:
    r = await c.post(
        "/api/v1/components",
        json={"machine_id": machine_id, "label": "Spindel", "component_type": "spindle"},
    )
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


async def _create_data_point(c: AsyncClient, machine_id: int) -> int:
    r = await c.post(
        "/api/v1/data_points",
        json={
            "machine_id": machine_id,
            "name": "Spindeltemperatur",
            "kind": "analog",
            "measurement_type": "temperature",
            "unit": "°C",
            "source": "opcua",
        },
    )
    assert r.status_code == 201, r.text
    return int(r.json()["id"])


# --- lines ---
async def test_line_create_list_get(auth_client: AsyncClient) -> None:
    line_id = await _create_line(auth_client)
    listing = await auth_client.get("/api/v1/lines")
    assert listing.status_code == 200
    assert any(item["id"] == line_id for item in listing.json())
    single = await auth_client.get(f"/api/v1/lines/{line_id}")
    assert single.status_code == 200
    assert single.json()["label"] == "Linie 1"


async def test_line_get_missing_404(auth_client: AsyncClient) -> None:
    assert (await auth_client.get("/api/v1/lines/999999")).status_code == 404


async def test_line_validation_422(auth_client: AsyncClient) -> None:
    # label fehlt
    assert (await auth_client.post("/api/v1/lines", json={})).status_code == 422


async def test_crud_requires_auth(client: AsyncClient) -> None:
    assert (await client.post("/api/v1/lines", json={"label": "x"})).status_code == 401


# --- machines / components / data_points (Hierarchie) ---
async def test_machine_component_data_point_chain(auth_client: AsyncClient) -> None:
    line_id = await _create_line(auth_client)
    machine_id = await _create_machine(auth_client, line_id)
    component_id = await _create_component(auth_client, machine_id)
    dp_id = await _create_data_point(auth_client, machine_id)

    m = await auth_client.get(f"/api/v1/machines/{machine_id}")
    assert m.status_code == 200 and m.json()["line_id"] == line_id
    c = await auth_client.get(f"/api/v1/components/{component_id}")
    assert c.status_code == 200 and c.json()["machine_id"] == machine_id
    dp = await auth_client.get(f"/api/v1/data_points/{dp_id}")
    assert dp.status_code == 200 and dp.json()["kind"] == "analog"


async def test_data_point_invalid_kind_422(auth_client: AsyncClient) -> None:
    machine_id = await _create_machine(auth_client)
    r = await auth_client.post(
        "/api/v1/data_points",
        json={"machine_id": machine_id, "name": "x", "kind": "unsinn"},
    )
    assert r.status_code == 422


async def test_data_point_invalid_source_422(auth_client: AsyncClient) -> None:
    machine_id = await _create_machine(auth_client)
    r = await auth_client.post(
        "/api/v1/data_points",
        json={
            "machine_id": machine_id,
            "name": "x",
            "kind": "analog",
            "source": "telepathie",
        },
    )
    assert r.status_code == 422


# --- production_runs ---
async def test_production_run_crud(auth_client: AsyncClient) -> None:
    line_id = await _create_line(auth_client)
    r = await auth_client.post(
        "/api/v1/production_runs",
        json={"line_id": line_id, "product_code": "P-100", "order_id": "A42"},
    )
    assert r.status_code == 201
    run = r.json()
    assert run["product_code"] == "P-100"
    assert run["started_at"] is not None  # Server-Default greift
    got = await auth_client.get(f"/api/v1/production_runs/{run['id']}")
    assert got.status_code == 200


# --- maintenance_events: performed_by → HMAC-Token (§8) ---
async def test_maintenance_event_performed_by_is_tokenized(auth_client: AsyncClient) -> None:
    machine_id = await _create_machine(auth_client)
    r = await auth_client.post(
        "/api/v1/maintenance_events",
        json={"machine_id": machine_id, "type": "inspection", "performed_by": "123"},
    )
    assert r.status_code == 201
    performed_by = r.json()["performed_by"]
    assert performed_by != "123"
    assert performed_by.startswith("v1:")
    assert performed_by == _EXPECTED.tokenize_worker("123")


# --- alarms: acknowledged_by → HMAC-Token; Nothalt-Felder vorhanden (§8) ---
async def test_alarm_acknowledged_by_is_tokenized(auth_client: AsyncClient) -> None:
    machine_id = await _create_machine(auth_client)
    r = await auth_client.post(
        "/api/v1/alarms",
        json={
            "machine_id": machine_id,
            "severity": "emergency",
            "category": "safety",
            "acknowledged_by": "55",
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["acknowledged_by"] == _EXPECTED.tokenize_worker("55")
    assert body["acknowledged_by"] != "55"
    assert body["severity"] == "emergency" and body["category"] == "safety"


async def test_alarm_invalid_severity_422(auth_client: AsyncClient) -> None:
    machine_id = await _create_machine(auth_client)
    r = await auth_client.post(
        "/api/v1/alarms",
        json={"machine_id": machine_id, "severity": "schlimm", "category": "safety"},
    )
    assert r.status_code == 422


# --- worker_notes: author → Token UND text → NER-maskiert (§8) ---
async def test_worker_note_author_tokenized_and_text_redacted(
    auth_client: AsyncClient,
) -> None:
    machine_id = await _create_machine(auth_client)
    r = await auth_client.post(
        "/api/v1/worker_notes",
        json={
            "machine_id": machine_id,
            "shift": "frueh",
            "text": "Lager an Spindel 3 mit Schmidt getauscht",
            "author": "77",
        },
    )
    assert r.status_code == 201
    body = r.json()
    # Autor pseudonymisiert
    assert body["author"] == _EXPECTED.tokenize_worker("77")
    # Freitext NER-maskiert: „Schmidt" ist weg, Platzhalter da
    assert "Schmidt" not in body["text"]
    assert "[PERSON]" in body["text"]
    # Persistenz bestätigen: GET liest dieselbe maskierte Zeile aus der DB
    got = await auth_client.get(f"/api/v1/worker_notes/{body['id']}")
    assert "Schmidt" not in got.json()["text"]


async def test_worker_note_missing_text_422(auth_client: AsyncClient) -> None:
    r = await auth_client.post("/api/v1/worker_notes", json={"shift": "spaet"})
    assert r.status_code == 422


# --- 404 + Filter-Zweige aller übrigen Ressourcen ---
async def test_missing_resources_return_404(auth_client: AsyncClient) -> None:
    for resource in (
        "machines",
        "components",
        "data_points",
        "production_runs",
        "maintenance_events",
        "alarms",
        "worker_notes",
    ):
        r = await auth_client.get(f"/api/v1/{resource}/999999")
        assert r.status_code == 404, resource


async def test_list_endpoints_with_filters(auth_client: AsyncClient) -> None:
    line_id = await _create_line(auth_client)
    machine_id = await _create_machine(auth_client, line_id)
    await _create_component(auth_client, machine_id)
    await _create_data_point(auth_client, machine_id)
    await auth_client.post(
        "/api/v1/maintenance_events",
        json={"machine_id": machine_id, "type": "inspection"},
    )
    await auth_client.post(
        "/api/v1/alarms",
        json={"machine_id": machine_id, "severity": "warning", "category": "process"},
    )
    await auth_client.post(
        "/api/v1/worker_notes", json={"machine_id": machine_id, "text": "alles ok"}
    )

    checks = (
        f"/api/v1/components?machine_id={machine_id}",
        f"/api/v1/data_points?machine_id={machine_id}",
        f"/api/v1/production_runs?line_id={line_id}",
        f"/api/v1/maintenance_events?machine_id={machine_id}",
        f"/api/v1/alarms?machine_id={machine_id}&category=process",
        f"/api/v1/worker_notes?machine_id={machine_id}",
    )
    for url in checks:
        response = await auth_client.get(url)
        assert response.status_code == 200, url
        assert isinstance(response.json(), list)
