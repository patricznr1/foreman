# ============================================================
#  FOREMAN — api/deps.py
#  Zweck: Wiederverwendbare FastAPI-Dependencies (DB, Settings, Auth,
#         Pseudonymizer, Redactor, Substrat-Client).
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Dependency Injection
#         statt globaler Zustände (§6).
# ============================================================
from __future__ import annotations

import os
from collections.abc import AsyncIterator, Callable, Iterable
from functools import lru_cache
from typing import Annotated, Any

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.config import Settings, get_settings
from foreman.core.pseudonymize import Pseudonymizer, build_pseudonymizer
from foreman.core.redact import PresidioRedactor, Redactor, build_redactor
from foreman.core.security import decode_access_token
from foreman.db.models import User
from foreman.db.session import get_session
from foreman.embeddings import EmbeddingProvider, LocalEmbeddingProvider, get_embedding_settings
from foreman.llm import LiteLLMGateway, LLMGateway, get_llm_settings
from foreman.realtime.authz import can_see_line, visible_line_scope, visible_machine_scope
from foreman.reasoners.failure.model import DEFAULT_ARTIFACT_PATH, FailureModel, load_model
from foreman.substrate.client import SubstrateClient

# --- Basis-Dependencies ---
SettingsDep = Annotated[Settings, Depends(get_settings)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def _extract_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nicht authentifiziert",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return authorization.split(" ", 1)[1].strip()


async def get_current_user(
    session: SessionDep,
    settings: SettingsDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Lädt den authentifizierten Nutzer aus dem Bearer-JWT. 401 bei Ungültigkeit."""
    token = _extract_bearer(authorization)
    try:
        payload = decode_access_token(token, settings)
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ungültiges oder abgelaufenes Token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    subject = payload.get("sub")
    if subject is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token ohne Subjekt")
    user = await session.get(User, int(subject))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Nutzer existiert nicht"
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*allowed: str) -> Callable[[User], User]:
    """Dependency-Factory: erzwingt SERVERSEITIG eine der erlaubten Rollen — über die
    FE-UX-Sperre hinaus, damit direkte API-Calls die Rollen-Matrix nicht umgehen
    können (§21.18). 403, wenn die Rolle nicht erlaubt ist. Authentifizierung bleibt
    Vorbedingung (`get_current_user` → 401). KEINE Aktorik — nur Zugriffskontrolle.
    """
    allowed_roles = frozenset(allowed)

    def _require(user: CurrentUser) -> User:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Diese Aktion ist deiner Rolle nicht erlaubt",
            )
        return user

    return _require


# --- Ressourcen-Scope an der Route (§20.4, Rollenmatrix 3.1) ---
class ResourceScope:
    """Der Ausschnitt der Anlage, den der anfragende Nutzer lesen darf.

    Die Auth-Middleware beantwortet „wer bist du". Diese Klasse beantwortet die
    zweite Frage, die sie nie stellt: „darfst du GENAU DIESE Ressource sehen".
    Ein `worker` mit gültigem Token hat die richtige Rolle für die Notizliste —
    er darf nur nicht die Berichte fremder Maschinen darin finden.

    EINE Quelle für die beiden Formen, in denen eine Ressourcen-Route fragt:
    `limit_to` beschneidet eine LISTE auf den erlaubten Ausschnitt, `require`
    entscheidet über eine AUSDRÜCKLICH angefragte Maschine, `can_see` über eine
    bereits geladene Zeile. Alle drei hängen an `visible_machine_scope` — demselben
    Resolver, den der Live-Push nutzt. Der Strich hält damit auf HTTP wie auf dem
    WebSocket; getrennte Umsetzungen wären die Stelle, an der die Transporte
    auseinanderlaufen.

    Zwei Ebenen, dieselbe Rollenmatrix: Maschinen (`machine_ids`, `can_see`,
    `require`, `limit_to`) und die Linien darüber (`line_ids`, `can_see_line`,
    `require_line`, `limit_to_lines`). Die Linien-Sicht ist aus der Maschinen-Sicht
    abgeleitet, nicht getrennt gepflegt — wer eine Maschine sieht, sieht ihre Linie.

    Jeder Ausschnitt wird je Anfrage EINMAL aufgelöst: Die Auflösung kostet eine
    Abfrage, die sonst bei jeder Prüfung derselben Anfrage erneut anfiele.
    """

    def __init__(self, session: AsyncSession, user: User) -> None:
        self._session = session
        self._user = user
        self._ids: list[int] | None = None
        self._resolved = False
        self._line_ids: list[int] | None = None
        self._lines_resolved = False

    @property
    def user(self) -> User:
        """Der anfragende Nutzer — für Routen, die zusätzlich die Rolle brauchen."""
        return self._user

    async def machine_ids(self) -> list[int] | None:
        """Die sichtbaren Maschinen. `None` heißt unbeschränkt, `[]` heißt keine."""
        if not self._resolved:
            self._ids = await visible_machine_scope(self._session, self._user)
            self._resolved = True
        return self._ids

    async def can_see(self, machine_id: int | None) -> bool:
        """Ob eine bereits geladene Zeile im Ausschnitt liegt (default-deny).

        `machine_id=None` steht für eine Zeile ohne Maschinenbezug: Für eine
        beschränkte Rolle gibt es dann nichts, woran die Zugehörigkeit hinge —
        also nein. Unbeschränkte Rollen sehen sie weiterhin.
        """
        ids = await self.machine_ids()
        if ids is None:
            return True
        return machine_id is not None and machine_id in ids

    async def require(self, machine_id: int) -> None:
        """403, wenn die ausdrücklich angefragte Maschine außerhalb des Ausschnitts liegt.

        Für Maschinen-Kennungen, die aus Query oder Rumpf kommen — dort ist die
        Existenz kein Geheimnis (Stammdatum) und die klare Absage die ehrlichere
        Antwort. Beim Einzelabruf über eine Datensatz-Kennung wird stattdessen
        `can_see` geprüft und die bestehende 404-Antwort verwendet, damit ein 403
        die Existenz der Zeile nicht bestätigt.
        """
        await self.require_all((machine_id,))

    async def require_all(self, machine_ids: Iterable[int]) -> None:
        """403, sobald AUCH NUR EINE der Maschinen außerhalb des Ausschnitts liegt.

        Für Anfragen, die mehrere Maschinen auf einmal berühren — ein Messwert-Batch
        erreicht über seine Datenpunkte leicht Dutzende. Der Ausschnitt wird einmal
        aufgelöst statt je Kennung.

        Alles-oder-nichts ist hier die richtige Härte: Ein Batch, aus dem still die
        unerlaubten Zeilen fielen, meldete Erfolg über eine Aufnahme, die so nie
        stattgefunden hat.
        """
        ids = await self.machine_ids()
        if ids is None:
            return
        erlaubt = set(ids)
        if any(machine_id not in erlaubt for machine_id in machine_ids):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Kein Zugriff auf diese Maschine",
            )

    async def limit_to(
        self, stmt: Select[Any], column: Any, *, machine_id: int | None = None
    ) -> Select[Any]:
        """Beschränkt ein Listen-SELECT auf den erlaubten Ausschnitt.

        `machine_id` ist die AUSDRÜCKLICH angefragte Maschine (Query-Parameter).
        Liegt sie außerhalb des Ausschnitts, endet die Anfrage mit 403 — eine
        stillschweigend leere Liste würde die Absage als „nichts vorhanden" tarnen.
        Ohne Angabe wird auf den gesamten Ausschnitt beschränkt: unbeschränkte Rolle
        → Statement unverändert; leerer Ausschnitt → `IN ()` liefert nichts, was der
        default-deny-Vorgabe entspricht.

        Beide Fälle liegen HIER und nicht in den Routen — sonst übernähme früher oder
        später eine Route nur die halbe Prüfung.
        """
        if machine_id is not None:
            await self.require(machine_id)
            return stmt.where(column == machine_id)
        ids = await self.machine_ids()
        return stmt if ids is None else stmt.where(column.in_(ids))

    async def for_query(self, machine_id: int | None) -> list[int] | None:
        """Der Ausschnitt für einen Pfad, der seine Bedingung selbst baut.

        Wie `limit_to`, nur für die Suchpfade: Sie ranken über Postgres-Volltext und
        Vektor-Distanz und sind als Roh-SQL geschrieben, nehmen also kein
        SELECT-Objekt entgegen. Die Reihenfolge bleibt dieselbe und liegt deshalb
        auch hier an EINER Stelle — erst die ausdrücklich angefragte Maschine prüfen
        (403 außerhalb), dann den Ausschnitt herausgeben.

        Rückgabe `None` heißt unbeschränkt, `[]` heißt nichts erlaubt. Der Aufrufer
        reicht den Wert an `machine_scope_sql` weiter, das die Unterscheidung hält.
        """
        if machine_id is not None:
            await self.require(machine_id)
        return await self.machine_ids()

    # --- Linien-Ebene: dieselben drei Formen, ein Stockwerk höher ---

    async def line_ids(self) -> list[int] | None:
        """Die sichtbaren Linien. `None` heißt unbeschränkt, `[]` heißt keine."""
        if not self._lines_resolved:
            self._line_ids = await visible_line_scope(self._session, self._user)
            self._lines_resolved = True
        return self._line_ids

    async def can_see_line(self, line_id: int | None) -> bool:
        """Ob eine bereits geladene Zeile im Linien-Ausschnitt liegt (default-deny)."""
        ids = await self.line_ids()
        if ids is None:
            return True
        return line_id is not None and line_id in ids

    async def require_line(self, line_id: int) -> None:
        """403, wenn die ausdrücklich angefragte Linie außerhalb des Ausschnitts liegt."""
        if not await can_see_line(self._session, self._user, line_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Kein Zugriff auf diese Linie",
            )

    async def limit_to_lines(
        self, stmt: Select[Any], column: Any, *, line_id: int | None = None
    ) -> Select[Any]:
        """Wie `limit_to`, nur entlang der Linien-Zugehörigkeit.

        Bewusst eine eigene Methode statt eines Schalters an `limit_to`: Welche
        Ebene gilt, hängt an der Spalte, und ein vertauschter Schalter fiele nicht
        auf — eine Liste käme dann mit den falschen Kennungen gefiltert zurück und
        sähe trotzdem plausibel aus.
        """
        if line_id is not None:
            await self.require_line(line_id)
            return stmt.where(column == line_id)
        ids = await self.line_ids()
        return stmt if ids is None else stmt.where(column.in_(ids))


async def get_resource_scope(session: SessionDep, user: CurrentUser) -> ResourceScope:
    """FastAPI-Dependency: der Maschinen-Ausschnitt des anfragenden Nutzers.

    Bringt die Identität mit (`CurrentUser`), sodass eine Route, die diesen
    Dependency führt, beide Prüfstufen an einer Stelle hat.
    """
    return ResourceScope(session, user)


ResourceScopeDep = Annotated[ResourceScope, Depends(get_resource_scope)]


def get_pseudonymizer(settings: SettingsDep) -> Pseudonymizer:
    """Baut den Pseudonymizer (HMAC) aus der Config."""
    return build_pseudonymizer(settings)


PseudonymizerDep = Annotated[Pseudonymizer, Depends(get_pseudonymizer)]


@lru_cache(maxsize=1)
def _redactor_singleton() -> PresidioRedactor:
    # Einmalig gebaut; das schwere spaCy-Modell wird erst beim ersten Aufruf geladen.
    return build_redactor()


def get_redactor() -> Redactor:
    """Liefert den (gecachten) NER-Redactor. In Tests via Override ersetzbar."""
    return _redactor_singleton()


RedactorDep = Annotated[Redactor, Depends(get_redactor)]


async def get_substrate_client(
    settings: SettingsDep,
) -> AsyncIterator[SubstrateClient | None]:
    """Liefert den Substrat-Client oder None (nicht konfiguriert). Schließt sauber."""
    if not settings.substrate_base_url:
        yield None
        return
    client = SubstrateClient.from_settings(settings)
    try:
        yield client
    finally:
        await client.aclose()


async def get_substrate_smoke_client(
    settings: SettingsDep,
) -> AsyncIterator[SubstrateClient | None]:
    """Wie `get_substrate_client`, aber auf dem Smoke-Namespace (§9).

    Getrennt, weil der Smoke schreibt: seine Test-Erinnerungen gehören nicht in den
    Bestand, gegen den die Archiv-Suche abruft.
    """
    if not settings.substrate_base_url:
        yield None
        return
    client = SubstrateClient.from_settings(settings, namespace=settings.substrate_smoke_namespace)
    try:
        yield client
    finally:
        await client.aclose()


SubstrateClientDep = Annotated[SubstrateClient | None, Depends(get_substrate_client)]
SubstrateSmokeClientDep = Annotated[SubstrateClient | None, Depends(get_substrate_smoke_client)]


# --- LLM-Gateway (F-LLM) — F6 (Ereignisketten) ist der erste Konsument ---
@lru_cache(maxsize=1)
def _llm_gateway_singleton() -> LiteLLMGateway:
    """Baut das Gateway einmalig aus der LLM-Config (Rate-Limit + Cache leben mit
    über die App-Lebensdauer). In Tests via Override ersetzt."""
    return LiteLLMGateway.from_settings(get_llm_settings())


def get_llm_gateway() -> LLMGateway:
    """FastAPI-Dependency: das (gecachte) LLM-Gateway als Protokoll-Typ — kein
    LiteLLM-Typ in reasoner-fähigen Pfaden (harte Architektur-Grenze)."""
    return _llm_gateway_singleton()


GatewayDep = Annotated[LLMGateway, Depends(get_llm_gateway)]


# --- Embedding-Provider (F-SEM) — Such-Route + semantische Notiz-Auswahl ---
@lru_cache(maxsize=1)
def _embedding_provider_singleton() -> LocalEmbeddingProvider:
    """Baut den Embedding-Provider einmalig aus der Config (über die App-Lebensdauer).
    In Tests via Override ersetzt."""
    return LocalEmbeddingProvider.from_settings(get_embedding_settings())


def get_embedding_provider() -> EmbeddingProvider:
    """FastAPI-Dependency: der (gecachte) Embedding-Provider als Protokoll-Typ —
    kein Backend-/Library-Typ in aufrufenden Pfaden (harte Architektur-Grenze)."""
    return _embedding_provider_singleton()


EmbeddingProviderDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]


# --- Ausfallvorhersage-Modell (F-PRED) — gebündeltes Demonstrator-Artefakt ---
@lru_cache(maxsize=1)
def _failure_model_singleton() -> FailureModel:
    """Lädt das F-PRED-Artefakt einmalig (über die App-Lebensdauer; SHAP-Explainer
    lebt mit). Override via FOREMAN_FAILURE_MODEL_PATH. In Tests via Override ersetzt.

    Demonstrator auf Simulationsdaten (§16): validation_status=simulation_only ist
    in den Artefakt-Metadaten verankert und wird durchgereicht."""
    override = os.environ.get("FOREMAN_FAILURE_MODEL_PATH")
    return load_model(override if override else DEFAULT_ARTIFACT_PATH)


def get_failure_model() -> FailureModel:
    """FastAPI-Dependency: das (gecachte) F-PRED-Modell."""
    return _failure_model_singleton()


FailureModelDep = Annotated[FailureModel, Depends(get_failure_model)]
