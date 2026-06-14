# ============================================================
#  FOREMAN — reasoners/drift/relevance.py
#  Zweck: Relevanz-Filter gegen Alarmmüdigkeit (F4, Research §8, Baustein 4).
#  Architektur-Einordnung: Reasoning-Schicht (F4), nachgelagert zum Detektor.
#         ADWIN meldet STATISTISCHE Signifikanz; betrieblich relevant ist erst
#         eine Drift ab gewisser Effektgröße UND Persistenz über mehrere
#         Intervalle. Dieser Filter setzt beide Hürden, bevor ein operatorseitiges
#         Drift-Ereignis entsteht — gegen eine Flut von Bagatell-Meldungen.
#  Reine, seedbare Logik (ohne DB testbar).
# ============================================================
from __future__ import annotations

from dataclasses import dataclass
from typing import Final

# Mindest-Effektgröße als z-Score (|Residuum| / Rausch-Streuung). Messgrößen-
# invariant: dieselbe Schwelle greift über mm/s, Nm, °C. An den Validierungs-
# Szenarien geschärft (mit zustandsspezifischer Baseline): erkennt die echten
# Verschleiß-Drifts (Lager, Werkzeug, Schmierung), unterdrückt aber sowohl das
# Schicht-Rauschen einer gesunden Maschine als auch eine bloß normale Alterung
# (lubrication-Kontroll-Lager). Zusammen mit der Persistenz die Fehlalarm-Sperre.
DEFAULT_MIN_EFFECT_SIZE: Final = 3.0

# Persistenz: so viele aufeinanderfolgende Intervalle muss die Effektgröße halten,
# bevor die Drift als relevant gilt. Trennt langanhaltende Drift von kurzen
# Rausch-Clustern (zentral für die Fehlalarm-Freiheit auf healthy_baseline).
DEFAULT_PERSISTENCE_INTERVALS: Final = 12


@dataclass
class RelevanceFilter:
    """Filtert ADWIN-Drift auf betrieblich relevante Ereignisse.

    Ablauf je data_point: Ein ADWIN-Signal „armt" den Filter (statistische
    Signifikanz). Relevant wird die Drift erst, wenn die Effektgröße zusätzlich
    über `persistence_intervals` aufeinanderfolgende Intervalle die
    `min_effect_size` hält. Pro zusammenhängender Drift-Episode wird genau einmal
    gemeldet; fällt die Effektgröße unter die Schwelle zurück, setzt der Filter
    zurück und eine neue Episode ist wieder meldbar.
    """

    min_effect_size: float = DEFAULT_MIN_EFFECT_SIZE
    persistence_intervals: int = DEFAULT_PERSISTENCE_INTERVALS
    _consecutive: int = 0
    _armed: bool = False
    _emitted: bool = False

    def update(self, effect_size: float, *, drift_signaled: bool) -> bool:
        """Verarbeitet ein Intervall und meldet, ob eine RELEVANTE Drift vorliegt.

        `effect_size`: Betrag der aktuellen Abweichung (>= 0), vom Service geliefert.
        `drift_signaled`: ADWIN hat in diesem Intervall statistische Drift gemeldet.
        """
        if drift_signaled:
            self._armed = True

        if effect_size >= self.min_effect_size:
            self._consecutive += 1
        else:
            # Zurück unter die Schwelle: Episode beendet, Filter zurücksetzen.
            self._consecutive = 0
            self._armed = False
            self._emitted = False

        persistent = self._consecutive >= self.persistence_intervals
        if self._armed and persistent and not self._emitted:
            self._emitted = True
            return True
        return False
