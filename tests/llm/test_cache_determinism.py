# ============================================================
#  FOREMAN — tests/llm/test_cache_determinism.py
#  Zweck: Pflicht-Test-Block für das deterministische Antwort-Caching (F-LLM).
#         Teil 1 (hier): Cache-Schlüssel deterministisch, abweichungssensitiv,
#         PII-frei (gehasht); get/set setzt from_cache; deaktivierter Cache
#         speichert nichts. Teil 2 (Gateway-Ebene: gleicher Input → byte-
#         identische gecachte Antwort, Backend nur einmal) folgt weiter unten.
#  Architektur-Einordnung: Quality Gate §10.3. Reine Unit-Tests, kein Netz.
# ============================================================
from __future__ import annotations

from foreman.llm.cache import ResponseCache
from foreman.llm.gateway import GatewayResponse, Task
from foreman.llm.grounding import GroundingSource


def _resp(text: str = "A") -> GatewayResponse:
    return GatewayResponse(
        text=text,
        backend="local",
        model="ollama/qwen3:14b",
        task=Task.EXPLANATION,
        prompt_tokens=1,
        completion_tokens=1,
        total_tokens=2,
        latency_ms=1.0,
        estimated_cost_usd=0.0,
        finish_reason="stop",
    )


_KEY_ARGS = {
    "model": "ollama/qwen3:14b",
    "task": Task.EXPLANATION,
    "system_prompt": "System",
    "user_prompt": "Erkläre die Drift.",
    "sources": [GroundingSource("dp:42", "Temperatur 80 Grad")],
    "temperature": 0.0,
    "max_tokens": None,
}


def test_make_key_ist_deterministisch() -> None:
    assert ResponseCache.make_key(**_KEY_ARGS) == ResponseCache.make_key(**_KEY_ARGS)


def test_make_key_unterscheidet_bei_abweichendem_prompt() -> None:
    other = {**_KEY_ARGS, "user_prompt": "Etwas anderes."}
    assert ResponseCache.make_key(**_KEY_ARGS) != ResponseCache.make_key(**other)


def test_make_key_unterscheidet_bei_abweichenden_parametern() -> None:
    other = {**_KEY_ARGS, "temperature": 0.7}
    assert ResponseCache.make_key(**_KEY_ARGS) != ResponseCache.make_key(**other)


def test_make_key_enthaelt_keine_pii_im_klartext() -> None:
    key = ResponseCache.make_key(
        model="m",
        task=Task.EXPLANATION,
        system_prompt="s",
        user_prompt="Schichtbericht von Schmidt",
        sources=[GroundingSource("note:1", "vertraulicher Freitext", trusted=False)],
        temperature=0.0,
        max_tokens=None,
    )
    # Der Schlüssel ist ein SHA-256-Hash — kein Klartext, keine PII (§8).
    assert "Schmidt" not in key
    assert "vertraulich" not in key
    assert len(key) == 64


def test_cache_get_set_setzt_from_cache_flag() -> None:
    cache = ResponseCache(enabled=True)
    cache.set("k", _resp("Antwort"))
    got = cache.get("k")
    assert got is not None
    assert got.from_cache is True
    assert got.text == "Antwort"


def test_cache_deaktiviert_speichert_nichts() -> None:
    cache = ResponseCache(enabled=False)
    cache.set("k", _resp())
    assert cache.get("k") is None


# --- Gateway-Ebene: gleicher Input → byte-identische gecachte Antwort ---


async def test_gateway_cache_liefert_byte_identische_antwort(
    make_gateway: object, make_backend: object
) -> None:
    # Fixtures aus conftest; typing bewusst lax (object), Aufruf folgt der Fabrik.
    backend = make_backend("local", reply="Stabile Antwort, 80 Grad.")  # type: ignore[operator]
    gateway = make_gateway(backends=[backend], cache_enabled=True)  # type: ignore[operator]
    call = {
        "task": Task.EXPLANATION,
        "system_prompt": "System",
        "user_prompt": "Erkläre die Drift.",
        "sources": [GroundingSource("dp:42", "Temperatur 80 Grad")],
    }
    first = await gateway.complete(**call)
    second = await gateway.complete(**call)

    # Zweiter Call wird aus dem Cache bedient — Backend nur EINMAL aufgerufen.
    assert backend.calls == 1
    assert first.from_cache is False
    assert second.from_cache is True
    # Bis auf das from_cache-Flag byte-identisch.
    assert second.model_dump(exclude={"from_cache"}) == first.model_dump(exclude={"from_cache"})
