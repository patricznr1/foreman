# ============================================================
#  FOREMAN — tests/embeddings/test_provider.py
#  Zweck: Provider-Orchestrierung (F-SEM, Baustein 1) gegen Mock-Backends —
#         Batch-Garantie, L2-Normalisierung, Dimension-Check, Priority/Fallback,
#         Metriken. Kein Netz, kein echter Embedding-Call.
# ============================================================
from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Protocol

import pytest

from foreman.embeddings import (
    DimensionMismatch,
    EmbeddingProvider,
    EmbeddingSettings,
    LocalEmbeddingProvider,
    ProviderUnavailable,
)
from foreman.observability.metrics import REGISTRY


class _CountingBackend(Protocol):
    """Strukturelle Sicht auf das Mock-Backend (zählt Batch-Aufrufe über `calls`)."""

    name: str
    calls: int

    async def embed_batch(self, texts: Sequence[str], *, timeout_s: float) -> list[list[float]]: ...


MakeProvider = Callable[..., LocalEmbeddingProvider]
MakeBackend = Callable[..., _CountingBackend]


def _sample(name: str, labels: dict[str, str]) -> float:
    """Aktueller Wert eines Prometheus-Counters (0.0, falls noch nicht gesetzt)."""
    value = REGISTRY.get_sample_value(name, labels)
    return value if value is not None else 0.0


async def test_embed_leere_eingabe_ohne_backend_call(
    make_provider: MakeProvider, make_embed_backend: MakeBackend
) -> None:
    backend = make_embed_backend("ollama")
    provider = make_provider(backends=[backend], priority="ollama_only")
    assert await provider.embed([]) == []
    assert backend.calls == 0


async def test_embed_batch_ein_call_ein_vektor_pro_text(
    make_provider: MakeProvider, make_embed_backend: MakeBackend
) -> None:
    backend = make_embed_backend("ollama", dim=1024)
    provider = make_provider(backends=[backend], priority="ollama_only", dimension=1024)
    result = await provider.embed(["a", "b", "c"])
    assert len(result) == 3
    assert all(len(vec) == 1024 for vec in result)
    assert backend.calls == 1  # EIN Batch-Call, nicht pro Text


async def test_embed_l2_normalisiert_auf_einheitslaenge(
    make_provider: MakeProvider, make_embed_backend: MakeBackend
) -> None:
    # Unnormalisierter Vektor [3,4,0,…] (Norm 5) → Provider normiert auf Länge 1.
    raw = [3.0, 4.0, *([0.0] * 1022)]
    backend = make_embed_backend("ollama", vectors=[raw])
    provider = make_provider(
        backends=[backend], priority="ollama_only", dimension=1024, normalize=True
    )
    [vec] = await provider.embed(["x"])
    assert math.sqrt(sum(c * c for c in vec)) == pytest.approx(1.0)
    assert vec[0] == pytest.approx(0.6)  # 3/5
    assert vec[1] == pytest.approx(0.8)  # 4/5


async def test_embed_ohne_normalisierung_bleibt_roh(
    make_provider: MakeProvider, make_embed_backend: MakeBackend
) -> None:
    raw = [3.0, 4.0, *([0.0] * 1022)]
    backend = make_embed_backend("ollama", vectors=[raw])
    provider = make_provider(backends=[backend], priority="ollama_only", normalize=False)
    [vec] = await provider.embed(["x"])
    assert vec[0] == pytest.approx(3.0)
    assert vec[1] == pytest.approx(4.0)


async def test_embed_nullvektor_bleibt_bei_normalisierung_stabil(
    make_provider: MakeProvider, make_embed_backend: MakeBackend
) -> None:
    # Ein reiner Nullvektor (Norm 0) darf nicht durch Division-durch-Null brechen.
    backend = make_embed_backend("ollama", vectors=[[0.0] * 1024])
    provider = make_provider(backends=[backend], priority="ollama_only", normalize=True)
    [vec] = await provider.embed(["x"])
    assert all(c == 0.0 for c in vec)


