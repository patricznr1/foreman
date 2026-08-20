# ============================================================
#  FOREMAN — tests/release/test_substrat_antwortform.py
#  Zweck: Freigabe-Bedingung 2 der NEXUS-Veredelung — die REALE Antwortform des
#         Substrats ist gepinnt: was beim `remember` als Metadaten mitging, kommt
#         beim `recall` zurück (Weg payload → metadata → machine_id).
#  Architektur-Einordnung: Freigabe-Nachweis (kein Unit-Test) gegen eine echte
#         Gegenstelle. Läuft NUR mit `-m release`.
#  Verhalten bei fehlender Konfiguration: FEHLSCHLAG, nicht skip. Ein
#         übersprungener Freigabe-Test sieht im Lauf aus wie ein bestandener.
#  Namespace: eigener Freigabe-Namespace, NIE der Betriebs-Namespace — dieser
#         Test schreibt, und sein Schreibgut gehört nicht in den Bestand, gegen
#         den die Veredelung abruft (dieselbe Regel wie für den Smoke, §9).
# ============================================================
from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest

from foreman.config import Settings
from foreman.reasoners.event_chain.recall import map_recall_response
from foreman.substrate.client import SubstrateClient

pytestmark = pytest.mark.release

# Der Namespace, in dem der Freigabe-Nachweis schreibt.
FREIGABE_NAMESPACE = "foreman-release"
# Wohin das Lauf-Protokoll geschrieben wird (Bedingung 2 verlangt es).
PROTOKOLL = Path("docs/freigaben/laufprotokoll-substrat-antwortform.json")


def _settings_oder_fehlschlag() -> Settings:
    """Liest die Zugangsdaten — und schlägt fehl, wenn sie fehlen.

    Bewusst kein `pytest.skip`: dieser Test IST der Nachweis. Ohne Gegenstelle
    gibt es keinen Nachweis, und das muss im Lauf rot sein.
    """
    settings = Settings(_env_file=None)
    if not settings.substrate_base_url or not settings.substrate_token:
        pytest.fail(
            "Freigabe-Nachweis nicht fahrbar: SUBSTRATE_BASE_URL und SUBSTRATE_TOKEN "
            "müssen gesetzt sein. Dieser Test skippt bewusst nicht — ohne echte "
            "Gegenstelle gibt es keinen Nachweis über die Antwortform."
        )
    return settings


def _protokoll_schreiben(eintrag: dict[str, Any]) -> None:
    """Schreibt das Lauf-Protokoll (synchron — Dateizugriff gehoert nicht in den
    Ereignis-Zyklus, ruff ASYNC240)."""
    PROTOKOLL.parent.mkdir(parents=True, exist_ok=True)
    PROTOKOLL.write_text(json.dumps(eintrag, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def test_recall_liefert_die_beim_remember_geschriebenen_metadaten() -> None:
    """Der Weg payload → metadata → machine_id, an der echten Anlage.

    Geschrieben wird eine Payload in genau der Form, die der Dual-Write seit dem
    20.08.2026 erzeugt (source_type + source_id + machine_id). Geprüft wird, dass
    sie unverändert zurückkommt UND dass das Mapping sie liest — die Fassade
    könnte die Felder durchreichen und `map_recall_response` sie trotzdem
    verwerfen; beide Hälften gehören zum Nachweis.
    """
    settings = _settings_oder_fehlschlag()
    marker = f"freigabe-{uuid4().hex}"
    payload: dict[str, Any] = {
        "source_type": "alarm",
        "source_id": 4711,
        "machine_id": 3,
        "code": "AX-03-TEMP",
        "severity": "warning",
        "marker": marker,
    }
    client = SubstrateClient.from_settings(settings, namespace=FREIGABE_NAMESPACE)
    try:
        await client.remember(f"Freigabe-Nachweis Antwortform {marker}", metadata=payload)
        roh = await client.recall(marker, max_results=5)
    finally:
        await client.aclose()

    treffer = [t for t in roh.get("results", []) if marker in json.dumps(t, default=str)]
    assert treffer, f"Der eben geschriebene Eintrag {marker} kam nicht zurück: {roh}"
    zurueck = treffer[0]

    # 1) Die Fassade reicht die Metadaten unverändert durch.
    metadaten = zurueck.get("metadata") or {}
    for schluessel, wert in payload.items():
        assert metadaten.get(schluessel) == wert, (
            f"Metadaten-Feld {schluessel!r} kam als {metadaten.get(schluessel)!r} "
            f"zurück statt {wert!r}"
        )

    # 2) Das Mapping liest sie auch — sonst nützt das Durchreichen nichts.
    (item,) = map_recall_response({"results": [zurueck]}, max_results=1)
    assert item.machine_id == 3
    assert item.relevance is not None, "Ohne Ähnlichkeitsmaß ist der Treffer nicht rangierbar"
    assert item.occurred_at is not None, "Ohne Zeit ist der Treffer nicht rangierbar"

    # 3) Lauf-Protokoll (Bedingung 2: Datum, Instanz-Host, Antwortform).
    _protokoll_schreiben(
        {
            "geprueft_am": datetime.now(UTC).isoformat(),
            "instanz": settings.substrate_base_url,
            "namespace": FREIGABE_NAMESPACE,
            "gesendete_payload_felder": sorted(payload),
            "zurueckgegebene_felder": sorted(zurueck),
            "zurueckgegebene_metadaten_felder": sorted(metadaten),
            "gelesen": {
                "machine_id": item.machine_id,
                "relevance": item.relevance,
                "occurred_at": item.occurred_at.isoformat() if item.occurred_at else None,
            },
        }
    )


def test_freigabe_namespace_ist_nicht_der_betriebs_namespace() -> None:
    """Sonst verschmutzt ausgerechnet der Freigabe-Nachweis den Bestand,
    dessen Güte er belegen soll (§9, dieselbe Regel wie für den Smoke)."""
    settings = Settings(_env_file=None)
    assert FREIGABE_NAMESPACE != settings.substrate_namespace
    assert FREIGABE_NAMESPACE != settings.substrate_smoke_namespace
    assert os.environ.get("SUBSTRATE_NAMESPACE", "foreman") != FREIGABE_NAMESPACE
