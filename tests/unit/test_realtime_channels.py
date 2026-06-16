# ============================================================
#  FOREMAN — tests/unit/test_realtime_channels.py
#  Zweck: NOTIFY-Vertrag (F5) — ChangeSet-Serialisierung. Roundtrip, leeres Set,
#         und Overflow-Schutz: ein zu großer Payload wird zu einem breiten
#         Refresh-Signal statt still abgeschnitten (Vorgabe 4: dünner Payload).
# ============================================================
from __future__ import annotations

from foreman.realtime.channels import (
    DASHBOARD_CHANNEL,
    ChangeSet,
    decode_change,
    encode_change,
)


def test_channel_name_is_a_valid_identifier() -> None:
    assert DASHBOARD_CHANNEL.isidentifier()


def test_roundtrip_preserves_all_axes() -> None:
    change = ChangeSet(
        machines=frozenset({5, 7}),
        data_points=frozenset({12}),
        kinds=frozenset({"reading", "alarm"}),
    )
    decoded = decode_change(encode_change(change))
    assert decoded.machines == frozenset({5, 7})
    assert decoded.data_points == frozenset({12})
    assert decoded.kinds == frozenset({"reading", "alarm"})
    assert decoded.broad is False


def test_empty_changeset_is_empty() -> None:
    assert ChangeSet().is_empty()
    assert not ChangeSet(machines=frozenset({1})).is_empty()


def test_broad_changeset_is_not_empty_and_roundtrips() -> None:
    assert not ChangeSet(broad=True).is_empty()
    assert decode_change(encode_change(ChangeSet(broad=True))).broad is True


def test_oversized_changeset_degrades_to_broad_within_notify_limit() -> None:
    # Mehr IDs, als in ein 8000-Byte-NOTIFY passen — Vorgabe 4: kein stilles
    # Abschneiden, sondern ein breites Refresh-Signal.
    huge = ChangeSet(data_points=frozenset(range(5000)))
    payload = encode_change(huge)
    assert len(payload.encode("utf-8")) <= 8000
    assert decode_change(payload).broad is True


def test_unknown_payload_version_degrades_to_broad() -> None:
    # Inkompatible Schema-Version (z. B. gemischter Deploy) → fail-safe broad,
    # keine still verlorenen IDs (CodeRabbit-Finding PR #18).
    assert decode_change('{"v":999,"data_points":[5]}').broad is True