async def test_embed_falsche_dimension_wirft(
    make_provider: MakeProvider, make_embed_backend: MakeBackend
) -> None:
    backend = make_embed_backend("ollama", dim=512)  # zu kurz für vector(1024)
    provider = make_provider(backends=[backend], priority="ollama_only", dimension=1024)
    with pytest.raises(DimensionMismatch):
        await provider.embed(["x"])


async def test_embed_fallback_auf_zweites_backend(
    make_provider: MakeProvider, make_embed_backend: MakeBackend
) -> None:
    primary = make_embed_backend("ollama", fail=True)
    secondary = make_embed_backend("sentence_transformers", dim=1024)
    provider = make_provider(backends=[primary, secondary], priority="ollama_first", dimension=1024)
    result = await provider.embed(["x"])
    assert len(result) == 1
    assert primary.calls == 1
    assert secondary.calls == 1  # Fallback hat gegriffen


async def test_embed_only_modus_kein_fallback(
    make_provider: MakeProvider, make_embed_backend: MakeBackend
) -> None:
    primary = make_embed_backend("ollama", fail=True)
    secondary = make_embed_backend("sentence_transformers", dim=1024)
    provider = make_provider(backends=[primary, secondary], priority="ollama_only")
    with pytest.raises(ProviderUnavailable):
        await provider.embed(["x"])
    assert secondary.calls == 0  # ollama_only → kein ST-Fallback


async def test_embed_zaehlt_erfolgs_metrik(
    make_provider: MakeProvider, make_embed_backend: MakeBackend
) -> None:
    backend = make_embed_backend("ollama", dim=1024)
    provider = make_provider(backends=[backend], priority="ollama_only", dimension=1024)
    ok_before = _sample("foreman_embed_requests_total", {"backend": "ollama", "result": "ok"})
    texts_before = _sample("foreman_embed_texts_total", {"backend": "ollama"})
    await provider.embed(["a", "b"])
    ok_after = _sample("foreman_embed_requests_total", {"backend": "ollama", "result": "ok"})
    texts_after = _sample("foreman_embed_texts_total", {"backend": "ollama"})
    assert ok_after == ok_before + 1
    assert texts_after == texts_before + 2


async def test_embed_zaehlt_fehler_metrik(
    make_provider: MakeProvider, make_embed_backend: MakeBackend
) -> None:
    backend = make_embed_backend("ollama", fail=True)
    provider = make_provider(backends=[backend], priority="ollama_only")
    err_before = _sample("foreman_embed_requests_total", {"backend": "ollama", "result": "error"})
    with pytest.raises(ProviderUnavailable):
        await provider.embed(["x"])
    err_after = _sample("foreman_embed_requests_total", {"backend": "ollama", "result": "error"})
    assert err_after == err_before + 1


def test_provider_erfuellt_protokoll(
    make_provider: MakeProvider, make_embed_backend: MakeBackend
) -> None:
    provider = make_provider(backends=[make_embed_backend("ollama")], priority="ollama_only")
    assert isinstance(provider, EmbeddingProvider)  # runtime_checkable


@pytest.mark.parametrize("priority", ["ollama_first", "st_first", "ollama_only", "st_only"])
def test_from_settings_baut_provider_je_modus(priority: str) -> None:
    # Baut die für den Priority-Modus nötigen Backends OHNE echten Call (lazy/injizierbar).
    settings = EmbeddingSettings(_env_file=None, priority=priority)  # type: ignore[arg-type]
    provider = LocalEmbeddingProvider.from_settings(settings)
    assert isinstance(provider, EmbeddingProvider)


async def test_embed_falsche_anzahl_vektoren_wirft(
    make_provider: MakeProvider, make_embed_backend: MakeBackend
) -> None:
    # Backend liefert 2 Vektoren für 1 Text → Cardinality-Vertrag (§15.1) verletzt.
    backend = make_embed_backend("ollama", vectors=[[0.1] * 1024, [0.2] * 1024])
    provider = make_provider(backends=[backend], priority="ollama_only", dimension=1024)
    with pytest.raises(ProviderUnavailable):
        await provider.embed(["nur ein text"])


# ──────────────────────────────────────────────────────────────────────
#  Der Anfrage-Präfix — kommt er am Backend an?
# ──────────────────────────────────────────────────────────────────────


