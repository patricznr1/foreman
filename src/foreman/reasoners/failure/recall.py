# ============================================================
#  FOREMAN — reasoners/failure/recall.py
#  Zweck: NEXUS-Recall ähnlicher VORLAUF-Muster für die Werker-Empfehlung (F-REC,
#         Baustein 1) — die „hatten wir so einen Vorlauf schon mal?"-Funktion.
#         Bildet aus dem Maschinen-Kontext + der Top-Faktor-Signatur der Vorhersage
#         eine PII-freie Recall-Query und ruft über den SubstrateClient ähnliche
#         frühere Vorfälle/Vorläufe ab.
#  Architektur-Einordnung: Brücke Reasoning-Schicht → Substrat (GROUND_TRUTH §9).
#  Verhalten: STRIKT best-effort. Kein Substrat / Substrat-Ausfall blockiert die
#         Empfehlung nie — sie wird dann ohne historischen Kontext erzeugt (leere
#         Liste). Logs ohne PII (die Query trägt nur Maschinenklasse / technische
#         Feature-Tags / Entscheidung).
#  Sicherheit: Recall-Inhalte sind externer Freitext → in den Grounding-Quellen
#         werden sie als untrusted geführt (siehe grounding.py). Die defensive
#         Mapping-Mechanik (RecallItem/map_recall_response) wird aus dem F6-Recall
#         wiederverwendet — reine, getestete Substrat-Antwort-Normalisierung.
# ============================================================
from __future__ import annotations

from foreman.db.models import Machine
from foreman.logging_setup import REASON, get_logger
from foreman.reasoners.event_chain.recall import RecallItem, map_recall_response
from foreman.reasoners.failure.schema import FailurePredictionRead
from foreman.substrate.client import SubstrateClient

logger = get_logger("foreman.reasoners.failure.recall")

# Wie viele der treibenden SHAP-Faktoren in die Recall-Signatur einfließen.
_QUERY_TOP_FACTORS = 3


def build_runup_query(machine: Machine | None, prediction: FailurePredictionRead) -> str:
    """Baut die Recall-Query aus Maschinen-Kontext + Top-Faktor-Signatur (PII-frei).

    Nutzt Maschinenklasse + die treibenden Feature-Namen (technische Tags) + die
    operative Entscheidung — keine Werker-Freitexte, keine Personen-/IDs mit
    Personenbezug. Fällt auf eine generische Formulierung zurück, wenn keine
    Merkmale vorliegen.
    """
    parts: list[str] = ["ähnlicher Vorlauf"]
    if machine is not None and machine.machine_class:
        parts.append(f"Maschinenklasse {machine.machine_class}")
    top_features = [factor.feature for factor in prediction.top_factors[:_QUERY_TOP_FACTORS]]
    if top_features:
        parts.append("Risikofaktoren " + ", ".join(top_features))
    parts.append(f"Entscheidung {prediction.decision}")
    return " ".join(parts)


async def recall_similar_runups(
    substrate: SubstrateClient | None,
    query: str,
    *,
    max_results: int = 5,
) -> list[RecallItem]:
    """Ruft ähnliche frühere Vorläufe/Vorfälle ab — STRIKT best-effort.

    Kein Substrat konfiguriert → leere Liste. Jeder Substrat-Fehler wird gefangen
    und führt zur leeren Liste (die Empfehlung wird dann ohne historischen Kontext
    erzeugt). Es wird NIE eine Exception nach oben gereicht.
    """
    if substrate is None:
        return []
    try:
        data = await substrate.recall(query, max_results=max_results)
        # Mapping INNERHALB des try: ein unerwartetes Recall-Format darf den
        # best-effort-Vertrag nicht brechen → wird hier mitgefangen.
        return map_recall_response(data, max_results=max_results)
    except Exception as exc:
        # Bewusst breit (best-effort): JEDER Recall-Fehler → kein Recall, nie Abbruch.
        logger.warning(
            "%s NEXUS-Recall (Vorlauf) fehlgeschlagen (best-effort, ohne Kontext): %s",
            REASON,
            exc,
        )
        return []
