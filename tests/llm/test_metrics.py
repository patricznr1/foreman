# ============================================================
#  FOREMAN — tests/llm/test_metrics.py
#  Zweck: Pflicht-Test-Block für die Gateway-Metriken (F-LLM). Prüft, dass die
#         Kennzahlen je Gateway-Call (Backend/Task/Latenz/Tokens/Kosten/
#         Fallback/Fehler + Cache-Treffer) in derselben Registry landen, die
#         GET /metrics rendert (§11.1) — und damit unter /metrics erscheinen.
#  Architektur-Einordnung: Quality Gate §10.3 (Observability). Reine Unit-
#         Tests gegen die geteilte Registry; render_metrics() IST exakt das,
#         was der /metrics-Endpunkt (api/metrics.py) ausliefert.
# ============================================================
from __future__ import annotations

from foreman.observability import metrics


def test_gateway_kennzahlen_landen_in_der_metrics_registry() -> None:
    metrics.observe_gateway_call(
        backend="local",
        task="explanation",
        latency_seconds=0.2,
        success=True,
        prompt_tokens=10,
        completion_tokens=5,
        cost_usd=0.0,
        fallback_used=True,
    )
    metrics.record_gateway_cache_hit()

    body = metrics.render_metrics()[0].decode()
    # Alle Gateway-Familien erscheinen im Prometheus-Textformat (= /metrics).
    assert "foreman_llm_requests_total" in body
    assert "foreman_llm_latency_seconds" in body
    assert "foreman_llm_tokens_total" in body
    assert "foreman_llm_cost_usd_total" in body
    assert "foreman_llm_fallbacks_total" in body
    assert "foreman_llm_cache_hits_total" in body
    # Labels sind gesetzt (Reihenfolge-robust geprüft).
    assert 'backend="local"' in body
    assert 'task="explanation"' in body
    assert 'result="ok"' in body
    assert 'kind="prompt"' in body
    assert 'kind="completion"' in body


def test_gateway_zaehlt_erfolg_und_fehler_getrennt() -> None:
    metrics.observe_gateway_call(
        backend="cloud",
        task="synthesis",
        latency_seconds=0.1,
        success=False,
        prompt_tokens=1,
        completion_tokens=1,
        cost_usd=0.01,
        fallback_used=False,
    )
    body = metrics.render_metrics()[0].decode()
    assert 'backend="cloud"' in body
    assert 'result="error"' in body
