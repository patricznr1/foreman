# ============================================================
#  FOREMAN — api/deps.py
#  Zweck: Wiederverwendbare FastAPI-Dependencies (DB, Settings, Auth,
#         Pseudonymizer, Redactor, Substrat-Client).
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Dependency Injection
#         statt globaler Zustände (§6).
# ============================================================
from __future__ import annotations

import os
from collections.abc import AsyncIterator
from functools import lru_cache
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.config import Settings, get_settings
from foreman.core.pseudonymize import Pseudonymizer, build_pseudonymizer
from foreman.core.redact import PresidioRedactor, Redactor, build_redactor
from foreman.core.security import decode_access_token
from foreman.db.models import User
from foreman.db.session import get_session
from foreman.embeddings import EmbeddingProvider, LocalEmbeddingProvider, get_embedding_settings
from foreman.llm import LiteLLMGateway, LLMGateway, get_llm_settings
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


SubstrateClientDep = Annotated[SubstrateClient | None, Depends(get_substrate_client)]


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
