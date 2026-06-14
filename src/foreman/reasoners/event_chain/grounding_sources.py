# ============================================================
#  FOREMAN — reasoners/event_chain/grounding_sources.py
#  Zweck: Bau der GroundingSource-Liste fürs Gateway (F6, Baustein 3) aus der
#         rekonstruierten Kette + den NEXUS-Recall-Treffern.
#  Architektur-Einordnung: Reasoning-Schicht (F6) → LLM-Schicht (F-LLM). Der
#         Reasoner LIEFERT die Quellen; das Gateway ERZWINGT Spotlighting/Grounding.
#  ZENTRALE SICHERHEITS-INVARIANTE (Brief §2.3, Schutz-Doc §5.1):
#         `worker_notes.text` ist untrusted Freitext → IMMER `trusted=False`
#         (Spotlighting-Quelle, nie Instruktion). NEXUS-Recall-Inhalte sind
#         externer Freitext → ebenfalls `trusted=False` (belegen keine Zahlen).
#         Nur strukturierte DB-/Reasoner-Daten (Alarm/Wartung) sind `trusted=True`.
#         Diese Funktion HEBT NIEMALS eine untrusted Quelle auf trusted an — sie
#         übernimmt das `trusted`-Flag der Kette unverändert.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence

from foreman.llm import GroundingSource
from foreman.reasoners.event_chain.recall import RecallItem
from foreman.reasoners.event_chain.schema import EventChain

# Präfix der Recall-Quellen-IDs (untrusted, externer Vergangenheits-Freitext).
RECALL_SOURCE_PREFIX = "recall"


def build_grounding_sources(
    chain: EventChain, recall_items: Sequence[RecallItem] = ()
) -> list[GroundingSource]:
    """Baut die Grounding-Quellen: je Ketten-Ereignis + je Recall-Treffer eine
    Quelle mit eindeutiger `source_id`.

    Das `trusted`-Flag wird aus dem Ketten-Ereignis UNVERÄNDERT übernommen
    (Werkernotizen bleiben untrusted). Recall-Treffer sind grundsätzlich untrusted.
    """
    sources: list[GroundingSource] = [
        GroundingSource(source_id=event.source_id, content=event.summary, trusted=event.trusted)
        for event in chain.events
    ]
    sources.extend(
        GroundingSource(
            source_id=f"{RECALL_SOURCE_PREFIX}:{index}", content=item.content, trusted=False
        )
        for index, item in enumerate(recall_items)
    )
    return sources


def allowed_source_ids(sources: Sequence[GroundingSource]) -> tuple[str, ...]:
    """Die Whitelist gültiger source_ids (für den ReasonerExplanation-Output-Guard)."""
    return tuple(source.source_id for source in sources)
