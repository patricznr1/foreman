# ============================================================
#  FOREMAN — tests/reasoners/failure/test_recommendation_recall.py
#  Zweck: NEXUS-Recall ähnlicher Vorlauf-Muster (F-REC, Baustein 1). Geprüft wird
#         die PII-freie Query-Bildung (Maschinenklasse + Top-Faktor-Signatur +
#         Entscheidung) und das STRIKT best-effort-Verhalten: kein Substrat /
#         Substrat-Ausfall blockiert die Empfehlung nie (leere Liste, keine
#         Exception). Der reale SubstrateClient wird mit httpx.MockTransport
#         getrieben (kein Netz).
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime

import httpx

from foreman.db.models import Machine
from foreman.reasoners.failure.recall import build_runup_query, recall_similar_runups
from foreman.reasoners.failure.schema import FailurePredictionRead, TopFactor
from foreman.substrate.client import SubstrateClient

_REF = datetime(2026, 3, 20, 12, 0, tzinfo=UTC)


def _prediction(**overrides: object) -> FailurePredictionRead:
    base: dict[str, object] = {
        "id": 1,
        "machine_id": 7,
        "reference_time": _REF,
        "horizon_h": 336,
        "probability": 0.87,
        "decision_threshold": 0.5,
        "decision": "elevated_risk",
        "top_factors": [
            TopFactor(
                feature="vibration_rms_velocity_spindle_bearing",
                value=3.9,
                shap=0.42,
                direction="increases_risk",
            ),
            TopFactor(
                feature="bearing_temperature_spindle",
                value=61.0,
                shap=0.18,
                direction="increases_risk",
            ),
        ],
        "validation_status": "simulation_only",
        "data_regime": "simulation",
        "model_version": "failure_lgbm@test",
        "created_at": _REF,
    }
    base.update(overrides)
    return FailurePredictionRead(**base)  # type: ignore[arg-type]


def _substrate(handler: httpx.MockTransport) -> SubstrateClient:
    client = httpx.AsyncClient(transport=handler, base_url="http://substrate")
    return SubstrateClient(base_url="http://substrate", client=client)


# --- Query-Bildung (PII-frei) ---
def test_build_runup_query_enthaelt_klasse_faktoren_entscheidung() -> None:
    machine = Machine(id=7, label="BAZ-01", machine_class="cnc_machining_center")
    query = build_runup_query(machine, _prediction())
    assert "cnc_machining_center" in query
    assert "vibration_rms_velocity_spindle_bearing" in query
    assert "elevated_risk" in query


def test_build_runup_query_ohne_merkmale_ist_generisch() -> None:
    query = build_runup_query(None, _prediction(top_factors=[]))
    assert "ähnlicher Vorlauf" in query
    # Auch ohne Maschine/Faktoren bleibt die Query PII-frei und nutzbar.
    assert "elevated_risk" in query


# --- best-effort Mapping ---
async def test_recall_ohne_substrat_leer() -> None:
    assert await recall_similar_runups(None, "query") == []


async def test_recall_erfolgreich_mapped() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"results": [{"content": "Damals: Lager getauscht nach Vibrationsanstieg"}]}
        )

    substrate = _substrate(httpx.MockTransport(handler))
    items = await recall_similar_runups(substrate, "query", max_results=5)
    assert len(items) == 1
    assert "Lager" in items[0].content


async def test_recall_bei_substrat_ausfall_blockiert_nicht() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"detail": "down"})

    substrate = _substrate(httpx.MockTransport(handler))
    # Darf NICHT werfen — best-effort: Ausfall → leere Liste.
    items = await recall_similar_runups(substrate, "query")
    assert items == []
