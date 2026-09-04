# ============================================================
#  FOREMAN — tests/unit/test_erkenntnis_saetze.py
#  Zweck: Die gespiegelten Saetze fuer Ereigniskette und Empfehlung tragen
#         Datensatznummer, Anlagenkennung und Entstehungszeit — und sind damit je
#         Rekonstruktion EINMALIG.
#  ANLASS (03./04.09.2026, beidseitig gemessen, C-124): Beide Bauer schrieben
#         „an Maschine <id>“ fest. Jede erneute Kette zu demselben Alarm mit gleichen
#         Zaehlern ergab denselben Text, und den verwirft der Plastic-Store der
#         Gegenstelle still als Hash-Dublette — samt created_at, recall_used und
#         occurred_at. Patrics Kette vom 03.09. war byte-gleich mit dem Spiegel vom
#         20.08. und kam nie an. Die Alias-Regel der Gegenstelle sah von dieser Art
#         nie eine Klammer.
#  ZWEI ZUSICHERUNGEN, beide mit Kontrollzwilling: die neue Form fuer angereicherte
#         Nutzlasten — und die ALTE Form, wortgleich, fuer den Altbestand, damit der
#         Nachlauf keine Zeile umschreibt.
# ============================================================
from __future__ import annotations

from foreman.substrate.content import baue_inhalt

KETTE_ALT = {
    "reasoner": "event_chain",
    "source_type": "event_chain",
    "source_id": None,
    "anchor_alarm_id": 4,
    "machine_id": 7,
    "event_count": 3,
    "confidence": "low",
    "is_hypothesis": True,
}
KETTE_NEU = {
    **KETTE_ALT,
    "source_id": 88,
    "machine_external_id": "PR-01",
    "machine_class": "servo_press",
    "component_type": None,
    "component_label": None,
    "created_at": "2026-09-03T19:29:28+00:00",
    "recall_used": True,
}
EMPFEHLUNG_ALT = {
    "reasoner": "failure_recommendation",
    "source_type": "failure_recommendation",
    "source_id": None,
    "prediction_id": 21,
    "machine_id": 8,
    "decision": "elevated_risk",
    "horizon_h": 336,
}
EMPFEHLUNG_NEU = {
    **EMPFEHLUNG_ALT,
    "source_id": 12,
    "machine_external_id": "PR-02",
    "created_at": "2026-09-04T06:10:00+00:00",
}


def test_die_kette_traegt_nummer_kennung_und_zeit() -> None:
    """DER TRAGENDE FALL: Datensatznummer vorn, Anlagenkennung mit Kennung und Zeit."""
    assert baue_inhalt("event_chain_reconstructed", KETTE_NEU) == (
        "Ereigniskette 88 zu Alarm 4 an PR-01 (Kennung 7, 2026-09-03T19:29:28+00:00): "
        "3 Ereignisse, Konfidenz low (Hypothese)."
    )


def test_zwei_rekonstruktionen_derselben_kette_ergeben_verschiedene_texte() -> None:
    """Die Zusicherung, um die es geht: Wiederholung ist kein Hash-Treffer mehr.

    Gleiche Kette, gleiche Zaehler — nur eine andere Erklaerungszeile und ein
    anderer Zeitpunkt. Vorher: byte-gleich, still verworfen.
    """
    zweite = {**KETTE_NEU, "source_id": 89, "created_at": "2026-09-04T07:00:00+00:00"}
    assert baue_inhalt("event_chain_reconstructed", KETTE_NEU) != baue_inhalt(
        "event_chain_reconstructed", zweite
    )


def test_der_altbestand_bleibt_wortgleich() -> None:
    """AUFBAU-KONTROLLE: Ohne die neuen Felder entsteht der bisherige Satz — byteweise.

    Der Nachlauf baut den Text aus der gespeicherten Nutzlast. Alte Zeilen tragen
    weder Nummer noch Kennung noch Zeit; aenderte sich ihr Satz, schriebe der
    Nachlauf den Altbestand um und erzeugte bei der Gegenstelle lauter neue
    Eintraege statt Wiederholungen.
    """
    assert baue_inhalt("event_chain_reconstructed", KETTE_ALT) == (
        "Ereigniskette zu Alarm 4 an Maschine 7: 3 Ereignisse, Konfidenz low (Hypothese)."
    )
    assert baue_inhalt("failure_recommendation", EMPFEHLUNG_ALT) == (
        "Werker-Empfehlung zu Vorhersage 21 an Maschine 8: Entscheidung elevated_risk, "
        "Horizont 336 h (simulationsbasiert, nicht validiert)."
    )


def test_die_empfehlung_traegt_dieselbe_form() -> None:
    assert baue_inhalt("failure_recommendation", EMPFEHLUNG_NEU) == (
        "Werker-Empfehlung 12 zu Vorhersage 21 an PR-02 (Kennung 8, 2026-09-04T06:10:00+00:00): "
        "Entscheidung elevated_risk, Horizont 336 h (simulationsbasiert, nicht validiert)."
    )
