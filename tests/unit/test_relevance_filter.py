# ============================================================
#  FOREMAN — tests/unit/test_relevance_filter.py
#  Zweck: Pflicht-Test-Block für den Relevanz-Filter (F4, Research §8).
#  Prüft: Bagatell-Signale (kleine Effektgröße) werden unterdrückt; persistente,
#  große Drift wird durchgelassen; ADWIN-Signal allein ohne Effektgröße/Persistenz
#  reicht nicht; pro Drift-Episode wird genau einmal gemeldet; nach Rückfall
#  setzt der Filter zurück.
#  Architektur-Einordnung: Quality Gate §10.3 (Reasoner, Relevanz-Heuristik).
# ============================================================
from __future__ import annotations

from foreman.reasoners.drift.relevance import (
    DEFAULT_MIN_EFFECT_SIZE,
    DEFAULT_PERSISTENCE_INTERVALS,
    RelevanceFilter,
)


def test_defaults_sind_gesetzt() -> None:
    flt = RelevanceFilter()
    assert flt.min_effect_size == DEFAULT_MIN_EFFECT_SIZE
    assert flt.persistence_intervals == DEFAULT_PERSISTENCE_INTERVALS


def test_bagatell_signal_wird_unterdrueckt() -> None:
    # Kleine Effektgröße unter der Schwelle — auch mit ADWIN-Signal nie relevant.
    flt = RelevanceFilter(min_effect_size=2.0, persistence_intervals=3)
    relevant = [flt.update(0.3, drift_signaled=True) for _ in range(50)]
    assert not any(relevant)


def test_grosse_persistente_drift_wird_durchgelassen() -> None:
    flt = RelevanceFilter(min_effect_size=2.0, persistence_intervals=3)
    # ADWIN meldet zum Zeitpunkt 0; Effektgröße bleibt über der Schwelle.
    results = []
    results.append(flt.update(5.0, drift_signaled=True))  # armed, consec=1
    results.append(flt.update(5.0, drift_signaled=False))  # consec=2
    results.append(flt.update(5.0, drift_signaled=False))  # consec=3 -> relevant
    assert results == [False, False, True]


def test_persistenz_noch_nicht_erreicht() -> None:
    flt = RelevanceFilter(min_effect_size=2.0, persistence_intervals=5)
    out = [flt.update(5.0, drift_signaled=True) for _ in range(4)]  # < 5 Intervalle
    assert not any(out)


def test_effektgroesse_ohne_adwin_signal_meldet_nicht() -> None:
    # Große, persistente Effektgröße, aber ADWIN hat NIE statistische Drift gemeldet
    # -> keine relevante Drift (ADWIN muss die Signifikanz bestätigen).
    flt = RelevanceFilter(min_effect_size=2.0, persistence_intervals=3)
    out = [flt.update(5.0, drift_signaled=False) for _ in range(20)]
    assert not any(out)


def test_genau_einmal_pro_episode() -> None:
    flt = RelevanceFilter(min_effect_size=2.0, persistence_intervals=2)
    out = []
    for i in range(20):
        out.append(flt.update(5.0, drift_signaled=(i == 0)))
    assert out.count(True) == 1  # nur eine Meldung pro zusammenhängender Episode


def test_reset_nach_rueckfall_erlaubt_neue_meldung() -> None:
    flt = RelevanceFilter(min_effect_size=2.0, persistence_intervals=2)
    # Erste Episode -> eine Meldung.
    flt.update(5.0, drift_signaled=True)
    first = flt.update(5.0, drift_signaled=False)
    assert first is True
    # Effektgröße fällt unter die Schwelle -> Filter setzt zurück.
    flt.update(0.1, drift_signaled=False)
    # Neue Episode -> wieder meldbar.
    flt.update(5.0, drift_signaled=True)
    second = flt.update(5.0, drift_signaled=False)
    assert second is True
