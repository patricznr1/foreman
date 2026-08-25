# ══════════════════════════════════════════════════════════════
# FOREMAN — Routen-Inventar mit Scope-Pflicht
# Jede Route mit Ressourcenbezug führt eine Autorisierungs-Dependency.
# ══════════════════════════════════════════════════════════════
"""Hält die Zugriffskontrolle an der Route fest, nicht nur an der Middleware.

WARUM DIE MIDDLEWARE NICHT GENÜGT. `AuthMiddleware` verlangt ein gültiges Token
für alles außer /health, /auth/* und der Doku. Das ist AUTHENTIFIZIERUNG: Sie
beantwortet „wer bist du", nicht „darfst du genau diese Ressource sehen". Ein
`worker` mit gültigem Token hat die richtige Rolle für `GET /api/worker_notes`
— er darf nur nicht die Notizen fremder Maschinen lesen. Diese zweite Frage
stellt die Middleware nie; sie kann nur an der Route gestellt werden.

WARUM GEGEN create_app(). Ein direkter Aufruf der Handler-Funktion umgeht
FastAPIs Dependency-Auflösung vollständig — die Prüfung fände gar nicht statt.
Hier wird die real gebaute App befragt, samt aufgelöster Dependency-Bäume.

WARUM OHNE DATENBANK. Der Test braucht `test_settings`, aber nicht
`_migrated_db`. Er läuft damit auch dort, wo keine Postgres-Instanz erreichbar
ist, statt still übersprungen zu werden — ein Wächter, der in der CI
weggeskippt wird, ist keiner.

DIE ÜBERGANGSLISTE. `OFFEN_STAND_2026_08_25` führt die Routen, die beim
Einführen dieses Tests bereits ohne Autorisierungs-Dependency waren. Sie sind
ein Befund, kein Normalzustand. Der Aufbau folgt dem Baseline-Prinzip aus
`.claude-quality-baseline.json`: Vorhandene Schulden blockieren nicht, aber
sie können weder wachsen noch stillschweigend bestehen bleiben —
`test_uebergangsliste_ist_aktuell` erzwingt, dass jede abgesicherte Route
sofort von der Liste verschwindet.
"""

import inspect

import pytest
from fastapi.routing import APIRoute

from foreman.config import Settings
from foreman.main import create_app

# Dependencies, die eine Identität an der Route durchsetzen. `require_roles`
# erzeugt `_require`, das seinerseits `CurrentUser` führt — die rekursive
# Sammlung unten findet deshalb beide.
IDENTITAETS_DEPS = {"get_current_user", "_require"}

# Der Helfer, der die sichtbaren Maschinen eines Nutzers bestimmt.
SCOPE_HELFER = {"visible_machine_scope"}

# Ressourcen-Kennungen: Führt eine Route eine davon, entscheidet nicht die
# Rolle über den Zugriff, sondern die Zugehörigkeit der konkreten Ressource.
RESSOURCEN_KENNUNGEN = {"machine_id", "line_id", "component_id", "data_point_id"}

GEPRUEFTE_METHODEN = {"GET", "POST", "PUT", "PATCH", "DELETE"}

# Bewusst offen — jeder Eintrag trägt seinen Grund. Eine Ausnahme ohne
# Begründung ist eine stille Ausnahme und damit wertlos.
AUSGENOMMEN = {
    "/health": "Betriebsprüfung, gibt keine Ressourcendaten heraus",
    "/auth/login": "erzeugt die Identität erst — laut middleware.py die einzige offene Schreib-Route",
    "/metrics": "Prometheus-Scraper ohne JWT, §11.2 — netzseitig abgeschottet, gibt keine Ressourcendaten heraus",
    "/openapi.json": "Schema, keine Daten",
    "/docs": "Schema, keine Daten",
    "/docs/oauth2-redirect": "Schema, keine Daten",
    "/redoc": "Schema, keine Daten",
}

