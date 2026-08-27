# ============================================================
#  FOREMAN — tests/embeddings/test_kalibrierung.py
#  Zweck: Hält den erhobenen Vektor-Grenzwert an sein Einbettungsmodell.
#  Warum das eine eigene Datei wert ist: Ein Grenzwert, der Treffer verwirft,
#         meldet seinen Ausfall NICHT. Steht er für ein anderes Modell als das
#         laufende, liefert die Suche zu wenig — und das sieht von aussen aus wie
#         ein leerer Bestand, nicht wie ein Defekt (C-048, Bemerkung). Genau diese
#         Klasse Fehler ist zweimal aufgetreten: der Wert 0,55 war nie erhoben,
#         der Wert 0,60 wurde erhoben und lebte danach nur in einer Umgebungs-
#         variable. Beide Male sah der Quelltext unauffällig aus.
# ============================================================
from __future__ import annotations

import inspect

import pytest

from foreman.config import Settings
from foreman.embeddings.config import EmbeddingSettings, Priority
from foreman.embeddings.kalibrierung import (
    ALLE,
    ARCHIV_VEKTOR_GRENZWERT,
    QUERY_PRAEFIX,
    Kalibrierung,
    aktives_modell,
    offene_meldungen,
    praefix_fuer,
    pruefe,
    pruefe_praefix,
)


def _einstellungen(prioritaet: Priority) -> EmbeddingSettings:
    return EmbeddingSettings(_env_file=None, priority=prioritaet)  # type: ignore[arg-type]


# ──────────────────────────────────────────────────────────────────────
#  Welches Modell läuft — die Frage, die der Grenzwert beantwortet haben muss
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("prioritaet", "erwartet"),
    [
        ("ollama_first", "bge-m3"),
        ("ollama_only", "bge-m3"),
        ("st_first", "BAAI/bge-m3"),
        ("st_only", "BAAI/bge-m3"),
        ("openai_only", "text-embedding-3-small"),
        ("openai_first", "text-embedding-3-small"),
    ],
)
def test_aktives_modell_folgt_der_eingestellten_kette(prioritaet: str, erwartet: str) -> None:
    """Jeder Modus muss auf SEIN Modell zeigen.

    Ohne diesen Fall liesse sich die Zuordnung auf einen Zweig verengen — etwa
    „alles ausser openai ist bge-m3" — und die sentence-transformers-Kette
    meldete stillschweigend den falschen Namen in der Beanstandung.
    """
    assert aktives_modell(_einstellungen(prioritaet)) == erwartet  # type: ignore[arg-type]


def test_jeder_priority_modus_ist_abgedeckt() -> None:
    """AUFBAU-KONTROLLE zur Parametrierung oben.

    Kommt ein siebter Modus hinzu, ohne dass `aktives_modell` ihn kennt, fällt er
    heute in den Ollama-Zweig — und die Beanstandung nennt ein Modell, das gar
    nicht läuft. Dieser Test zwingt dazu, die Liste oben mitzuziehen.
    """
    from typing import get_args

    abgedeckt = {
        "ollama_first",
        "ollama_only",
        "st_first",
        "st_only",
        "openai_only",
        "openai_first",
    }
    assert set(get_args(Priority)) == abgedeckt


# ──────────────────────────────────────────────────────────────────────
#  Die Beanstandung — beide Fälle, und der Zwilling der nichts sagt
# ──────────────────────────────────────────────────────────────────────


def test_unbelegte_kalibrierung_meldet_sich() -> None:
    """`modell=None` heisst „nicht belegt", nicht „gilt für alle".

    Das ist der schlechtere der beiden Fälle: Ein Wert, dessen Grundlage niemand
    kennt, lässt sich nicht einmal widerlegen. Die Meldung muss deshalb sagen,
    WAS läuft und WORAUF sich der Wert beruft.
    """
    meldung = pruefe(ARCHIV_VEKTOR_GRENZWERT, _einstellungen("openai_only"))

    assert meldung is not None
    assert "nicht belegt" in meldung
    assert "text-embedding-3-small" in meldung
    assert "C-048" in meldung


