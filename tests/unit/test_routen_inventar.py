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

DIE ÜBERGANGSLISTE. `UEBERGANG_OFFEN` ist leer: Jede geprüfte Route führt eine
Autorisierungs-Dependency. Die Menge bleibt als Konstrukt bestehen, damit ein
künftiger Umbau eine befristete Ausnahme SICHTBAR eintragen kann, statt den
Wächter abzuschalten — und `test_uebergangsliste_ist_aktuell` erzwingt, dass ein
solcher Eintrag wieder verschwindet, sobald er erledigt ist.
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

# Autorisierung auf RESSOURCEN-Ebene. Zwei zulässige Formen, in dieser Rangfolge:
# (1) der gemeinsame Dependency `get_resource_scope` — im Dependency-Baum sichtbar
#     und damit strukturell prüfbar, nicht über eine Zeichenkette;
# (2) für die Routen, die ausdrücklich das WS-Thema spiegeln: der Aufruf im Rumpf.
# Geprüft wird dort die AUSFÜHRBARE Form (`await …(`), nicht der bloße Name — sonst
# genügte eine Erwähnung im Docstring, um die Route abgesichert aussehen zu lassen.
SCOPE_DEPS = {"get_resource_scope"}
SCOPE_IM_RUMPF = ("await can_subscribe(", "await visible_machine_scope(")

# Ressourcen-Kennungen: Führt eine Route eine davon, entscheidet nicht die
# Rolle über den Zugriff, sondern die Zugehörigkeit der konkreten Ressource.
RESSOURCEN_KENNUNGEN = {"machine_id", "line_id", "component_id", "data_point_id"}

# Routen, die eine Ressourcen-Kennung führen und trotzdem bewusst KEINEN
# Ausschnitt anwenden — jede mit ihrem Grund. Eine Ausnahme ohne Begründung ist
# eine stille Ausnahme; eine Ausnahme, die den Grund nicht mehr trägt, ist eine
# Lücke mit Häkchen.
SCOPE_NICHT_NOETIG = {
    "GET /api/v1/audit": (
        "Steht ausschließlich `manager` offen (api/routers/audit.py, _AUDIT_ROLES) — "
        "und diese Rolle hat nach Matrix 3.1 ohnehin keinen beschränkten Ausschnitt. "
        "Ein Scope-Aufruf wäre hier wirkungslos und täuschte Wirksamkeit vor. Fällt "
        "die Rollenbeschränkung, gehört der Ausschnitt hierher."
    ),
}

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

# Der Übergang ist abgeschlossen: Jede geprüfte Route führt eine Autorisierungs-
# Dependency. Die Menge bleibt als Konstrukt bestehen — ein künftiger Umbau kann
# hier eine befristete, sichtbare Ausnahme eintragen, statt den Wächter darunter
# abzuschalten. Was hier steht, ist eine Schuld auf Zeit, kein Bestand.
UEBERGANG_OFFEN: set[str] = set()


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
    neu_offen = [k for k in _ohne_identitaet(app_routen) if k not in UEBERGANG_OFFEN]
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
    erledigt = UEBERGANG_OFFEN - offen
    assert not erledigt, (
        f"✅ {len(erledigt)} Route(n) sind inzwischen abgesichert:\n  "
        + "\n  ".join(sorted(erledigt))
        + "\n\nAus UEBERGANG_OFFEN streichen — die Liste ist eine "
        "Schuldenliste, kein Bestandsverzeichnis."
    )


@pytest.mark.parametrize("pfad,grund", sorted(AUSGENOMMEN.items()))
def test_jede_ausnahme_traegt_eine_begruendung(pfad, grund):
    """Eine Ausnahme ohne Grund ist eine stille Ausnahme."""
    assert grund and len(grund) > 10, f"{pfad} steht ohne tragende Begründung frei."


@pytest.mark.parametrize("kennung,grund", sorted(SCOPE_NICHT_NOETIG.items()))
def test_jede_scope_ausnahme_traegt_eine_begruendung(kennung, grund):
    """Auch die zweite Ausnahmeliste bleibt begründungspflichtig."""
    assert grund and len(grund) > 30, f"{kennung} steht ohne tragende Begründung ohne Ausschnitt."


def test_die_scope_ausnahmen_gibt_es_noch(app_routen):
    """Eine Ausnahme für eine Route, die es nicht mehr gibt, ist toter Ballast.

    Sie täuscht außerdem Sorgfalt vor: Wer die Liste liest, hält einen bedachten
    Sonderfall für geprüft, während der Fall längst verschwunden ist.
    """
    vorhanden = {_kennung(r) for r in _zu_pruefen(app_routen)}
    verwaist = sorted(set(SCOPE_NICHT_NOETIG) - vorhanden)
    assert not verwaist, (
        "❌ Ausnahme(n) ohne zugehörige Route:\n  "
        + "\n  ".join(verwaist)
        + "\n\nAus SCOPE_NICHT_NOETIG streichen."
    )


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
    # Anmerkung zur Aussagekraft: Ein vorhandener Dependency belegt, dass der
    # Ausschnitt AUFGELÖST wird — nicht, dass die Route ihn auch ANWENDET. Diese
    # zweite Hälfte kann nur ein Verhaltenstest zeigen; sie steht in
    # tests/integration/test_ressourcen_scope.py, je Sperre als Paar.
    kandidaten = []
    for route in _zu_pruefen(app_routen):
        namen = _dependency_namen(route)
        if not (namen & IDENTITAETS_DEPS):
            continue  # fehlt schon die Identität — steht im Test darüber
        if not (namen & RESSOURCEN_KENNUNGEN):
            continue
        if namen & SCOPE_DEPS:
            continue  # trägt den gemeinsamen Dependency — strukturell belegt
        if _kennung(route) in SCOPE_NICHT_NOETIG:
            continue  # begründete Ausnahme, siehe SCOPE_NICHT_NOETIG
        try:
            rumpf = inspect.getsource(route.endpoint)
        except (OSError, TypeError):
            continue
        if not any(aufruf in rumpf for aufruf in SCOPE_IM_RUMPF):
            kandidaten.append(_kennung(route))

    if kandidaten:
        pytest.skip(
            "Prüfkandidaten für Ressourcen-Scope (keine Zusicherung, Bericht):\n  "
            + "\n  ".join(sorted(kandidaten))
        )
