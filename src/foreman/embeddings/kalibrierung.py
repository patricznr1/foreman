# ============================================================
#  FOREMAN — embeddings/kalibrierung.py
#  Zweck: Bindet jeden an Daten erhobenen Grenzwert an das Einbettungsmodell,
#         gegen das er erhoben wurde — und meldet beim Start, wenn ein anderes
#         läuft oder wenn die Grundlage gar nicht festgehalten ist.
#  Architektur-Einordnung: Querfunktion neben dem EmbeddingProvider (Schicht 2).
#         Reine Funktionen, kein Netz, kein Zustand — vollständig prüfbar.
#  Warum es diese Datei gibt: Cosinus-Abstände sind NICHT modellübergreifend
#         vergleichbar (Steck/Ekanadham/Kallus, WWW 2024). Dieselbe Zahl bedeutet
#         bei einem anderen Modell eine andere Strenge. Ein Grenzwert, der Treffer
#         verwirft, meldet seinen Ausfall nicht: Die Suche liefert weniger, und das
#         sieht von aussen aus wie ein leeres Archiv, nicht wie ein Defekt (C-048).
#  Konvention (§6): deutsche Kommentare, Emoji-Prefix im Log, keine PII.
# ============================================================
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from foreman.embeddings.backends import resolve_chain
from foreman.embeddings.config import (
    OPENAI_BACKEND,
    ST_BACKEND,
    EmbeddingSettings,
)


@dataclass(frozen=True, slots=True)
class Kalibrierung:
    """Ein an Daten erhobener Grenzwert samt der Bedingung, unter der er gilt.

    `modell` ist ausdrücklich optional: `None` heisst NICHT "gilt für alle",
    sondern "an welchem Modell erhoben wurde, ist nicht belegt". Der Unterschied
    ist der ganze Zweck dieser Klasse — ein Wert ohne Grundlage lässt sich nicht
    einmal widerlegen, und genau das fällt sonst niemandem auf.
    """

    name: str
    wert: float
    modell: str | None
    datum: str
    beleg: str  # Kennung im Aussagen-Register (claims/claims.yaml)


# Der Relevanz-Grenzwert der hybriden Notiz-Suche (config.archive_vector_max_distance).
#
# `modell=None` ist eine bewusste Angabe, kein vergessenes Feld: C-048 misst am
# 24.08.2026 "gegen die laufende Instanz" und nennt das Einbettungsmodell nicht;
# die Umgebung jener Instanz liegt nicht im Repository. GROUND_TRUTH §15.10 schreibt
# den Wert "bge-m3" zu — für diese Zuschreibung gibt es im Repository keine
# Fundstelle. Bis die Distanzverteilung gegen das tatsächlich laufende Modell
# erhoben ist, bleibt hier None und der Start meldet es.
ARCHIV_VEKTOR_GRENZWERT: Final = Kalibrierung(
    name="archive_vector_max_distance",
    wert=0.60,
    modell=None,
    datum="2026-08-24",
    beleg="C-048",
)

# Alles, was gegen ein Einbettungsmodell erhoben wurde. Eine Liste und nicht je
# ein Aufruf an der Fundstelle: Sonst prüft der Start nur, woran gerade jemand
# gedacht hat.
ALLE: Final[tuple[Kalibrierung, ...]] = (ARCHIV_VEKTOR_GRENZWERT,)


def aktives_modell(settings: EmbeddingSettings) -> str:
    """Nennt das Modell, das die erste Stufe der eingestellten Kette benutzt.

    Die Kette kommt aus `resolve_chain` und wird nicht nachgebildet — eine zweite
    Zuordnung Priority→Backend liefe früher oder später von der ersten weg.
    """
    erstes = resolve_chain(settings.priority)[0]
    if erstes == OPENAI_BACKEND:
        return settings.openai_model
    if erstes == ST_BACKEND:
        return settings.st_model
    return settings.model


def pruefe(kalibrierung: Kalibrierung, settings: EmbeddingSettings) -> str | None:
    """Liefert eine Meldung, wenn der Grenzwert für das laufende Modell nicht gilt.

    Zwei Fälle, beide melden — und der zweite ist der schlechtere von beiden:
    das laufende Modell ist ein ANDERES als das erhobene, oder es ist gar nicht
    festgehalten, gegen welches erhoben wurde.
    """
    laeuft = aktives_modell(settings)
    if kalibrierung.modell is None:
        return (
            f"{kalibrierung.name}={kalibrierung.wert} ist ungeprüft: gegen welches "
            f"Einbettungsmodell erhoben wurde, ist nicht belegt "
            f"({kalibrierung.beleg}, {kalibrierung.datum}). Es läuft '{laeuft}'."
        )
    if kalibrierung.modell != laeuft:
        return (
            f"{kalibrierung.name}={kalibrierung.wert} wurde gegen '{kalibrierung.modell}' "
            f"erhoben ({kalibrierung.beleg}, {kalibrierung.datum}), es läuft aber "
            f"'{laeuft}'. Cosinus-Abstände sind zwischen Modellen nicht vergleichbar — "
            f"der Wert bedeutet hier eine andere Strenge als dort."
        )
    return None


def offene_meldungen(settings: EmbeddingSettings) -> list[str]:
    """Alle Beanstandungen über sämtliche erhobenen Werte, in Reihenfolge von ALLE."""
    meldungen = [pruefe(k, settings) for k in ALLE]
    return [m for m in meldungen if m is not None]
