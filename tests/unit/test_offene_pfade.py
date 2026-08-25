# ══════════════════════════════════════════════════════════════
# FOREMAN — Die offenen Pfade sind genau die aufgezählten
# Kein Präfix-Zufall, keine tokenfreie Methode, keine Landkarte im Betrieb.
# ══════════════════════════════════════════════════════════════
"""Hält die Angriffsfläche der Auth-Middleware klein und begründet.

WARUM OHNE DATENBANK. Alles hier entscheidet sich in der Middleware, bevor eine
Route ihre Session zieht. Der Test läuft deshalb gegen `create_app(settings)`
ohne `_migrated_db` — und wird dort, wo keine Postgres-Instanz erreichbar ist,
nicht still übersprungen.
"""

from __future__ import annotations

import pytest
from fastapi.routing import APIRoute
from httpx import ASGITransport, AsyncClient

from foreman.config import Settings
from foreman.main import create_app


def _settings(environment: str) -> Settings:
    return Settings(
        _env_file=None,
        database_url="postgresql+asyncpg://ungenutzt/ungenutzt",
        jwt_secret="test-secret-foreman-offene-pfade-0123456789",
        environment=environment,
        substrate_base_url=None,
        log_level="WARNING",
    )


@pytest.fixture
def entwicklungs_app():
    return create_app(_settings("development"))


async def _ohne_token(app, methode: str, pfad: str) -> int:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http:
        antwort = await http.request(methode, pfad)
    return antwort.status_code


# --- Präfix: die Doku-Pfade sind Namen, keine Anfangsbuchstaben ---


@pytest.mark.parametrize("pfad", ["/docs-admin", "/openapi.json.bak", "/redoc-intern"])
async def test_ein_pfad_neben_der_doku_bleibt_geschuetzt(entwicklungs_app, pfad: str) -> None:
    """Ein Pfad, der mit einem Doku-Namen BEGINNT, ist damit noch keine Doku.

    Heute existiert keiner dieser Pfade — die Antwort wäre also so oder so kein
    Erfolg. Geprüft wird deshalb die UNTERSCHEIDUNG: 401 heißt, die Middleware hat
    ihn für sich beansprucht; 404 hieße, sie hat ihn durchgelassen und erst die
    Routenauflösung hat ihn abgewiesen. Genau dieser Unterschied entscheidet, was
    passiert, sobald jemand einen solchen Pfad anlegt.
    """
    assert await _ohne_token(entwicklungs_app, "GET", pfad) == 401


@pytest.mark.parametrize("pfad", ["/docs", "/redoc", "/openapi.json"])
async def test_die_doku_selbst_bleibt_offen(entwicklungs_app, pfad: str) -> None:
    """Zwilling: Die aufgezählten Pfade bleiben ohne Token erreichbar.

    Ohne ihn wäre der Test darüber auch dann grün, wenn die Middleware einfach
    alles beanspruchte — dann prüfte er die Unterscheidung gar nicht mehr.
    """
    assert await _ohne_token(entwicklungs_app, "GET", pfad) == 200


# --- OPTIONS: keine Methode kommt ohne Token durch ---


async def test_options_verlangt_ein_token(entwicklungs_app) -> None:
    """OPTIONS ist der übliche Freibrief für CORS-Preflights — hier gibt es keine.

    FOREMAN richtet keine CORS-Middleware ein; das Frontend spricht über einen
    Proxy (frontend/next.config.ts). Eine tokenfreie Methode deckt damit nichts ab,
    was gebraucht würde, gibt aber jedem die Möglichkeit, Pfade auf ihre Existenz
    abzuklopfen. Kommt CORS später, gehört die Ausnahme in die CORSMiddleware.
    """
    assert await _ohne_token(entwicklungs_app, "OPTIONS", "/api/v1/machines") == 401


async def test_options_auf_einem_offenen_pfad_bleibt_offen(entwicklungs_app) -> None:
    """Zwilling: Der Gesundheitsruf ist offen — für jede Methode."""
    assert await _ohne_token(entwicklungs_app, "OPTIONS", "/health") != 401


# --- Die Landkarte gehört nicht in den Betrieb ---


def _pfade(app) -> set[str]:
    return {r.path for r in app.routes} | {r.path for r in app.routes if isinstance(r, APIRoute)}


def test_die_doku_ist_im_betrieb_nicht_ausgeliefert() -> None:
    """Im Produktionsbetrieb gibt es keine Schema-Endpunkte.

    Das Schema beschreibt jede Route, ihre Parameter und ihre Antwortformen. Für
    die Entwicklung ist das der halbe Wert des Werkzeugs; an einer öffentlich
    erreichbaren Adresse ist es eine Landkarte, die niemand braucht, der die
    Anwendung bedient — die Oberfläche kennt ihre Aufrufe.
    """
    betrieb = create_app(_settings("production"))

    assert betrieb.openapi_url is None
    assert betrieb.docs_url is None
    assert betrieb.redoc_url is None
    assert not {"/docs", "/redoc", "/openapi.json"} & _pfade(betrieb)


def test_in_der_entwicklung_bleibt_die_doku(entwicklungs_app) -> None:
    """Zwilling: Ohne ihn bliebe der Test darüber auch dann grün, wenn die Doku
    überhaupt nicht mehr gebaut würde — und niemandem fiele der Verlust auf."""
    assert entwicklungs_app.openapi_url == "/openapi.json"
    assert {"/docs", "/openapi.json"} <= _pfade(entwicklungs_app)
