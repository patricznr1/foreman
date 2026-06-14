# ============================================================
#  FOREMAN — tests/unit/test_metrics.py
#  Zweck: Pflicht-Test-Block für die Prometheus-Metrik-Helfer (F4, §11.2).
#  Prüft: Reasoner-Zähler (Erfolg/Fehler) + Latenz, Drift-Kennzahlen
#  (Events, Detektionsverzug, Fehlalarme), Rendering im Prometheus-Textformat.
#  Architektur-Einordnung: Quality Gate §10.3 (Observability).
# ============================================================
from __future__ import annotations

from foreman.observability import metrics


def test_render_metrics_ist_prometheus_textformat_mit_drift_kennzahlen() -> None:
    metrics.observe_reasoner_run("drift", 0.5, success=True)
    metrics.record_drift_event()
    metrics.record_detection_delay(3600.0)
    metrics.record_false_alarm()
    metrics.record_false_alarm(2)

    payload, content_type = metrics.render_metrics()
    body = payload.decode()
    assert content_type.startswith("text/plain")
    assert "foreman_drift_events_total" in body
    assert "foreman_drift_detection_delay_seconds" in body
    assert "foreman_drift_false_alarms_total" in body
    assert "foreman_reasoner_requests_total" in body  # nach observe (Label gesetzt)


def test_observe_reasoner_run_zaehlt_erfolg_und_fehler_getrennt() -> None:
    metrics.observe_reasoner_run("drift", 0.1, success=True)
    metrics.observe_reasoner_run("drift", 0.2, success=False)
    body = metrics.render_metrics()[0].decode()
    assert 'reasoner="drift",result="ok"' in body
    assert 'reasoner="drift",result="error"' in body
