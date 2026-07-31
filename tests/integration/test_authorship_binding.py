# ============================================================
#  FOREMAN — tests/integration/test_authorship_binding.py
#  Zweck: Die Autoren-/Nachweisbindung der Schreibpfade (§8/§19, OWASP A01):
#         `worker_notes.author` kommt IMMER aus dem Token, `maintenance_events.
#         performed_by` per Default ebenfalls — ein abweichender Wert ist ein
#         Nachtrag und nur den aufsichtsführenden Rollen erlaubt. Dazu die
#         Längengrenze des Notiz-Freitextes.
#  Architektur-Einordnung: Integrationstest gegen die echte Test-DB (§10.3).
#  Pflicht-Test-Block: Happy-Path, Auth-/Permission-Fall, Validierung, Edge,
#         Contract (model_validate gegen das Read-Schema).
# ============================================================
from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient

from foreman.core.pseudonymize import Pseudonymizer
from foreman.schemas.resources import (
    WORKER_NOTE_TEXT_MAX,
    MaintenanceEventRead,
    WorkerNoteRead,
)

pytestmark = pytest.mark.integration

AuthHeaders = Callable[[str, str], Awaitable[dict[str, str]]]


async def _own_id(client: AsyncClient, headers: dict[str, str]) -> int:
    return int((await client.get("/api/v1/me", headers=headers)).json()["id"])


# --------------------------------------------------------------------------- #
#  worker_notes — der Verfasser kommt aus dem Token
# --------------------------------------------------------------------------- #
async def test_note_without_token_401(client: AsyncClient) -> None:
    response = await client.post("/api/v1/worker_notes", json={"text": "Lager heiß"})
    assert response.status_code == 401


async def test_note_rejects_client_supplied_author(
    client: AsyncClient, auth_headers_for: AuthHeaders
) -> None:
    """Ein mitgeschicktes `author` wird abgelehnt statt still verworfen — sonst
    glaubte der Client, die Angabe hätte gewirkt."""
    headers = await auth_headers_for("bind-wrk1@foreman.de", "worker")

    response = await client.post(
        "/api/v1/worker_notes",
        json={"text": "Lager heiß", "author": "999"},
        headers=headers,
    )

    assert response.status_code == 422


async def test_note_still_accepts_the_documented_extra_field(
    client: AsyncClient, auth_headers_for: AuthHeaders
) -> None:
    """Gegenprobe zum Autor-Verbot: der übrige Vertrag bleibt unverändert.

    Das Frontend sendet `classification` als markierten Anschlusspunkt mit (§21.16);
    das Feld wird wie bisher nicht übernommen, darf den Insert aber nicht brechen.
    Deshalb ein gezieltes Verbot für `author` statt `extra="forbid"`."""
    headers = await auth_headers_for("bind-extra@foreman.de", "worker")

    response = await client.post(
        "/api/v1/worker_notes",
        json={"text": "Lager heiß", "classification": "auffaellig"},
        headers=headers,
    )

    assert response.status_code == 201, response.text


async def test_note_author_is_bound_to_token_identity(
    client: AsyncClient, auth_headers_for: AuthHeaders, pseudonymizer: Pseudonymizer
) -> None:
    """Kern-Assert: der gespeicherte Autor ist der Token-Nutzer — und ausdrücklich
    NICHT ein anderer Nutzer der Anlage."""
    author_headers = await auth_headers_for("bind-author@foreman.de", "worker")
    other_headers = await auth_headers_for("bind-other@foreman.de", "worker")
    author_id = await _own_id(client, author_headers)
    other_id = await _own_id(client, other_headers)

    response = await client.post(
        "/api/v1/worker_notes", json={"text": "Lager heiß"}, headers=author_headers
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["author"] == pseudonymizer.tokenize_worker(str(author_id))
    assert body["author"] != pseudonymizer.tokenize_worker(str(other_id))
    # Contract: die Antwort erfüllt das deklarierte Read-Schema.
    WorkerNoteRead.model_validate(body)


async def test_note_text_over_limit_422(client: AsyncClient, auth_headers_for: AuthHeaders) -> None:
    headers = await auth_headers_for("bind-long@foreman.de", "worker")

    response = await client.post(
        "/api/v1/worker_notes",
        json={"text": "x" * (WORKER_NOTE_TEXT_MAX + 1)},
        headers=headers,
    )

    assert response.status_code == 422
    assert "detail" in response.json()


async def test_note_text_at_limit_is_accepted(
    client: AsyncClient, auth_headers_for: AuthHeaders
) -> None:
    """Edge: die Grenze ist inklusiv — exakt WORKER_NOTE_TEXT_MAX geht durch."""
    headers = await auth_headers_for("bind-edge@foreman.de", "worker")

    response = await client.post(
        "/api/v1/worker_notes",
        json={"text": "x" * WORKER_NOTE_TEXT_MAX},
        headers=headers,
    )

    assert response.status_code == 201, response.text


# --------------------------------------------------------------------------- #
#  maintenance_events — Nachweisfeld mit Rollen-Regel
# --------------------------------------------------------------------------- #
async def _machine_id(client: AsyncClient, headers: dict[str, str]) -> int:
    line = (await client.post("/api/v1/lines", json={"label": "L"}, headers=headers)).json()
    machine = (
        await client.post(
            "/api/v1/machines", json={"label": "M", "line_id": line["id"]}, headers=headers
        )
    ).json()
    return int(machine["id"])


async def test_maintenance_defaults_to_token_identity(
    client: AsyncClient, auth_headers_for: AuthHeaders, pseudonymizer: Pseudonymizer
) -> None:
    """Ohne `performed_by` wird der eingeloggte Nutzer eingetragen (nicht NULL)."""
    headers = await auth_headers_for("bind-mt-wrk@foreman.de", "worker")
    machine_id = await _machine_id(client, headers)
    own = await _own_id(client, headers)

    response = await client.post(
        "/api/v1/maintenance_events",
        json={"machine_id": machine_id, "type": "inspection"},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["performed_by"] == pseudonymizer.tokenize_worker(str(own))
    MaintenanceEventRead.model_validate(body)


async def test_maintenance_worker_cannot_write_for_others(
    client: AsyncClient, auth_headers_for: AuthHeaders
) -> None:
    """Ein Werker trägt nur für sich selbst ein — fremdes `performed_by` → 403."""
    headers = await auth_headers_for("bind-mt-wrk2@foreman.de", "worker")
    machine_id = await _machine_id(client, headers)

    response = await client.post(
        "/api/v1/maintenance_events",
        json={"machine_id": machine_id, "type": "inspection", "performed_by": "4711"},
        headers=headers,
    )

    assert response.status_code == 403


@pytest.mark.parametrize("role", ["shift_lead", "technician", "manager"])
async def test_supervising_roles_may_record_for_others(
    client: AsyncClient, auth_headers_for: AuthHeaders, pseudonymizer: Pseudonymizer, role: str
) -> None:
    """Der Nachtrag für eine dritte Person ist ein legitimer Vorgang der
    aufsichtsführenden Rollen — und wird tokenisiert abgelegt."""
    headers = await auth_headers_for(f"bind-mt-{role}@foreman.de", role)
    machine_id = await _machine_id(client, headers)

    response = await client.post(
        "/api/v1/maintenance_events",
        json={"machine_id": machine_id, "type": "inspection", "performed_by": "4711"},
        headers=headers,
    )

    assert response.status_code == 201, response.text
    assert response.json()["performed_by"] == pseudonymizer.tokenize_worker("4711")