# Befund vom 25.08.2026: beim Einführen dieses Tests offene Routen.
# Aus der Messung erzeugt, nicht abgetippt. Diese Liste MUSS schrumpfen.
OFFEN_STAND_2026_08_25: set[str] = {
    "GET /api/v1/alarms",
    "GET /api/v1/alarms/{alarm_id}",
    "GET /api/v1/components",
    "GET /api/v1/components/{component_id}",
    "GET /api/v1/data_points",
    "GET /api/v1/data_points/{data_point_id}",
    "GET /api/v1/lines",
    "GET /api/v1/lines/{line_id}",
    "GET /api/v1/machines",
    "GET /api/v1/machines/{machine_id}",
    "GET /api/v1/maintenance_events",
    "GET /api/v1/maintenance_events/{event_id}",
    "GET /api/v1/production_runs",
    "GET /api/v1/production_runs/{run_id}",
    "GET /api/v1/reasoners/drift/alarms",
    "GET /api/v1/reasoners/event_chain/explanations",
    "GET /api/v1/reasoners/event_chain/explanations/{explanation_id}",
    "GET /api/v1/reasoners/event_chain/explanations/{explanation_id}/siblings",
    "GET /api/v1/reasoners/failure/predictions",
    "GET /api/v1/reasoners/failure/predictions/{prediction_id}",
    "GET /api/v1/reasoners/failure/predictions/{prediction_id}/recommendation",
    "GET /api/v1/substrate/smoke",
    "GET /api/v1/worker_notes",
    "GET /api/v1/worker_notes/{note_id}",
    "POST /api/v1/alarms",
    "POST /api/v1/components",
    "POST /api/v1/data_points",
    "POST /api/v1/lines",
    "POST /api/v1/machines",
    "POST /api/v1/production_runs",
    "POST /api/v1/readings",
}


@pytest.fixture(scope="module")
def app_routen(test_settings: Settings):
    """Die real gebaute App — ohne Datenbank, ohne Lifespan."""
    return list(create_app(test_settings).routes)


def _dependency_namen(route: APIRoute) -> set[str]:
    """Alle Dependency-Namen einer Route, auch geschachtelte."""
    namen: set[str] = set()
    offen = list(route.dependant.dependencies)
    while offen:
        abhaengigkeit = offen.pop()
        aufruf = getattr(abhaengigkeit, "call", None)
        if aufruf is not None:
            namen.add(getattr(aufruf, "__name__", str(aufruf)))
        offen.extend(abhaengigkeit.dependencies)
    # Parameter-Dependencies (Annotated[..., Depends(...)]) hängen ebenfalls im
    # Baum, tauchen aber je nach FastAPI-Fassung als eigene Ebene auf.
    for feld in ("path_params", "query_params", "body_params"):
        for parameter in getattr(route.dependant, feld, []):
            namen.add(parameter.name)
    return namen


def _kennung(route: APIRoute) -> str:
    methoden = sorted(route.methods & GEPRUEFTE_METHODEN)
    return f"{methoden[0]} {route.path}" if methoden else route.path


def _zu_pruefen(routen) -> list[APIRoute]:
    return [
        r
        for r in routen
        if isinstance(r, APIRoute)
        and (r.methods & GEPRUEFTE_METHODEN)
        and r.path not in AUSGENOMMEN
    ]


def _ohne_identitaet(routen) -> list[str]:
    return sorted(
        _kennung(r) for r in _zu_pruefen(routen) if not (_dependency_namen(r) & IDENTITAETS_DEPS)
    )


def test_aufbau_der_pruefung_traegt(app_routen):
    """Zwilling: belegt, dass die Prüfung überhaupt etwas sieht.

    Ohne ihn wäre jede Aussage unten auch dann grün, wenn create_app() keine
    Routen liefert oder die Dependency-Namen ins Leere zeigen — ein Häkchen,
    das Sicherheit vortäuscht.
    """
    zu_pruefen = _zu_pruefen(app_routen)
    assert zu_pruefen, "❌ Die Prüfung sieht keine einzige Route — Aufbau kaputt."

    mit_identitaet = [r for r in zu_pruefen if _dependency_namen(r) & IDENTITAETS_DEPS]
    assert mit_identitaet, (
        "❌ Keine einzige Route trägt eine Dependency aus IDENTITAETS_DEPS. "
        "Entweder sind die Namen falsch geschrieben oder die Auflösung greift "
        "nicht — in beiden Fällen wäre der Hauptprüfung nicht zu trauen."
    )


