# ============================================================
#  FOREMAN — llm/__init__.py
#  Zweck: Öffentliche Schnittstelle des Modell-Gateways (F-LLM). Das ist die
#         EINZIGE Fläche, die ein Reasoner berührt — Task-Enum, GatewayResponse,
#         das LLMGateway-Protokoll + die LiteLLMGateway-Implementierung, der
#         Grounding-Vertrag (Quelle/Report), die LLM-Settings und die Fehler-
#         hierarchie. Kein Export exponiert LiteLLM-Typen (harte Architektur-
#         Grenze des Briefings; LiteLLM lebt ausschließlich in backends.py).
#  Architektur-Einordnung: Schicht 2 — die Abstraktion, auf der jeder kommende
#         LLM-Reasoner (zuerst Ereignisketten) aufsetzt.
# ============================================================
from __future__ import annotations

from foreman.llm.config import LLMSettings, Priority, get_llm_settings
from foreman.llm.errors import (
    BackendUnavailable,
    GatewayConfigError,
    GatewayError,
    GatewayTimeout,
    GroundingViolation,
    RateLimited,
)
from foreman.llm.gateway import GatewayResponse, LiteLLMGateway, LLMGateway, Task
from foreman.llm.grounding import GroundingReport, GroundingSource

# Öffentliche Reasoner-Schnittstelle (sortiert; Gruppen: Gateway, Grounding,
# Config, Fehlerhierarchie — Details im Modul-Header).
__all__ = [
    "BackendUnavailable",
    "GatewayConfigError",
    "GatewayError",
    "GatewayResponse",
    "GatewayTimeout",
    "GroundingReport",
    "GroundingSource",
    "GroundingViolation",
    "LLMGateway",
    "LLMSettings",
    "LiteLLMGateway",
    "Priority",
    "RateLimited",
    "Task",
    "get_llm_settings",
]
