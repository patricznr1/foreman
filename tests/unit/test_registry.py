# ============================================================
#  FOREMAN — tests/unit/test_registry.py
#  Zweck: Pflicht-Test-Block für die Adapter-Registry (F3).
#  Prüft: register/create/available/load_active + Fehlerfall (unbekannter Name)
#  + dass der Simulations-Adapter per Import-Seiteneffekt registriert ist.
#  Architektur-Einordnung: Quality Gate §10.3.
# ============================================================
from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any

import pytest

from foreman.ingestion.adapter import SourceAdapter
from foreman.ingestion.normalized import NormalizedEvent, NormalizedReading
from foreman.ingestion.registry import (
    AdapterNotRegisteredError,
    available_adapters,
    create_adapter,
    load_active_adapters,
    register_adapter,
)


class _DummyAdapter(SourceAdapter):
    """Minimaler SourceAdapter für Registry-Tests."""

    def __init__(self, **config: Any) -> None:
        self.config = config

    @property
    def name(self) -> str:
        return "dummy"

    async def seed_topology(self, session: object) -> None:
        return None

    def readings(self) -> Iterable[NormalizedReading]:
        return iter(())

    def events(self) -> Iterator[NormalizedEvent]:
        return iter(())


def test_register_und_create_mit_config() -> None:
    register_adapter("dummy_test", lambda **cfg: _DummyAdapter(**cfg))
    assert "dummy_test" in available_adapters()
    adapter = create_adapter("dummy_test", x=1, y="z")
    assert isinstance(adapter, _DummyAdapter)
    assert adapter.config == {"x": 1, "y": "z"}


def test_create_unbekannter_adapter_wirft() -> None:
    with pytest.raises(AdapterNotRegisteredError):
        create_adapter("gibt_es_nicht_xyz")


def test_load_active_adapters_mit_configs() -> None:
    register_adapter("dummy_active", lambda **cfg: _DummyAdapter(**cfg))
    adapters = load_active_adapters(["dummy_active"], {"dummy_active": {"k": 7}})
    assert len(adapters) == 1
    assert isinstance(adapters[0], _DummyAdapter)
    assert adapters[0].config == {"k": 7}


def test_load_active_adapters_ohne_config_ist_leer_parametrisiert() -> None:
    register_adapter("dummy_noconf", lambda **cfg: _DummyAdapter(**cfg))
    adapters = load_active_adapters(["dummy_noconf"])
    assert adapters[0].config == {}


def test_simulation_adapter_ist_registriert() -> None:
    # Import-Seiteneffekt registriert den Simulations-Adapter.
    import foreman.adapters.simulation  # noqa: F401

    assert "simulation" in available_adapters()