def test_keine_neue_route_ohne_scope(app_routen):
    """Eine NEUE Route ohne Autorisierungs-Dependency ist ein Befund."""
    neu_offen = [k for k in _ohne_identitaet(app_routen) if k not in OFFEN_STAND_2026_08_25]
    assert not neu_offen, (
        f"❌ {len(neu_offen)} Route(n) ohne Autorisierungs-Dependency:\n  "
        + "\n  ".join(neu_offen)
        + "\n\nDie Middleware prüft nur, DASS ein Token da ist — nicht, ob diese "
        "Identität genau diese Ressource sehen darf. Entweder `CurrentUser` bzw. "
        "`require_roles(...)` an die Route hängen oder mit Begründung in "
        "AUSGENOMMEN aufnehmen. Stillschweigend offen lassen: nein."
    )


def test_uebergangsliste_ist_aktuell(app_routen):
    """Erzwingt, dass die Schuldenliste schrumpft, statt zu versteinern.

    Sobald eine Route abgesichert wird, muss sie von der Liste verschwinden.
    Ohne diesen Test bliebe ein Eintrag auch dann stehen, wenn er längst
    erledigt ist — und die Liste behauptete dauerhaft mehr Schulden, als es
    gibt. Umgekehrt fiele nicht auf, wenn die Absicherung wieder herausfällt.
    """
    offen = set(_ohne_identitaet(app_routen))
    erledigt = OFFEN_STAND_2026_08_25 - offen
    assert not erledigt, (
        f"✅ {len(erledigt)} Route(n) sind inzwischen abgesichert:\n  "
        + "\n  ".join(sorted(erledigt))
        + "\n\nAus OFFEN_STAND_2026_08_25 streichen — die Liste ist eine "
        "Schuldenliste, kein Bestandsverzeichnis."
    )


@pytest.mark.parametrize("pfad,grund", sorted(AUSGENOMMEN.items()))
def test_jede_ausnahme_traegt_eine_begruendung(pfad, grund):
    """Eine Ausnahme ohne Grund ist eine stille Ausnahme."""
    assert grund and len(grund) > 10, f"{pfad} steht ohne tragende Begründung frei."


def test_ressourcen_routen_rufen_den_scope_helfer(app_routen):
    """Zweite Stufe: Identität allein genügt nicht, wo eine Kennung im Spiel ist.

    Führt eine Route eine Ressourcen-Kennung (machine_id o. ä.) oder gibt sie
    eine Liste zurück, die danach gefiltert gehört, dann entscheidet nicht die
    Rolle über den Zugriff, sondern die Zugehörigkeit der konkreten Ressource.
    Das sieht kein Dependency-Baum — geprüft wird deshalb der Rumpf.

    Bewusst als Bericht und nicht als harte Zusicherung: Welche Route eine
    Filterung BRAUCHT, ist eine fachliche Entscheidung. Der Test macht die
    Kandidaten sichtbar; er entscheidet nicht an Patrics Stelle.
    """
    kandidaten = []
    for route in _zu_pruefen(app_routen):
        namen = _dependency_namen(route)
        if not (namen & IDENTITAETS_DEPS):
            continue  # fehlt schon die Identität — steht im Test darüber
        if not (namen & RESSOURCEN_KENNUNGEN):
            continue
        try:
            rumpf = inspect.getsource(route.endpoint)
        except (OSError, TypeError):
            continue
        if not any(helfer in rumpf for helfer in SCOPE_HELFER):
            kandidaten.append(_kennung(route))

    if kandidaten:
        pytest.skip(
            "Prüfkandidaten für Ressourcen-Scope (keine Zusicherung, Bericht):\n  "
            + "\n  ".join(sorted(kandidaten))
        )
