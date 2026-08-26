# ══════════════════════════════════════════════════════════════
# FOREMAN — Das Embedding-Modell wird genau einmal geladen
# Zwei gleichzeitige Anfragen dürfen es nicht zweimal in den Speicher holen.
# ══════════════════════════════════════════════════════════════
"""Hält den einmaligen Ladevorgang des lokalen Embedding-Modells fest.

WORUM ES GEHT. `_encode_sync` läuft über `asyncio.to_thread`, also in einem
Arbeits-Thread. Treffen zwei Anfragen gleichzeitig ein, laufen zwei Threads durch
dieselbe Stelle. Ohne Sperre sehen beide „noch nicht geladen" und laden je ein
eigenes Modell.

WAS DAS KOSTET. Nicht ein falsches Ergebnis — beide Modelle rechnen gleich. Es
kostet doppelten Arbeitsspeicher und doppelte Ladezeit, bei einem
Embedding-Modell schnell einige hundert Megabyte. Auf einer Plattform mit knappem
Speicher ist das der Unterschied zwischen langsam und abgebrochen.

WIE HIER GEPRÜFT WIRD. Der teure Ladevorgang wird durch einen Zähler ersetzt, der
lange genug verweilt, dass sich die Threads sicher überlappen. Ohne diese Pause
könnte der Test auch bei fehlender Sperre zufällig grün werden — er prüfte dann
die Nebenläufigkeit gar nicht.
"""

from __future__ import annotations

import asyncio
import sys
import threading
import time
import types
from typing import Any

import pytest

from foreman.embeddings.backends import SentenceTransformersBackend


class _ModellAttrappe:
    """Steht für das geladene Modell; `encode` liefert einen Vektor je Text."""

    def encode(self, texts: list[str], **_optionen: Any) -> list[list[float]]:
        return [[0.1, 0.2, 0.3] for _ in texts]


@pytest.fixture
def zaehlender_lader(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Ersetzt den Modell-Aufbau durch einen Zähler mit spürbarer Ladezeit."""
    zustand = {"aufrufe": 0}

    def _laden(*_a: object, **_k: object) -> _ModellAttrappe:
        zustand["aufrufe"] += 1
        # Lange genug, dass ein zweiter Thread die Stelle sicher erreicht, während
        # der erste noch lädt. Ohne diese Pause liefe der Test am Fall vorbei.
        time.sleep(0.25)
        return _ModellAttrappe()

    # Ein Attrappen-Modul statt eines Patches an der echten Bibliothek: Die ist ein
    # optionaler Zusatz und muss für diesen Test weder installiert noch geladen
    # sein — geprüft wird FOREMANs Ladelogik, nicht die Bibliothek.
    modul = types.ModuleType("sentence_transformers")
    modul.SentenceTransformer = _laden  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sentence_transformers", modul)
    return zustand


async def test_zwei_gleichzeitige_anfragen_laden_das_modell_einmal(
    zaehlender_lader: dict[str, int],
) -> None:
    """Der eigentliche Fall: zwei Aufrufe, ein Ladevorgang."""
    provider = SentenceTransformersBackend(model_name="attrappe", device="cpu")

    ergebnisse = await asyncio.gather(
        provider.embed_batch(["erster Text"], timeout_s=5.0),
        provider.embed_batch(["zweiter Text"], timeout_s=5.0),
    )

    assert zaehlender_lader["aufrufe"] == 1, (
        f"❌ Das Modell wurde {zaehlender_lader['aufrufe']} mal geladen. Zwei gleichzeitige "
        "Anfragen laufen durch dieselbe Stelle; ohne Sperre sehen beide einen leeren "
        "Platz und laden je ein eigenes Modell."
    )
    assert all(len(vektoren) == 1 for vektoren in ergebnisse), (
        "Beide Anfragen brauchen ihr Ergebnis."
    )


async def test_der_aufbau_traegt(zaehlender_lader: dict[str, int]) -> None:
    """Zwilling: belegt, dass der Zähler überhaupt hochzählt.

    Ohne ihn wäre die Zusicherung oben auch dann erfüllt, wenn der Ladevorgang nie
    stattfände — etwa weil die Attrappe an der falschen Stelle sitzt. Dann prüfte
    `aufrufe == 1` nichts und wäre trotzdem grün, sobald man es auf `== 0` änderte.
    """
    provider = SentenceTransformersBackend(model_name="attrappe", device="cpu")

    await provider.embed_batch(["ein Text"], timeout_s=5.0)

    assert zaehlender_lader["aufrufe"] == 1


async def test_weitere_anfragen_laden_nicht_erneut(zaehlender_lader: dict[str, int]) -> None:
    """Die Sperre darf den späteren Weg nicht verteuern — geladen bleibt geladen."""
    provider = SentenceTransformersBackend(model_name="attrappe", device="cpu")

    await provider.embed_batch(["erster"], timeout_s=5.0)
    await provider.embed_batch(["zweiter"], timeout_s=5.0)
    await provider.embed_batch(["dritter"], timeout_s=5.0)

    assert zaehlender_lader["aufrufe"] == 1


def test_das_laden_haelt_auch_bei_vielen_threads(zaehlender_lader: dict[str, int]) -> None:
    """Härtere Fassung: acht Threads gleichzeitig auf denselben Anbieter.

    Zwei Aufrufe treffen sich womöglich knapp; acht treffen sich sicher. Der Test
    greift direkt auf den blockierenden Pfad zu, ohne den Umweg über die
    Ereignisschleife.
    """
    provider = SentenceTransformersBackend(model_name="attrappe", device="cpu")
    start = threading.Barrier(8)

    def _arbeiten() -> None:
        start.wait()
        provider._encode_sync(["text"])

    threads = [threading.Thread(target=_arbeiten) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert zaehlender_lader["aufrufe"] == 1
