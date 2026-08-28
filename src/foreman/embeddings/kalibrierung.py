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
# ERHOBEN GEGEN ARCTIC (C-091, 28.08.2026). Bis hierher stand `modell=None` — nicht
# als vergessenes Feld, sondern als Aussage: C-048 mass am 24.08.2026 "gegen die
# laufende Instanz", ohne das Einbettungsmodell zu nennen. Diese Lücke ist zu.
#
# WARUM DER WERT SICH VERSCHIEBT: Vektoren verschiedener Modelle liegen in
# verschiedenen Räumen, und ein Abstand ist nur innerhalb eines Raumes eine Zahl
# mit Bedeutung. Arctic bildet dieselben Sachverhalte auf grössere Abstände ab als
# das vorige Modell; derselbe Zahlenwert schneidet damit viel schärfer. Bei 0,60
# blieben 6 von 10 Anfragen des Bewertungssatzes OHNE einen einzigen zutreffenden
# Treffer — die Suche arbeitete faktisch als reine Volltextsuche. Genau der
# Ausfall, den C-048 beschrieben hat, nur mit vertauschten Vorzeichen.
#
# WARUM 0,75 UND NICHT MEHR: 0,60 → 0,75 trägt (Trefferquote +0,213, Ranggüte
# +0,142, verdichtet +0,198, je p=0,016 im exakten Permutationstest; kein einziger
# verlorener Treffer, 70 % der Anfragen mit Zusatztreffer). Der weitere Schritt auf
# 0,85 ist NICHT gezeigt (p=0,250) — und dort sättigt die Ausgabe: alle 150 Plätze
# gefüllt, der Grenzwert schneidet nichts mehr ab und wäre kein Relevanzboden mehr.
ARCHIV_VEKTOR_GRENZWERT: Final = Kalibrierung(
    name="archive_vector_max_distance",
    wert=0.75,
    modell="Snowflake/snowflake-arctic-embed-l-v2.0",
    datum="2026-08-28",
    beleg="C-091",
)

# Alles, was gegen ein Einbettungsmodell erhoben wurde. Eine Liste und nicht je
# ein Aufruf an der Fundstelle: Sonst prüft der Start nur, woran gerade jemand
# gedacht hat.
ALLE: Final[tuple[Kalibrierung, ...]] = (ARCHIV_VEKTOR_GRENZWERT,)


# Der Präfix, den ein Modell für ANFRAGEN verlangt (Dokumente bekommen keinen).
#
# AM MODELL, NICHT AN EINEM SCHALTER: Ein Schalter lässt sich beim Modellwechsel
# vergessen, und dann läuft das neue Modell falsch — ohne Fehler, nur mit
# schlechteren Treffern. Die Zuordnung hier kann man nicht vergessen; wer ein
# Modell einträgt, muss den Präfix mit entscheiden.
#
# BELEGT AUS DER MODELLKARTE, nicht aus dem Gedächtnis: Arctic v2.0 verlangt
# `query: ` ausdrücklich — im Sentence-Transformers-Beispiel als
# `prompt_name="query"`, im Transformers-Beispiel als `query_prefix = 'query: '`,
# und `config_sentence_transformers.json` führt den Prompt. OpenAI und bge-m3
# kennen keinen Präfix.
QUERY_PRAEFIX: Final[dict[str, str]] = {
    # OpenAI-Cloud — kein Präfix.
    "text-embedding-3-small": "",
    "text-embedding-3-large": "",
    # bge-m3, lokal über Ollama bzw. sentence-transformers — kein Präfix.
    "bge-m3": "",
    "BAAI/bge-m3": "",
    # Snowflake Arctic v2.0 — VERLANGT den Präfix auf der Anfrageseite.
    "Snowflake/snowflake-arctic-embed-l-v2.0": "query: ",
    "Snowflake/snowflake-arctic-embed-m-v2.0": "query: ",
    "snowflake-arctic-embed2": "query: ",
}


def praefix_fuer(modell: str) -> str:
    """Der Anfrage-Präfix eines Modells — leer, wenn keiner nötig oder unbekannt.

    Ein unbekanntes Modell bekommt KEINEN Präfix und wird beim Start gemeldet
    (`offene_meldungen`). Hart abzubrechen wäre falsch: Wer ein eigenes Modell
    einhängt, soll das können — er soll es nur nicht unbemerkt tun.
    """
    return QUERY_PRAEFIX.get(modell, "")


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


def pruefe_praefix(settings: EmbeddingSettings) -> str | None:
    """Meldet ein Modell, für das keine Präfix-Entscheidung getroffen wurde.

    Ein Modell, das einen Anfrage-Präfix verlangt und keinen bekommt, liefert
    schlechtere Treffer — ohne Fehler, ohne Warnung. Umgekehrt schadet ein
    Präfix, den das Modell nicht kennt. Beides ist von aussen nicht zu sehen,
    deshalb wird die fehlende Entscheidung hier sichtbar gemacht.
    """
    laeuft = aktives_modell(settings)
    if laeuft in QUERY_PRAEFIX:
        return None
    return (
        f"Für '{laeuft}' ist nicht entschieden, ob Anfragen einen Präfix brauchen. "
        f"Anfragen gehen ohne. Bekannte Modelle: {', '.join(sorted(QUERY_PRAEFIX))}."
    )


def offene_meldungen(settings: EmbeddingSettings) -> list[str]:
    """Alle Beanstandungen über sämtliche erhobenen Werte, in Reihenfolge von ALLE."""
    meldungen = [pruefe(k, settings) for k in ALLE]
    meldungen.append(pruefe_praefix(settings))
    return [m for m in meldungen if m is not None]
