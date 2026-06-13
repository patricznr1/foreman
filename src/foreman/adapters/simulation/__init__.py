# ============================================================
#  FOREMAN — adapters/simulation/__init__.py
#  Zweck: Simulations-Adapter (F3) — szenario-getriebener Generator realistischer
#         Sensordaten mit injizierbarer Drift bei bekanntem t*.
#  Architektur-Einordnung: Datenakquise (Schicht 2). Der Import registriert den
#         Adapter unter dem Namen 'simulation' in der Ingestion-Registry.
# ============================================================
from __future__ import annotations

# Import mit Seiteneffekt: registriert SimulationAdapter in der Registry.
from foreman.adapters.simulation.adapter import SimulationAdapter

__all__ = ["SimulationAdapter"]
