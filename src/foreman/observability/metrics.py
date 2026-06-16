# ============================================================
#  FOREMAN — observability/metrics.py
#  Zweck: Prometheus-Metriken-Registry + Helfer (GROUND_TRUTH §11.1/§11.2,
#         /metrics ab F4). Request-/Latenz-Zähler je Reasoner plus drift-
#         spezifische Kennzahlen (Detektionsverzug, Fehlalarm-Zähler) plus
#         Gateway-Kennzahlen je LLM-Call (F-LLM: Backend/Task/Latenz/Tokens/
#         Kosten/Fallback/Fehler + Cache-Treffer).
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

# --- Gateway-Kennzahlen (F-LLM, §11.1) — je Call: Backend/Task/Latenz/Tokens/
#     Kosten/Fallback/Fehler. Labels bewusst niedrig-kardinal (backend ∈ {local,
#     cloud}; task ∈ {explanation,synthesis,classification}; result ∈ {ok,error};
#     kind ∈ {prompt,completion}) — keine machine_id/PII (§8). ---
GATEWAY_REQUESTS: Final = Counter(
    "foreman_llm_requests_total",
    "Anzahl der Gateway-Aufrufe je Backend, Task und Ergebnis.",
    ["backend", "task", "result"],
    registry=REGISTRY,
)
GATEWAY_LATENCY: Final = Histogram(
    "foreman_llm_latency_seconds",
    "Latenz der Gateway-Aufrufe je Backend und Task (Sekunden).",
    ["backend", "task"],
    registry=REGISTRY,
)
GATEWAY_TOKENS: Final = Counter(
    "foreman_llm_tokens_total",
    "Verbrauchte Tokens je Backend, Task und Art (prompt/completion).",
    ["backend", "task", "kind"],
    registry=REGISTRY,
)
GATEWAY_COST: Final = Counter(
    "foreman_llm_cost_usd_total",
    "Geschätzte Inferenz-Kosten (USD) je Backend.",
    ["backend"],
    registry=REGISTRY,
)
GATEWAY_FALLBACKS: Final = Counter(
    "foreman_llm_fallbacks_total",
    "Anzahl der Backend-Fallbacks (primäres Backend nicht erreichbar).",
    registry=REGISTRY,
)
GATEWAY_CACHE_HITS: Final = Counter(
    "foreman_llm_cache_hits_total",
    "Anzahl der aus dem Antwort-Cache bedienten Gateway-Aufrufe.",
    registry=REGISTRY,
)

# --- Ereignisketten-Reasoner (F6) — Erklär-Ergebnisse + NEXUS-Recall + die
#     Injection-Containment-Sicht (geflaggte unbelegte Inhalte je Erklärung).
#     Labels niedrig-kardinal (result ∈ {clean,flagged} bzw. {hit,miss}). ---
EVENT_CHAIN_EXPLANATIONS: Final = Counter(
    "foreman_event_chain_explanations_total",
    "Anzahl der Ereignisketten-Erklärungen, getrennt nach geflaggt/sauber.",
    ["result"],
    registry=REGISTRY,
)
EVENT_CHAIN_RECALL: Final = Counter(
    "foreman_event_chain_recall_total",
    "NEXUS-Recall-Ausgänge des Ereignisketten-Reasoners (Treffer/kein Treffer).",
    ["result"],
    registry=REGISTRY,
)

# --- Embedding-Schicht (F-SEM, §11.2) — je embed()-Call: Backend/Latenz/Ergebnis
#     + Durchsatz (Anzahl embeddeter Texte). Labels niedrig-kardinal
#     (backend ∈ {ollama,sentence_transformers}; result ∈ {ok,error}) — keine PII,
#     keine Notiz-Texte, keine Vektoren (§8). ---
EMBED_REQUESTS: Final = Counter(
    "foreman_embed_requests_total",
    "Anzahl der Embedding-Aufrufe je Backend und Ergebnis.",
    ["backend", "result"],
    registry=REGISTRY,
)
EMBED_LATENCY: Final = Histogram(
    "foreman_embed_latency_seconds",
    "Latenz der Embedding-Aufrufe je Backend (Sekunden).",
    ["backend"],
    registry=REGISTRY,
)
EMBED_TEXTS: Final = Counter(
    "foreman_embed_texts_total",
    "Anzahl der eingebetteten Texte je Backend (Durchsatz).",
    ["backend"],
    registry=REGISTRY,
)


# --- Ausfallvorhersage-Reasoner (F-PRED, §11.2) — je Vorhersage: Datenregime +
#     Entscheidung + Wahrscheinlichkeits-Verteilung. Das Label `data_regime`
#     (= 'simulation') ist auf ALLEN foreman_failure_*-Kennzahlen Pflicht — der
#     Sim-Vorbehalt ist auch in den Metriken sichtbar (§16). Labels niedrig-kardinal
#     (data_regime ∈ {simulation}; decision ∈ {elevated_risk,normal}) — keine PII. ---
FAILURE_PREDICTIONS: Final = Counter(
    "foreman_failure_predictions_total",
    "Anzahl der Ausfallvorhersagen je Datenregime und Entscheidung.",
    ["data_regime", "decision"],
    registry=REGISTRY,
)
FAILURE_PROBABILITY: Final = Histogram(
    "foreman_failure_probability",
    "Verteilung der vorhergesagten Ausfallwahrscheinlichkeiten je Datenregime.",
    ["data_regime"],
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
    registry=REGISTRY,
)