def test_abweichendes_modell_nennt_beide() -> None:
    """Eine Beanstandung, die nur eines der beiden Modelle nennt, ist unbrauchbar —
    wer sie liest, weiss dann nicht, in welche Richtung er nachmessen muss."""
    kalibriert_fuer_bge = Kalibrierung(
        name="probe", wert=0.6, modell="bge-m3", datum="2026-08-24", beleg="C-048"
    )

    meldung = pruefe(kalibriert_fuer_bge, _einstellungen("openai_only"))

    assert meldung is not None
    assert "bge-m3" in meldung
    assert "text-embedding-3-small" in meldung


def test_passendes_modell_meldet_nichts() -> None:
    """AUFBAU-KONTROLLE: Die Prüfung darf nicht immer anschlagen.

    Ohne diesen Zwilling wäre eine Prüfung, die pauschal beanstandet, von einer
    wirksamen nicht zu unterscheiden — und das Startprotokoll bekäme eine Zeile,
    die man nach einer Woche überliest.
    """
    kalibriert_fuer_bge = Kalibrierung(
        name="probe", wert=0.6, modell="bge-m3", datum="2026-08-24", beleg="C-048"
    )

    assert pruefe(kalibriert_fuer_bge, _einstellungen("ollama_first")) is None


def test_offene_meldungen_sammelt_nur_beanstandungen() -> None:
    """Sammler und Einzelprüfung dürfen nicht auseinanderlaufen."""
    meldungen = offene_meldungen(_einstellungen("ollama_first"))

    einzeln = [m for m in (pruefe(k, _einstellungen("ollama_first")) for k in ALLE) if m]
    assert meldungen == einzeln


# ──────────────────────────────────────────────────────────────────────
#  Die Bindung — ohne sie beschreibt der Eintrag einen Wert, der nicht gilt
# ──────────────────────────────────────────────────────────────────────


def test_der_vorgabewert_ist_der_erhobene_wert() -> None:
    """Der Eintrag muss den Wert beschreiben, der tatsächlich wirkt.

    Bis zum 27.08.2026 lief die Instanz auf 0,60 (C-048, GROUND_TRUTH §15.10),
    während `config.py` 0,55 als Vorgabe führte und §15.8 dasselbe schrieb: Der
    gemessene Wert stand NIRGENDS im Repository, sondern allein in einer
    Umgebungsvariable. Ein Redeploy von einem anderen Rechner hätte die Messung
    stillschweigend zurückgenommen, und kein Prüflauf hätte je den Wert gesehen,
    gegen den gemessen wurde.
    """
    assert Settings(_env_file=None).archive_vector_max_distance == ARCHIV_VEKTOR_GRENZWERT.wert


def test_jede_kalibrierung_nennt_ihren_beleg() -> None:
    """Ein erhobener Wert ohne Registereintrag ist eine Behauptung.

    Datum und Belegkennung sind das, was einen erhobenen Wert von einem geratenen
    unterscheidet — fehlt eines davon, ist der Eintrag nur eine hübschere Form
    derselben nackten Zahl.
    """
    for k in ALLE:
        assert k.beleg.startswith("C-"), k.name
        assert len(k.datum) == 10 and k.datum.count("-") == 2, k.name


# ──────────────────────────────────────────────────────────────────────
#  Der Träger selbst — eine Prüfung, die niemand aufruft, prüft nichts
# ──────────────────────────────────────────────────────────────────────


def test_der_start_ruft_die_pruefung_auf() -> None:
    """Die Prüfung hängt in der Lifespan von `create_app` — nicht nur im Modul.

    Geprüft wird auf dem ANWEISUNGSBLOCK (Kommentarzeilen entfernt) und auf die
    AUSFÜHRBARE Form mit Klammern: Eine Suche über die ganze Quelle fände den
    Namen auch in dem Kommentar, der die Prüfung erklärt — und bliebe grün,
    während der Aufruf verschwunden ist.
    """
    from foreman.main import create_app

    quelle = inspect.getsource(create_app)
    anweisungen = "\n".join(z for z in quelle.splitlines() if not z.lstrip().startswith("#"))

    assert "offene_meldungen(get_embedding_settings())" in anweisungen


# ──────────────────────────────────────────────────────────────────────
#  Der Anfrage-Präfix — er hängt am Modell, nicht an einem Schalter
# ──────────────────────────────────────────────────────────────────────


