# ============================================================
#  FOREMAN — tests/archive/test_such_kennzahlen.py
#  Zweck: Hält die zwei Kennzahlen der Archiv-Suche fest — Dauer des vollen
#         Aufrufs und Rückfall auf den reinen Volltext.
#  Warum sie eine eigene Datei wert sind: Beide beschreiben Ausfälle, die NICHT
#         werfen. Am 28.08.2026 lief die Suche wochenlang mit 5,5 s statt 0,15 s,
#         ohne dass etwas rot wurde (C-095); und ein Ausfall des Einbettungs-
#         Backends degradiert die Suche still auf Volltext — die Trefferliste
#         sieht danach vollständig aus und hat ihren bedeutungsbasierten Teil
#         verloren. Wer diese Kennzahlen still verliert, verliert die einzige
#         Spur, die es von beidem gibt.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import pytest

from foreman.archive import search as archiv_suche
from foreman.notes import search as notiz_suche
from foreman.observability import metrics


def _summe(histogramm: Any) -> tuple[int, float]:
    """Anzahl und Summe eines Histogramms ohne Labels — aus der Registry gelesen."""
    anzahl = summe = 0.0
    for probe in histogramm.collect()[0].samples:
        if probe.name.endswith("_count"):
            anzahl = probe.value
        elif probe.name.endswith("_sum"):
            summe = probe.value
    return int(anzahl), summe


def _zaehler(counter: Any) -> float:
    for probe in counter.collect()[0].samples:
        if probe.name.endswith("_total"):
            return float(probe.value)
    return 0.0


# ──────────────────────────────────────────────────────────────────────
#  Die Dauer — sie muss den GANZEN Aufruf umschliessen
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ein_suchaufruf_wird_in_der_dauer_gezaehlt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Normalfall: Ein Aufruf, ein Eintrag."""
    vorher, _ = _summe(metrics.ARCHIVE_SEARCH_LATENCY)

    async def kein_ablauf(*a: object, **k: object) -> list[Any]:
        return []

    monkeypatch.setattr(archiv_suche, "_suche_archiv", kein_ablauf)
    await archiv_suche.search_archive(None, None, "egal", max_distance=0.75)  # type: ignore[arg-type]

    nachher, _ = _summe(metrics.ARCHIVE_SEARCH_LATENCY)
    assert nachher == vorher + 1


@pytest.mark.asyncio
async def test_auch_ein_gescheiterter_aufruf_wird_gezaehlt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DER FALL, DEN MAN LEICHT VERLIERT.

    Eine Suche, die nach zehn Sekunden in einen Fehler läuft, ist der
    interessanteste Betriebsbefund überhaupt — und fiele aus der Verteilung,
    wenn die Zeitnahme nur den Erfolgsfall einträgt. Dann sähe die Kennzahl umso
    gesünder aus, je öfter die Suche scheitert.
    """
    vorher, _ = _summe(metrics.ARCHIVE_SEARCH_LATENCY)

    async def scheitert(*a: object, **k: object) -> list[Any]:
        raise RuntimeError("Datenbank weg")

    monkeypatch.setattr(archiv_suche, "_suche_archiv", scheitert)
    with pytest.raises(RuntimeError):
        await archiv_suche.search_archive(None, None, "egal", max_distance=0.75)  # type: ignore[arg-type]

    nachher, _ = _summe(metrics.ARCHIVE_SEARCH_LATENCY)
    assert nachher == vorher + 1, (
        "❌ Der gescheiterte Aufruf fehlt in der Dauer-Kennzahl. Damit sieht die "
        "Verteilung umso besser aus, je oefter die Suche scheitert."
    )


@pytest.mark.asyncio
async def test_die_gemessene_zeit_umschliesst_den_ablauf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AUFBAU-KONTROLLE: Gemessen werden muss der Ablauf, nicht die leere Hülle.

    Ohne diesen Fall bliebe die Kennzahl auch dann grün, wenn die Zeitnahme
    versehentlich um nichts läge — sie zählte Aufrufe und meldete Dauer null.
    """
    import asyncio

    _, summe_vorher = _summe(metrics.ARCHIVE_SEARCH_LATENCY)

    async def dauert(*a: object, **k: object) -> list[Any]:
        await asyncio.sleep(0.05)
        return []

    monkeypatch.setattr(archiv_suche, "_suche_archiv", dauert)
    await archiv_suche.search_archive(None, None, "egal", max_distance=0.75)  # type: ignore[arg-type]

    _, summe_nachher = _summe(metrics.ARCHIVE_SEARCH_LATENCY)
    assert summe_nachher - summe_vorher >= 0.04, (
        "❌ Die eingetragene Dauer ist kleiner als der Ablauf, den sie umschliessen "
        "soll — die Zeitnahme liegt an der falschen Stelle."
    )


# ──────────────────────────────────────────────────────────────────────
#  Der Rückfall auf den Volltext — der stille Ausfall
# ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_der_rueckfall_auf_volltext_wird_gezaehlt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fällt das Einbettungs-Backend aus, muss der Zähler steigen.

    Er ist die einzige abfragbare Spur davon. Ohne ihn stünde der Ausfall nur
    als Warnung im Protokoll — an einer Stelle, die niemand regelmässig liest.
    """
    from foreman.embeddings.errors import ProviderUnavailable

    vorher = _zaehler(metrics.ARCHIVE_DEGRADIERT)

    class KaputterAnbieter:
        async def embed(self, texts: Sequence[str], **k: object) -> list[list[float]]:
            raise ProviderUnavailable("❌ nicht verfügbar", attempted=("test",))

    async def volltext_allein(*a: object, **k: object) -> list[Any]:
        return []

    monkeypatch.setattr(notiz_suche, "hybrid_search_notes", volltext_allein)
    await notiz_suche.embed_and_search_hybrid(
        KaputterAnbieter(),  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        "egal",
        max_distance=0.75,
    )

    assert _zaehler(metrics.ARCHIVE_DEGRADIERT) == vorher + 1


@pytest.mark.asyncio
async def test_die_gesunde_suche_zaehlt_nicht_mit(monkeypatch: pytest.MonkeyPatch) -> None:
    """AUFBAU-KONTROLLE zum Zähler: Er darf nicht bei jeder Suche steigen.

    Ein Zähler, der immer steigt, ist von einem wirksamen nicht zu
    unterscheiden — und ein Alarm darauf würde nach einer Woche abgeschaltet.
    """
    vorher = _zaehler(metrics.ARCHIVE_DEGRADIERT)

    class HeilerAnbieter:
        async def embed(self, texts: Sequence[str], **k: object) -> list[list[float]]:
            return [[0.1] * 1024 for _ in texts]

    async def volltext(*a: object, **k: object) -> list[Any]:
        return []

    monkeypatch.setattr(notiz_suche, "hybrid_search_notes", volltext)
    await notiz_suche.embed_and_search_hybrid(
        HeilerAnbieter(),  # type: ignore[arg-type]
        None,  # type: ignore[arg-type]
        "egal",
        max_distance=0.75,
    )

    assert _zaehler(metrics.ARCHIVE_DEGRADIERT) == vorher
