# ============================================================
#  FOREMAN — tests/unit/test_drift_corridor.py
#  Zweck: Pure-Unit-Tests für den geteilten Detektor-Band-Korridor
#         (reasoners/drift/baseline.corridor_at) — die EINE Quelle des
#         zustandsspezifischen Korridors median +/- effect_size_k * noise_sigma,
#         genutzt vom Trend-Band-Overlay UND der Datenpunkt-Status-Ableitung.
#  Architektur-Einordnung: Reasoning-Schicht (F4), ohne DB testbar.
# ============================================================
from __future__ import annotations

from datetime import UTC, datetime

from foreman.reasoners.drift.baseline import corridor_at

_AT_HOUR_12 = datetime(2026, 6, 16, 12, 30, tzinfo=UTC)
_AT_HOUR_3 = datetime(2026, 6, 16, 3, 5, tzinfo=UTC)


def test_corridor_at_known_state_returns_median_plus_minus_half() -> None:
    # Halbbreite = effect_size_k * noise_sigma = 3.0 * 2.0 = 6.0 → [124, 130, 136].
    band = corridor_at(
        {"12": {"median": 130.0, "sample_count": 50}},
        noise_sigma=2.0,
        effect_size_k=3.0,
        moment=_AT_HOUR_12,
    )
    assert band == (124.0, 130.0, 136.0)


def test_corridor_at_unknown_state_returns_none() -> None:
    # Zu Stunde 3 existiert kein Zustands-Profil → ehrlich None (kein geratener Korridor).
    band = corridor_at(
        {"12": {"median": 130.0, "sample_count": 50}},
        noise_sigma=2.0,
        effect_size_k=3.0,
        moment=_AT_HOUR_3,
    )
    assert band is None
