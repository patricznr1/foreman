# ============================================================
#  FOREMAN — tests/integration/test_stammdaten_pflege.py
#  Zweck: Die Anlagenstruktur (Linie → Maschine → Komponente → Datenpunkt) pflegt
#         der Betreiber, nicht jede angemeldete Person.
#  Architektur-Einordnung: Quality Gate §10.3 (Integration, braucht DB).
#  Warum die Rolle und nicht der Ausschnitt: Der Maschinen-Ausschnitt taugt hier
#         strukturell nicht als Maßstab — er leitet sich aus zugewiesenen Maschinen
#         ab, und eine frisch angelegte Linie enthält noch keine. Eine Scope-Prüfung
#         verböte, die erste Maschine einer Linie anzulegen. Wer pflegen darf, ist
#         deshalb eine Frage der Rollenmatrix.
#  Anschlusspunkt: Sobald es eine eigene Administrations-Rolle gibt, wandert die
#         Berechtigung dorthin. Bis dahin trägt sie `manager` — dieselbe Lösung,
#         die `api/routers/audit.py` für den Audit-Trail schon getroffen hat.
# ============================================================
from __future__ import annotations

from collections.abc import Awaitable, Callable

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration

AuthHeaders = Callable[[str, str], Awaitable[dict[str, str]]]

# Die vier Ebenen der Anlagenstruktur (§4: Linie → Maschine → Komponente → Datenpunkt),
# je mit einem Rumpf, der die Validierung besteht. `machine_id`/`line_id` werden im
# Test nachgereicht, damit die Fälle unabhängig voneinander laufen.
STAMMDATEN_PFADE = [
    pytest.param("/api/v1/lines", {"label": "Neue Linie"}, id="lines"),
    pytest.param("/api/v1/machines", {"label": "Neue Maschine"}, id="machines"),
    pytest.param("/api/v1/components", {"label": "Neue Komponente"}, id="components"),
    pytest.param("/api/v1/data_points", {"name": "vib", "kind": "analog"}, id="data_points"),
]

# Alle Rollen außer `manager`. Bewusst vollständig aufgezählt statt „alles außer X":
# Käme eine Rolle hinzu, soll dieser Test sie NICHT stillschweigend mitprüfen —
# dann ist eine Entscheidung fällig, und die Lücke in der Liste erzwingt sie.
NICHT_PFLEGENDE_ROLLEN = ["worker", "shift_lead", "technician"]


async def _maschine_und_linie(client: AsyncClient, verwalter: dict[str, str]) -> tuple[int, int]:
    """Legt Linie und Maschine als Verwalter an — der Aufbau, nicht der Prüfling."""
    linie = (await client.post("/api/v1/lines", json={"label": "L"}, headers=verwalter)).json()
    maschine = (
        await client.post(
            "/api/v1/machines", json={"label": "M", "line_id": linie["id"]}, headers=verwalter
        )
    ).json()
    return int(linie["id"]), int(maschine["id"])


@pytest.mark.parametrize("pfad,rumpf", STAMMDATEN_PFADE)
@pytest.mark.parametrize("rolle", NICHT_PFLEGENDE_ROLLEN)
async def test_ohne_verwaltungsrolle_keine_stammdaten(
    client: AsyncClient,
    auth_headers_for: AuthHeaders,
    pfad: str,
    rumpf: dict[str, object],
    rolle: str,
) -> None:
    """Wer die Anlage bedient, legt sie nicht an.

    Geprüft wird zusätzlich die BEGRÜNDUNG des 403: Der Maschinen-Ausschnitt
    antwortet mit derselben Zahl, und beide Regeln sollen unterscheidbar bleiben.
    """
    verwalter = await auth_headers_for("stamm-verwalter@x.de", "manager")
    linie_id, maschine_id = await _maschine_und_linie(client, verwalter)
    headers = await auth_headers_for(f"stamm-{rolle}@x.de", rolle)

    antwort = await client.post(
        pfad, json={**rumpf, "machine_id": maschine_id, "line_id": linie_id}, headers=headers
    )

    assert antwort.status_code == 403, antwort.text
    assert antwort.json()["detail"] == "Diese Aktion ist deiner Rolle nicht erlaubt"


@pytest.mark.parametrize("pfad,rumpf", STAMMDATEN_PFADE)
async def test_die_verwaltungsrolle_legt_stammdaten_an(
    client: AsyncClient,
    auth_headers_for: AuthHeaders,
    pfad: str,
    rumpf: dict[str, object],
) -> None:
    """Zwilling: Ohne ihn wäre der Test darüber auch dann grün, wenn NIEMAND mehr
    Stammdaten anlegen könnte — und die Anlage ließe sich nicht mehr einrichten."""
    verwalter = await auth_headers_for("stamm-verwalter@x.de", "manager")
    linie_id, maschine_id = await _maschine_und_linie(client, verwalter)

    antwort = await client.post(
        pfad, json={**rumpf, "machine_id": maschine_id, "line_id": linie_id}, headers=verwalter
    )

    assert antwort.status_code == 201, antwort.text


@pytest.mark.parametrize("pfad", [p.values[0] for p in STAMMDATEN_PFADE])
async def test_stammdaten_lesen_bleibt_allen_rollen_offen(
    client: AsyncClient, auth_headers_for: AuthHeaders, pfad: str
) -> None:
    """Gegenprobe: Die Beschränkung trifft das ANLEGEN, nicht das Lesen.

    Ohne sie wäre nicht auszuschließen, dass die Rollenregel versehentlich auch die
    Lese-Routen zumauert — dann sähe ein Werker seine eigene Maschine nicht mehr,
    und der Maschinen-Ausschnitt liefe ins Leere.
    """
    headers = await auth_headers_for("stamm-leser@x.de", "worker")

    antwort = await client.get(pfad, headers=headers)

    assert antwort.status_code == 200, antwort.text
