# ============================================================
#  FOREMAN — ingestion/registry.py
#  Zweck: Registry/Loader für Quell-Adapter — aktive Adapter werden per Config
#         (Namensliste) aufgelöst und gebaut.
#  Architektur-Einordnung: Ingestion (Schicht 2). Entkoppelt den IngestionService
#         von konkreten Adapter-Implementierungen: der Service kennt nur
#         SourceAdapter, die Registry kennt die Factories.
# ============================================================
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from foreman.ingestion.adapter import SourceAdapter

# Eine Adapter-Factory baut aus benannten Parametern eine SourceAdapter-Instanz.
AdapterFactory = Callable[..., SourceAdapter]

# Modul-weite Registry (bewusst dokumentierter Zustand, §6): Name → Factory.
_REGISTRY: dict[str, AdapterFactory] = {}


class AdapterNotRegisteredError(KeyError):
    """Angeforderter Adapter ist nicht registriert (Deutsch, §6)."""


def register_adapter(name: str, factory: AdapterFactory) -> None:
    """Registriert eine Adapter-Factory unter einem Namen (idempotent überschreibend)."""
    _REGISTRY[name] = factory


def available_adapters() -> tuple[str, ...]:
    """Liste der registrierten Adapter-Namen (stabil sortiert)."""
    return tuple(sorted(_REGISTRY))


def create_adapter(name: str, **config: Any) -> SourceAdapter:
    """Baut einen registrierten Adapter mit den übergebenen Parametern.

    Wirft AdapterNotRegisteredError mit klarer deutscher Meldung, wenn der Name
    unbekannt ist (z. B. Tippfehler in der Config).
    """
    try:
        factory = _REGISTRY[name]
    except KeyError as exc:
        known = ", ".join(available_adapters()) or "(keine)"
        raise AdapterNotRegisteredError(
            f"Adapter '{name}' ist nicht registriert. Bekannt: {known}."
        ) from exc
    return factory(**config)


def load_active_adapters(
    active: list[str], configs: dict[str, dict[str, Any]] | None = None
) -> list[SourceAdapter]:
    """Lädt die per Config aktiven Adapter.

    `active` ist die Namensliste (z. B. aus Settings); `configs` liefert je
    Adapter die Bau-Parameter. Reihenfolge der Liste bleibt erhalten.
    """
    configs = configs or {}
    return [create_adapter(name, **configs.get(name, {})) for name in active]
