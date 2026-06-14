# ============================================================
#  FOREMAN — observability/metrics.py
#  Zweck: Prometheus-Metriken-Registry + Helfer (GROUND_TRUTH §11.1/§11.2,
#         /metrics ab F4). Request-/Latenz-Zähler je Reasoner plus drift-
#         spezifische Kennzahlen (Detektionsverzug, Fehlalarm-Zähler).
#  Architektur-Einordnung: Querschnitt (Schicht 2). Eigene CollectorRegistry —
#         entkoppelt vom globalen Default, damit Mehrfach-Importe (Tests) nicht
#         an doppelter Registrierung scheitern. Labels bewusst niedrig-kardinal
#         (reasoner/result) — keine machine_id/data_point_id (Kardinalitäts-Explosion).
#  Datenschutz (§8): keine PII in Metriken/Labels.
# ============================================================
from __future__ import annotations

from typing import Final

from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST

# Eigene Registry (nicht der globale Default) für saubere Kapselung + Testbarkeit.
REGISTRY: Final = CollectorRegistry()

REASONER_REQUESTS: Final = Counter(
    "foreman_reasoner_requests_total",
    "Anzahl der Reasoner-Aufrufe je Reasoner und Ergebnis.",
    ["reasoner", "result"],
    registry=REGISTRY,
)
REASONER_LATENCY: Final = Histogram(
    "foreman_reasoner_latency_seconds",
    "Latenz der Reasoner-Aufrufe je Reasoner (Sekunden).",
    ["reasoner"],
    registry=REGISTRY,
)
DRIFT_EVENTS: Final = Counter(
    "foreman_drift_events_total",
    "Anzahl erkannter, relevanter Drift-Ereignisse (operatorseitige Warnungen).",
    registry=REGISTRY,
)
DRIFT_DETECTION_DELAY: Final = Histogram(
    "foreman_drift_detection_delay_seconds",
    "Detektionsverzug erkannter Drift (t* -> Meldung), in Sekunden.",
    # Buckets von 1 h bis 20 d — Drift ist langsam (Stunden-Wochen).
    buckets=(3600, 21600, 86400, 259200, 604800, 1209600, 1728000),
    registry=REGISTRY,
)
DRIFT_FALSE_ALARMS: Final = Counter(
    "foreman_drift_false_alarms_total",
    "Als Fehlalarm gewertete Drift-Meldungen (driftfreie Strecken/Validierung).",
    registry=REGISTRY,
)


def observe_reasoner_run(reasoner: str, latency_seconds: float, *, success: bool) -> None:
    """Zählt einen Reasoner-Aufruf und seine Latenz (je Reasoner, Erfolg/Fehler)."""
    REASONER_REQUESTS.labels(reasoner=reasoner, result="ok" if success else "error").inc()
    REASONER_LATENCY.labels(reasoner=reasoner).observe(latency_seconds)


def record_drift_event() -> None:
    """Zählt ein erkanntes, relevantes Drift-Ereignis."""
    DRIFT_EVENTS.inc()


def record_detection_delay(seconds: float) -> None:
    """Trägt den Detektionsverzug (t* -> Meldung) einer erkannten Drift ein."""
    DRIFT_DETECTION_DELAY.observe(seconds)


def record_false_alarm(count: int = 1) -> None:
    """Zählt Fehlalarm-Meldungen (driftfreie Strecken)."""
    DRIFT_FALSE_ALARMS.inc(count)


def render_metrics() -> tuple[bytes, str]:
    """Rendert die Registry im Prometheus-Textformat plus den Content-Type."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