def test_arctic_verlangt_den_anfrage_praefix() -> None:
    """Belegt aus der Modellkarte, nicht aus dem Gedächtnis.

    Snowflake Arctic v2.0 nennt ihn an drei Stellen: im
    Sentence-Transformers-Beispiel als `prompt_name="query"`, im
    Transformers-Beispiel als `query_prefix = 'query: '`, und
    `config_sentence_transformers.json` führt den Prompt.
    """
    assert praefix_fuer("Snowflake/snowflake-arctic-embed-l-v2.0") == "query: "
    assert praefix_fuer("Snowflake/snowflake-arctic-embed-m-v2.0") == "query: "


def test_openai_und_bge_bekommen_keinen_praefix() -> None:
    """AUFBAU-KONTROLLE: Ein Präfix, den das Modell nicht kennt, schadet ebenso.

    Ohne diesen Fall liesse sich der Präfix pauschal setzen — und dann liefe das
    heute produktive `text-embedding-3-small` schlechter, ohne dass ein Fehler
    auffiele.
    """
    assert praefix_fuer("text-embedding-3-small") == ""
    assert praefix_fuer("bge-m3") == ""
    assert praefix_fuer("BAAI/bge-m3") == ""


def test_jedes_waehlbare_modell_hat_eine_praefix_entscheidung() -> None:
    """DER TRAGENDE FALL: Was die Konfiguration auswählen kann, muss entschieden sein.

    Ein Modell ohne Eintrag bekommt stillschweigend keinen Präfix. Verlangt es
    einen, liefert es schlechtere Treffer — ohne Fehler, ohne Warnung. Dieser
    Test zwingt dazu, bei jedem neuen Vorgabemodell die Entscheidung zu treffen,
    statt sie zu vergessen.
    """
    from typing import get_args

    for prioritaet in get_args(Priority):
        modell = aktives_modell(_einstellungen(prioritaet))
        assert modell in QUERY_PRAEFIX, (
            f"Für '{modell}' (Modus {prioritaet}) ist nicht entschieden, ob Anfragen "
            "einen Präfix brauchen."
        )


def test_ein_unbekanntes_modell_wird_beim_start_gemeldet() -> None:
    """Geraten wird nicht, aber geschwiegen auch nicht.

    Wer ein eigenes Modell einhängt, soll das können — er soll nur nicht
    unbemerkt ohne Präfix fahren. Hart abzubrechen wäre Bevormundung, stumm
    weiterzulaufen wäre die stille Verschlechterung.
    """
    eigenes = EmbeddingSettings(  # type: ignore[call-arg]
        _env_file=None, priority="openai_only", openai_model="mein-eigenes-modell"
    )

    meldung = pruefe_praefix(eigenes)

    assert meldung is not None
    assert "mein-eigenes-modell" in meldung
    assert praefix_fuer("mein-eigenes-modell") == ""


def test_ein_bekanntes_modell_wird_nicht_gemeldet() -> None:
    """AUFBAU-KONTROLLE: Die Meldung darf nicht bei jedem Start erscheinen."""
    assert pruefe_praefix(_einstellungen("openai_only")) is None


def test_die_praefix_meldung_haengt_in_der_startpruefung() -> None:
    """Eine Prüfung, die niemand aufruft, prüft nichts.

    `offene_meldungen` ist die Liste, die der Start ausgibt. Stünde die
    Präfix-Prüfung daneben statt darin, bliebe sie folgenlos.

    GEPRÜFT WIRD AUF DEN WORTLAUT DER PRÄFIX-MELDUNG, nicht auf den Modellnamen:
    Der steht auch in der Kalibrierungs-Meldung („Es läuft '…'"). Die erste
    Fassung dieses Tests fragte danach — und blieb grün, als die Präfix-Prüfung
    versuchsweise ausgebaut wurde. Ein Test, der aus dem falschen Grund grün ist,
    ist schlimmer als keiner.
    """
    eigenes = EmbeddingSettings(  # type: ignore[call-arg]
        _env_file=None, priority="openai_only", openai_model="mein-eigenes-modell"
    )

    meldungen = offene_meldungen(eigenes)

    assert any("Präfix" in m for m in meldungen), meldungen
    assert any("mein-eigenes-modell" in m and "Präfix" in m for m in meldungen)
