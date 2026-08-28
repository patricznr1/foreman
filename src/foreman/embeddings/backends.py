# ============================================================
#  FOREMAN — embeddings/backends.py
#  Zweck: Backend-Auflösung/Routing der Embedding-Schicht (F-SEM) — lokales
#         Ollama-Backend (bge-m3 über httpx) + sentence-transformers-Alternative,
#         plus die Prioritäts-/Fallback-Logik. DIES ist die EINZIGE Datei, die die
#         konkreten Embedding-Libraries berührt (sentence-transformers LAZY). Kein
#         Library-Typ verlässt dieses Modul — jede Fremd-Ausnahme wird in einen
#         typisierten Embedding-Fehler übersetzt (harte Architektur-Grenze,
#         analog §13.2 Gateway-Backends).
#  Architektur-Einordnung: Schicht 2, hinter der EmbeddingProvider-Abstraktion.
#         Beide Backends sind lokal; Async durchgängig; reine Routing-Funktionen
#         seedbar (Tests ohne Netz/Modell).
#  Konvention (§6): deutsche Kommentare, keine PII/keine Notiz-Texte/keine Vektoren
#         in Logs/Fehlern.
# ============================================================
from __future__ import annotations

import asyncio
import os
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final, Protocol, runtime_checkable

import httpx

from foreman.embeddings.config import OLLAMA_BACKEND, OPENAI_BACKEND, ST_BACKEND, Priority
from foreman.embeddings.errors import EmbeddingError, EmbeddingTimeout, ProviderUnavailable
from foreman.logging_setup import OK, get_logger

logger = get_logger("foreman.embeddings.backends")

# Rohe (un-normalisierte) Vektoren, wie ein Backend sie liefert — vor Dim-Check/
# L2-Normalisierung im Provider.
RawVector = list[float]


@runtime_checkable
class EmbeddingBackend(Protocol):
    """Ein konkretes Embedding-Backend (Ollama/sentence-transformers).

    Vertrag: ein Batch von Texten → ein Roh-Vektor je Text (gleiche Reihenfolge).
    Nicht erreichbar/Timeout → typisierter Embedding-Fehler (nie Library-Ausnahme).
    """

    name: str

    async def embed_batch(self, texts: Sequence[str], *, timeout_s: float) -> list[RawVector]: ...


# Priority-Modus → Reihenfolge der Backend-Namen (GROUND_TRUTH §15).
# Die openai-Modi tragen bewusst KEINEN lokalen Fallback (Cloud-Demo-Image ohne
# Ollama/sentence-transformers) — beide enthalten nur das Cloud-Backend (§15.2).
_CHAINS: dict[str, tuple[str, ...]] = {
    "ollama_first": (OLLAMA_BACKEND, ST_BACKEND),
    "st_first": (ST_BACKEND, OLLAMA_BACKEND),
    "ollama_only": (OLLAMA_BACKEND,),
    "st_only": (ST_BACKEND,),
    "openai_only": (OPENAI_BACKEND,),
    "openai_first": (OPENAI_BACKEND,),
}


def resolve_chain(priority: Priority) -> tuple[str, ...]:
    """Liefert die Backend-Reihenfolge für einen Priority-Modus (rein, seedbar)."""
    return _CHAINS[priority]


async def run_with_fallback(
    chain: Sequence[EmbeddingBackend],
    texts: Sequence[str],
    *,
    timeout_s: float,
) -> tuple[list[RawVector], EmbeddingBackend]:
    """Versucht die Backends in Reihenfolge; fällt bei Nicht-Erreichbarkeit/Timeout
    auf das nächste zurück.

    Rückgabe: (Roh-Vektoren, genutztes Backend). Ist die Kette erschöpft (oder
    leer/`*_only` mit verbotenem Fallback), wird ein sauberer `ProviderUnavailable`
    mit der Liste der versuchten Backends geworfen.
    """
    attempted: list[str] = []
    last_exc: EmbeddingError | None = None
    for backend in chain:
        attempted.append(backend.name)
        try:
            vectors = await backend.embed_batch(texts, timeout_s=timeout_s)
        except (ProviderUnavailable, EmbeddingTimeout) as exc:
            last_exc = exc
            continue
        return vectors, backend
    raise ProviderUnavailable(
        f"❌ Kein erlaubtes Embedding-Backend erreichbar (versucht: {attempted})",
        attempted=attempted,
    ) from last_exc