# --- LLM-Werker-Empfehlung (F-REC, §11.2) — der Erklär-Layer über der Vorhersage.
#     Auch hier ist `data_regime` (= 'simulation') Pflicht-Label — der Sim-Vorbehalt
#     bleibt im Monitoring sichtbar (§16). `result` niedrig-kardinal: issued |
#     rejected_numeric (unbelegte Zahl, Invariante I) | rejected_overclaim
#     (Umdeutung des Vorbehalts, Invariante II). Keine PII. ---
FAILURE_RECOMMENDATIONS: Final = Counter(
    "foreman_failure_recommendation_total",
    "Anzahl der LLM-Werker-Empfehlungen je Datenregime und Ausgang.",
    ["data_regime", "result"],
    registry=REGISTRY,
)
FAILURE_RECOMMENDATION_RECALL: Final = Counter(
    "foreman_failure_recommendation_recall_total",
    "NEXUS-Recall-Ausgänge des Empfehlungs-Reasoners (Treffer/kein Treffer).",
    ["result"],
    registry=REGISTRY,
)


# --- MCP-Schnittstelle (F7, §11.2) — je Tool-Aufruf: Tool-Name + Ergebnis + Latenz.
#     FOREMAN als offener Knoten: read-only Tools an Drittsysteme. Labels bewusst
#     niedrig-kardinal (tool aus festem Set; result ∈ {ok,error}) — keine machine_id,
#     keine Tool-Payloads mit Personenbezug, keine internen Vokabeln (§8). ---
MCP_REQUESTS: Final = Counter(
    "foreman_mcp_requests_total",
    "Anzahl der MCP-Tool-Aufrufe je Tool und Ergebnis.",
    ["tool", "result"],
    registry=REGISTRY,
)
MCP_LATENCY: Final = Histogram(
    "foreman_mcp_latency_seconds",
    "Latenz der MCP-Tool-Aufrufe je Tool (Sekunden).",
    ["tool"],
    registry=REGISTRY,
)


def observe_mcp_call(*, tool: str, latency_seconds: float, success: bool) -> None:
    """Zählt einen MCP-Tool-Aufruf und seine Latenz (je Tool, Erfolg/Fehler, F7)."""
    MCP_REQUESTS.labels(tool=tool, result="ok" if success else "error").inc()
    MCP_LATENCY.labels(tool=tool).observe(latency_seconds)


def observe_failure_prediction(*, data_regime: str, decision: str, probability: float) -> None:
    """Zählt eine Ausfallvorhersage + ihre Wahrscheinlichkeit (F-PRED, §11.2).

    `data_regime` ist Pflicht-Label (Sim-Vorbehalt sichtbar in den Metriken, §16).
    """
    FAILURE_PREDICTIONS.labels(data_regime=data_regime, decision=decision).inc()
    FAILURE_PROBABILITY.labels(data_regime=data_regime).observe(probability)


def observe_failure_recommendation(*, data_regime: str, result: str) -> None:
    """Zählt eine LLM-Werker-Empfehlung (F-REC, §11.2).

    `data_regime` ist Pflicht-Label (Sim-Vorbehalt sichtbar in den Metriken, §16).
    `result` ∈ {issued, rejected_numeric, rejected_overclaim}.
    """
    FAILURE_RECOMMENDATIONS.labels(data_regime=data_regime, result=result).inc()


def record_failure_recommendation_recall(result: str) -> None:
    """Zählt einen NEXUS-Recall-Ausgang des Empfehlungs-Reasoners (result ∈ {hit, miss})."""
    FAILURE_RECOMMENDATION_RECALL.labels(result=result).inc()


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


def observe_gateway_call(
    *,
    backend: str,
    task: str,
    latency_seconds: float,
    success: bool,
    prompt_tokens: int,
    completion_tokens: int,
    cost_usd: float,
    fallback_used: bool,
) -> None:
    """Trägt die Kennzahlen eines Gateway-Calls ein (F-LLM, §11.1)."""
    GATEWAY_REQUESTS.labels(backend=backend, task=task, result="ok" if success else "error").inc()
    GATEWAY_LATENCY.labels(backend=backend, task=task).observe(latency_seconds)
    GATEWAY_TOKENS.labels(backend=backend, task=task, kind="prompt").inc(prompt_tokens)
    GATEWAY_TOKENS.labels(backend=backend, task=task, kind="completion").inc(completion_tokens)
    GATEWAY_COST.labels(backend=backend).inc(cost_usd)
    if fallback_used:
        GATEWAY_FALLBACKS.inc()


def record_gateway_cache_hit() -> None:
    """Zählt einen aus dem Antwort-Cache bedienten Gateway-Aufruf."""
    GATEWAY_CACHE_HITS.inc()


def record_event_chain_explanation(*, flagged: bool) -> None:
    """Zählt eine erzeugte Ereignisketten-Erklärung (geflaggt = unbelegte Inhalte)."""
    EVENT_CHAIN_EXPLANATIONS.labels(result="flagged" if flagged else "clean").inc()


def record_event_chain_recall(result: str) -> None:
    """Zählt einen NEXUS-Recall-Ausgang des Reasoners (result ∈ {hit, miss})."""
    EVENT_CHAIN_RECALL.labels(result=result).inc()


def observe_embedding(*, backend: str, latency_seconds: float, success: bool, n_texts: int) -> None:
    """Trägt die Kennzahlen eines Embedding-Calls ein (F-SEM, §11.2).

    `n_texts` ist die Anzahl der im Call eingebetteten Texte (Durchsatz); bei
    Erfolg mitgezählt. Keine PII/keine Notiz-Texte/keine Vektoren (§8).
    """
    EMBED_REQUESTS.labels(backend=backend, result="ok" if success else "error").inc()
    EMBED_LATENCY.labels(backend=backend).observe(latency_seconds)
    if success and n_texts:
        EMBED_TEXTS.labels(backend=backend).inc(n_texts)


def render_metrics() -> tuple[bytes, str]:
    """Rendert die Registry im Prometheus-Textformat plus den Content-Type."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
