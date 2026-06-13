# ============================================================
#  FOREMAN — substrate/smoke.py
#  Zweck: remember→recall-Round-Trip gegen das Gedächtnis-Substrat (§9).
#  Architektur-Einordnung: Boot-/Health-Prüfung der Substrat-Anbindung.
#  Verhalten: legt eine eindeutig markierte Test-Erinnerung ab, ruft sie ab und
#         prüft, ob die Markierung zurückkommt. Ergebnis {ok, latency_ms}.
#         Ein Fehlschlag blockiert NICHT — er wird geloggt und gemeldet (Fallback §9).
# ============================================================
from __future__ import annotations

import json
from time import perf_counter
from uuid import uuid4

from foreman.logging_setup import ERROR, MEMORY, OK, get_logger
from foreman.schemas.substrate import SubstrateSmokeResult
from foreman.substrate.client import SubstrateClient, SubstrateError

logger = get_logger("foreman.substrate.smoke")


async def run_substrate_smoke(client: SubstrateClient) -> SubstrateSmokeResult:
    """Führt einen remember→recall-Round-Trip aus und liefert {ok, latency_ms}."""
    marker = f"foreman-smoke-{uuid4().hex}"
    content = f"FOREMAN Substrat-Smoke {marker}"
    start = perf_counter()
    detail: str | None = None
    ok = False
    try:
        await client.remember(content, metadata={"kind": "smoke", "marker": marker})
        recalled = await client.recall(marker, max_results=5)
        # Robust gegen unbekannte Antwort-Form: Markierung im serialisierten Ergebnis suchen.
        ok = marker in json.dumps(recalled, ensure_ascii=False, default=str)
        if not ok:
            detail = "Markierung im Recall-Ergebnis nicht gefunden"
    except SubstrateError as exc:
        detail = str(exc)
    latency_ms = round((perf_counter() - start) * 1000, 2)

    if ok:
        logger.info("%s Substrat-Smoke ok (latency_ms=%s)", OK, latency_ms)
    else:
        # Kein PII; nur technische Diagnose. Fehlschlag ist nicht-blockierend.
        logger.warning(
            "%s Substrat-Smoke fehlgeschlagen (latency_ms=%s, detail=%s)",
            ERROR,
            latency_ms,
            detail,
        )
    logger.debug("%s Substrat-Smoke abgeschlossen", MEMORY)
    return SubstrateSmokeResult(ok=ok, latency_ms=latency_ms, detail=detail)
