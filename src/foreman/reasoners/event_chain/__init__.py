# ============================================================
#  FOREMAN — reasoners/event_chain/__init__.py
#  Zweck: Öffentliche Fläche des Ereignisketten-Reasoners (F6) — der ERSTE
#         LLM-Freitext-Reasoner und erste Konsument des F-LLM-Gateways. Er
#         verknüpft Drift-Events, Werkernotizen, Wartungen und NEXUS-Recall
#         ähnlicher Vergangenheits-Vorfälle zu einer gegroundeten Erzählung.
#  Architektur-Einordnung: Reasoning-Schicht (Schicht 2), aufgesetzt auf das
#         LLMGateway (F-LLM). Sicherheits-Invariante: `worker_notes.text` ist
#         untrusted Freitext → immer Spotlighting-Quelle, nie Instruktion.
# ============================================================
from __future__ import annotations

from foreman.reasoners.event_chain.schema import (
    ChainEvent,
    ChainEventType,
    ChainWindow,
    Confidence,
    EventChain,
    ReasonerExplanation,
    ReasonerExplanationDetailRead,
    ReasonerExplanationRead,
    ReconstructRequest,
    SiblingReference,
)

__all__ = [
    "ChainEvent",
    "ChainEventType",
    "ChainWindow",
    "Confidence",
    "EventChain",
    "ReasonerExplanation",
    "ReasonerExplanationDetailRead",
    "ReasonerExplanationRead",
    "ReconstructRequest",
    "SiblingReference",
]