def _coerce_vectors(raw: Any, *, expected_count: int) -> list[RawVector]:
    """Mappt eine rohe Backend-Antwort defensiv auf eine Liste von Float-Vektoren.

    `raw` ist eine Liste von Zahlen-Listen (Embeddings). Alles andere ist eine
    unverwertbare Antwort → ProviderUnavailable (keine Library-Ausnahme nach oben).
    """
    if not isinstance(raw, list) or len(raw) != expected_count:
        raise ProviderUnavailable(
            f"❌ Embedding-Backend lieferte eine unverwertbare Antwort "
            f"(erwartet {expected_count} Vektoren)."
        )
    vectors: list[RawVector] = []
    for row in raw:
        if not isinstance(row, list):
            raise ProviderUnavailable("❌ Embedding-Backend lieferte einen unverwertbaren Vektor.")
        try:
            vectors.append([float(value) for value in row])
        except (TypeError, ValueError) as exc:
            # Architektur-Grenze: nicht-numerische Werte dürfen nicht als rohe
            # ValueError/TypeError aus der Embedding-Schicht lecken.
            raise ProviderUnavailable(
                "❌ Embedding-Backend lieferte nicht-numerische Vektor-Werte."
            ) from exc
    return vectors


class OllamaBackend:
    """Embedding-Backend über Ollama (`POST /api/embed`, Batch via `input`).

    Übersetzt jede httpx-Ausnahme in einen typisierten Embedding-Fehler — nichts
    Library-Spezifisches verlässt das Modul. Ein `httpx.AsyncClient` kann injiziert
    werden (Tests gegen MockTransport, ohne echtes Ollama)."""

    name = OLLAMA_BACKEND

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        self._base_url = base_url
        self._client = client

    async def embed_batch(self, texts: Sequence[str], *, timeout_s: float) -> list[RawVector]:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(base_url=self._base_url, timeout=timeout_s)
        try:
            response = await client.post(
                "/api/embed",
                json={"model": self.model, "input": list(texts)},
                timeout=timeout_s,
            )
            response.raise_for_status()
            data: Any = response.json()
        except httpx.TimeoutException as exc:
            raise EmbeddingTimeout(
                f"❌ Zeitüberschreitung beim Embedding-Backend '{self.name}' (>{timeout_s}s)"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            # ValueError deckt JSONDecodeError (200 mit nicht-JSON-Body) ab — sonst
            # verließe eine rohe Library-Ausnahme die Architektur-Grenze (§15.2).
            raise ProviderUnavailable(
                f"❌ Embedding-Backend '{self.name}' nicht erreichbar", attempted=(self.name,)
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

        embeddings = data.get("embeddings") if isinstance(data, dict) else None
        return _coerce_vectors(embeddings, expected_count=len(texts))


def _extract_openai_embeddings(data: Any, *, expected_count: int) -> Any:
    """Zieht die Embeddings aus einer OpenAI-`/embeddings`-Antwort und stellt die
    INPUT-Reihenfolge über `data[].index` wieder her.

    OpenAI darf die Einträge in beliebiger Reihenfolge liefern; die Vertrags-Garantie
    „ein Vektor je Text in Eingabe-Reihenfolge" stellt die Sortierung über `index`
    sicher. Defensiv: jede unerwartete Form (kein `data`-Array, fehlendes `index`/
    `embedding`) wird zu `ProviderUnavailable` — keine Library-Ausnahme nach oben.
    Die finale Form-/Längen-/Typprüfung übernimmt anschließend `_coerce_vectors`.
    """
    items = data.get("data") if isinstance(data, dict) else None
    if not isinstance(items, list):
        raise ProviderUnavailable(
            "❌ Embedding-Backend 'openai' lieferte eine unverwertbare Antwort "
            "(kein 'data'-Array).",
            attempted=(OPENAI_BACKEND,),
        )
    try:
        ordered = sorted(items, key=lambda item: item["index"])
        indices = [item["index"] for item in ordered]
        embeddings = [item["embedding"] for item in ordered]
    except (KeyError, TypeError) as exc:
        raise ProviderUnavailable(
            "❌ Embedding-Backend 'openai' lieferte eine unverwertbare Antwort.",
            attempted=(OPENAI_BACKEND,),
        ) from exc
    # `data[].index` muss eine dichte 0..n-1-Permutation sein — doppelte/lückenhafte/
    # nicht-ganzzahlige Indizes (gleiche Anzahl, falsche Zuordnung) würden sonst still
    # durchrutschen und ein Embedding dem falschen Eingabetext zuordnen.
    if indices != list(range(expected_count)):
        raise ProviderUnavailable(
            "❌ Embedding-Backend 'openai' lieferte inkonsistente data[].index-Werte.",
            attempted=(OPENAI_BACKEND,),
        )
    return embeddings


class OpenAIBackend:
    """Embedding-Backend über die OpenAI-API (`POST {base_url}/embeddings`).

    Optionaler Cloud-Pfad (Demo, US-Drittland — §15.2/§18): `text-embedding-3-small`
    mit `dimensions=1024` passt OHNE Migration in `worker_notes.embedding`
    (`vector(1024)`). Reines httpx wie `OllamaBackend` — KEIN openai-SDK; nichts
    Library-Spezifisches verlässt das Modul, jede httpx-Ausnahme wird in einen
    typisierten Embedding-Fehler übersetzt. Der API-Key wird NIE geloggt oder in
    Fehlern wiedergegeben (§8/§15.7). Ein `httpx.AsyncClient` kann injiziert werden
    (Tests gegen MockTransport, ohne Netz)."""

    name = OPENAI_BACKEND

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        dimensions: int,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self.model = model
        # Vollständiger Endpoint: base_url trägt einen Pfad (`/v1`) → ein relativer
        # httpx-base_url-Join würde das `/v1` verschlucken, darum explizit bauen.
        self._endpoint = f"{base_url.rstrip('/')}/embeddings"
        self._api_key = api_key
        self._dimensions = dimensions
        self._client = client

    async def embed_batch(self, texts: Sequence[str], *, timeout_s: float) -> list[RawVector]:
        owns_client = self._client is None
        client = self._client or httpx.AsyncClient(timeout=timeout_s)
        try:
            response = await client.post(
                self._endpoint,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self.model,
                    "input": list(texts),
                    "dimensions": self._dimensions,
                    "encoding_format": "float",
                },
                timeout=timeout_s,
            )
            response.raise_for_status()
            data: Any = response.json()
        except httpx.TimeoutException as exc:
            raise EmbeddingTimeout(
                f"❌ Zeitüberschreitung beim Embedding-Backend '{self.name}' (>{timeout_s}s)"
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            # ValueError deckt JSONDecodeError (200 mit nicht-JSON-Body) ab — sonst
            # verließe eine rohe Library-Ausnahme die Architektur-Grenze (§15.2).
            raise ProviderUnavailable(
                f"❌ Embedding-Backend '{self.name}' nicht erreichbar", attempted=(self.name,)
            ) from exc
        finally:
            if owns_client:
                await client.aclose()

        return _coerce_vectors(
            _extract_openai_embeddings(data, expected_count=len(texts)),
            expected_count=len(texts),
        )


# Obergrenze der Rechen-Threads des lokalen Einbettungsmodells.
#
# WARUM ES DIESE GRENZE ÜBERHAUPT BRAUCHT: torch bemisst seine Threadzahl an
# `os.cpu_count()` — und das meldet im Behälter die Kerne des WIRTS, nicht die
# Zuteilung. Auf der Betriebsmaschine sind das 48 gegen eine Quote von 24.
#
# Der Schaden ist nicht Überlastung, sondern Absprache: Eine einzelne kurze
# Anfrage ist eine winzige Rechnung. Je mehr Threads sich darüber abstimmen,
# desto mehr Zeit geht für die Abstimmung drauf. Gemessen am 28.08.2026 im
# Betriebsbehälter, Median je Anfrage:
#
#     48 Threads → 5,340 s     16 Threads → 0,082 s
#     24 Threads → 0,193 s      8 Threads → 0,087 s
#      4 Threads → 0,113 s      1 Thread  → 0,322 s
#
# Faktor 65 zwischen Vorgabe und Bestwert. Der Wert 16 ist der gemessene
# Umschlagpunkt: Darunter fehlt Rechenkraft, darüber frisst die Abstimmung sie
# wieder auf. Er wird zusätzlich an der Zuteilung gedeckelt — auf einem kleinen
# Behälter sind 16 Threads nicht vorhanden.
#
# ERGEBNISSE ÄNDERT DIE ZAHL NICHT über Gleitkomma-Rauschen hinaus: gemessen
# 2·10⁻⁷ Unterschied je Komponente, Kosinus 1,000000000 zwischen 48 und 16
# Threads. Sie ist eine Geschwindigkeits-, keine Genauigkeitsfrage.
_THREAD_OBERGRENZE: Final = 16


def _zugeteilte_kerne() -> int:
    """Kerne, die dem Prozess wirklich zustehen — nicht die des Wirts.

    Reihenfolge nach Verlässlichkeit: cgroup-Quote (der Behälter), dann die
    Prozess-Affinität, dann `os.cpu_count()` als letzter Ausweg. Ist nichts
    davon lesbar, bleibt 1 — lieber zu wenig als die 48 des Wirts.
    """
    for pfad, teiler in (
        ("/sys/fs/cgroup/cpu.max", None),
        ("/sys/fs/cgroup/cpu/cpu.cfs_quota_us", "/sys/fs/cgroup/cpu/cpu.cfs_period_us"),
    ):
        try:
            roh = Path(pfad).read_text().split()
            quote = roh[0]
            if quote in ("max", "-1"):
                break
            periode = float(roh[1]) if teiler is None else float(Path(teiler).read_text())
            return max(1, int(float(quote) / periode))
        except (OSError, ValueError, IndexError):
            continue
    # `sched_getaffinity` gibt es nur auf Linux — über `getattr` geholt, damit die
    # Prüfung auch für Windows durchgeht, wo entwickelt wird.
    affinitaet = getattr(os, "sched_getaffinity", None)
    if affinitaet is not None:
        return max(1, len(affinitaet(0)))
    return max(1, os.cpu_count() or 1)


def _ziel_threadzahl() -> int:
    """Die Zahl, auf die begrenzt wird — getrennt von `_begrenze_threads`, damit sie
    ohne installiertes torch prüfbar ist."""
    return max(1, min(_THREAD_OBERGRENZE, _zugeteilte_kerne()))


def _begrenze_threads() -> None:
    """Setzt die Threadzahl vor dem ersten Laden. Wirkt prozessweit — deshalb hier
    und nicht beim Import: Wer das Backend nie benutzt, soll auch nichts umstellen.

    OHNE torch passiert nichts, und das ist Absicht: Die Begrenzung ist eine
    Geschwindigkeitsfrage, keine Voraussetzung. Sie darf den Einbettungspfad
    nicht zum Scheitern bringen — etwa dort, wo ein Ersatzmodell eingespielt
    wird und die schwere Bibliothek gar nicht gebraucht wird. Fehlt sie
    wirklich, scheitert das Laden des Modells unmittelbar danach von selbst,
    laut und an der richtigen Stelle.
    """
    try:
        import torch
    except ImportError:
        return

    ziel = _ziel_threadzahl()
    if torch.get_num_threads() != ziel:
        torch.set_num_threads(ziel)
        logger.info("%s Einbettungs-Threads auf %d begrenzt (Zuteilung).", OK, ziel)


class SentenceTransformersBackend:
    """Embedding-Backend über sentence-transformers (Alternative zu Ollama).

    Die schwere Library + das Modell werden LAZY beim ersten echten Aufruf geladen
    (kein zweites Modell im API-Prozess, solange ungenutzt). `encode_fn` ist ein
    Injektionspunkt für deterministische Tests ohne Modell-Download. Jede
    Fremd-Ausnahme (inkl. fehlender Library) wird zu ProviderUnavailable."""

    name = ST_BACKEND

    def __init__(
        self,
        *,
        model_name: str,
        device: str = "cpu",
        encode_fn: Any | None = None,
    ) -> None:
        self._model_name = model_name
        self._device = device
        self._encode_fn = encode_fn
        self._model: Any | None = None
        # `_encode_sync` läuft über `asyncio.to_thread`, also in einem Arbeits-Thread.
        # Zwei gleichzeitige Anfragen laufen damit durch dieselbe Stelle; ohne diese
        # Sperre sähen beide einen leeren Platz und lüden je ein eigenes Modell.
        # Die Folge wäre kein falsches Ergebnis, sondern doppelter Speicher und
        # doppelte Ladezeit — bei einem Embedding-Modell einige hundert Megabyte.
        self._model_lock = threading.Lock()

    async def embed_batch(self, texts: Sequence[str], *, timeout_s: float) -> list[RawVector]:
        try:
            if self._encode_fn is not None:
                raw = await self._encode_fn(list(texts))
            else:
                raw = await asyncio.to_thread(self._encode_sync, list(texts))
        except EmbeddingError:
            raise
        except Exception as exc:  # Library-/Modell-/Import-Fehler kapseln (Architektur-Grenze)
            raise ProviderUnavailable(
                f"❌ Embedding-Backend '{self.name}' nicht verfügbar", attempted=(self.name,)
            ) from exc
        return _coerce_vectors(raw, expected_count=len(texts))

    def _encode_sync(
        self, texts: list[str]
    ) -> list[RawVector]:  # pragma: no cover - braucht Modell
        """Blockierender Encode-Pfad (in einen Thread ausgelagert). Lädt Library/Modell lazy."""
        # BEI JEDEM AUFRUF, nicht nur beim Laden — `torch.set_num_threads` ist
        # THREAD-LOKAL. Diese Funktion läuft über `asyncio.to_thread`, also in
        # einem Thread aus einem Vorrat; welcher es ist, wechselt. Stünde die
        # Begrenzung nur im Ladezweig, gälte sie ausschliesslich für den Thread,
        # der zufällig zuerst da war — jeder weitere rechnete wieder mit der
        # Threadzahl des Wirts und wäre um den Faktor 50 langsamer.
        #
        # Gemessen am 28.08.2026 im Betriebsbehälter: derselbe Prozess meldet im
        # Haupt-Thread weiterhin 48, während der Arbeits-Thread mit 16 rechnet.
        # Die Anzeige täuscht, die Wirkung nicht — und genau deshalb wäre der
        # Fehler beim Nachsehen nicht aufgefallen.
        #
        # Der Aufruf kostet im Regelfall einen Vergleich: `_begrenze_threads`
        # setzt nur, wenn der Wert abweicht.
        _begrenze_threads()

        # Doppelte Prüfung: Die erste Abfrage läuft ohne Sperre und kostet im
        # Regelfall (Modell längst geladen) nichts. Nur wer sie leer vorfindet,
        # nimmt die Sperre — und prüft danach ERNEUT, weil in der Wartezeit ein
        # anderer Thread bereits geladen haben kann.
        if self._model is None:
            with self._model_lock:
                if self._model is None:
                    # Lazy und HIER: Nur wer wirklich lädt, braucht die schwere
                    # Bibliothek. Stünde der Import weiter oben, verlangte ihn
                    # auch jeder Aufruf mit längst geladenem Modell — und jeder
                    # Pfad, der ein Ersatzmodell einsetzt, scheiterte daran.
                    from sentence_transformers import SentenceTransformer

                    self._model = SentenceTransformer(self._model_name, device=self._device)
        result = self._model.encode(texts, normalize_embeddings=False)
        return [[float(value) for value in row] for row in result]