class _MitschreibendesBackend:
    """Merkt sich, welche Texte es bekommen hat — darum geht es hier."""

    name = "ollama"

    def __init__(self) -> None:
        self.gesehen: list[str] = []

    async def embed_batch(self, texts: Sequence[str], *, timeout_s: float) -> list[list[float]]:
        self.gesehen.extend(texts)
        return [[1.0] + [0.0] * 1023 for _ in texts]


def _mit_praefix(praefix: str) -> tuple[LocalEmbeddingProvider, _MitschreibendesBackend]:
    backend = _MitschreibendesBackend()
    provider = LocalEmbeddingProvider(
        backends=[backend],  # type: ignore[list-item]
        priority="ollama_only",
        dimension=1024,
        normalize=True,
        timeout_s=30.0,
        query_praefix=praefix,
    )
    return provider, backend


async def test_eine_anfrage_bekommt_den_praefix() -> None:
    """Snowflake Arctic v2.0 verlangt ihn auf der Anfrageseite.

    Geprüft wird, was das BACKEND sieht — nicht, was der Provider vorhat. Ein
    Präfix, der unterwegs verlorengeht, wäre von einem fehlenden nicht zu
    unterscheiden.
    """
    provider, backend = _mit_praefix("query: ")

    await provider.embed(["Lager laeuft heiss"], mode="query")

    assert backend.gesehen == ["query: Lager laeuft heiss"]


async def test_ein_dokument_bekommt_ihn_nicht() -> None:
    """AUFBAU-KONTROLLE: Der Präfix gehört NUR an die Anfrage.

    Auf beiden Seiten gesetzt wäre er wirkungslos bis schädlich — das Modell ist
    darauf trainiert, dass Anfrage und Dokument sich unterscheiden. Ohne diesen
    Fall liesse sich der Präfix pauschal voranstellen, und die Suche sähe
    weiterhin plausibel aus.
    """
    provider, backend = _mit_praefix("query: ")

    await provider.embed(["Lager laeuft heiss"], mode="passage")

    assert backend.gesehen == ["Lager laeuft heiss"]


async def test_ohne_modus_gilt_dokument() -> None:
    """Die sichere Richtung ist die Vorgabe.

    Ein vergessener Modus beim SCHREIBEN ist folgenlos; beim SUCHEN nicht. Die
    Vorgabe steht deshalb auf `passage`, und der Suchpfad nennt `query`
    ausdrücklich.
    """
    provider, backend = _mit_praefix("query: ")

    await provider.embed(["Lager laeuft heiss"])

    assert backend.gesehen == ["Lager laeuft heiss"]


async def test_ohne_praefix_bleibt_der_text_unberuehrt() -> None:
    """Das ist der heutige Produktivfall: `text-embedding-3-small` kennt keinen.

    Ohne diesen Fall könnte die Umstellung einen leeren Präfix als Leerzeichen
    voranstellen — eine Änderung an jedem einzelnen Vektor, ohne dass jemand
    danach gefragt hätte.
    """
    provider, backend = _mit_praefix("")

    await provider.embed(["Lager laeuft heiss"], mode="query")

    assert backend.gesehen == ["Lager laeuft heiss"]


def test_der_suchpfad_nennt_den_anfrage_modus() -> None:
    """Eine Möglichkeit, die niemand nutzt, wirkt nicht.

    Geprüft wird auf dem ANWEISUNGSBLOCK (Kommentarzeilen entfernt) und auf die
    ausführbare Form: Der Name `mode="query"` steht sonst auch in dem Kommentar,
    der ihn erklärt, und eine Suche über die ganze Datei bliebe grün, während der
    Aufruf ihn nicht mehr übergibt.
    """
    import inspect

    from foreman.notes import search as notiz_suche

    quelle = inspect.getsource(notiz_suche)
    anweisungen = "\n".join(z for z in quelle.splitlines() if not z.lstrip().startswith("#"))

    assert anweisungen.count('mode="query"') == 2, "beide Suchpfade müssen den Modus nennen"
    # Der Schreibpfad darf ihn NICHT nennen — sonst bekäme jedes Dokument den Präfix.
    assert "mode=" not in inspect.getsource(
        __import__("foreman.embeddings.backfill", fromlist=["x"])
    )
