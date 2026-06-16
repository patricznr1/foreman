# ============================================================
#  FOREMAN — realtime/channels.py
#  Zweck: Der NOTIFY-Vertrag (F5) zwischen Producer (Schreibpfad) und Consumer
#         (Hub). Ein `ChangeSet` beschreibt, WAS sich in einem Commit/Batch
#         geändert hat (Maschinen-/Datenpunkt-IDs + Ereignisarten) — bewusst nur
#         IDs, nie Nutzlast (dünner Payload, fire-and-forget). Der Hub lädt nach
#         dem debounce über den Read-Core konsolidiert nach.
#  Architektur-Einordnung: Live-Push-Layer (F5), reine Serialisierung — ohne DB,
#         ohne Transport, direkt unit-testbar.
#  Overflow (Vorgabe 4): ein zu großer Payload (NOTIFY-Limit 8000 Byte) wird NICHT
#         still abgeschnitten, sondern zu einem breiten Refresh-Signal (`broad`),
#         das den Hub anweist, alle abonnierten Themen nachzuladen.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

import json
from dataclasses import dataclass

# Postgres-NOTIFY-Kanal des Dashboard-Push-Layers (gültiger Identifier).
DASHBOARD_CHANNEL = "foreman_dashboard"
# Schema-Version des Payloads — erlaubt spätere Feldänderungen ohne Bruch.
_PAYLOAD_VERSION = 1
# Sicherheitsgrenze unter dem harten 8000-Byte-NOTIFY-Limit von Postgres.
_MAX_PAYLOAD_BYTES = 7000


@dataclass(frozen=True)
class ChangeSet:
    """Was sich in einem Commit/Batch geändert hat — die NOTIFY-Nutzlast (nur IDs).

    `broad=True` ist das Overflow-/Sammel-Signal: „etwas hat sich geändert, lade
    alle abonnierten Themen neu" — ohne einzelne IDs.
    """

    machines: frozenset[int] = frozenset()
    data_points: frozenset[int] = frozenset()
    kinds: frozenset[str] = frozenset()
    broad: bool = False

    def is_empty(self) -> bool:
        """True, wenn nichts zu signalisieren ist (kein NOTIFY nötig)."""
        return not (self.broad or self.machines or self.data_points or self.kinds)


def _broad_payload() -> str:
    return json.dumps({"v": _PAYLOAD_VERSION, "broad": True}, separators=(",", ":"))


def encode_change(change: ChangeSet) -> str:
    """Serialisiert ein ChangeSet zu kompaktem JSON für pg_notify.

    Übersteigt der Payload die Sicherheitsgrenze, degradiert er zu einem breiten
    Refresh-Signal — kein stilles Abschneiden von IDs (Vorgabe 4).
    """
    if change.broad:
        return _broad_payload()
    payload = json.dumps(
        {
            "v": _PAYLOAD_VERSION,
            "machines": sorted(change.machines),
            "data_points": sorted(change.data_points),
            "kinds": sorted(change.kinds),
        },
        separators=(",", ":"),
    )
    if len(payload.encode("utf-8")) > _MAX_PAYLOAD_BYTES:
        return _broad_payload()
    return payload


def decode_change(payload: str) -> ChangeSet:
    """Liest ein ChangeSet aus dem NOTIFY-Payload (Hub-Seite)."""
    data = json.loads(payload)
    if data.get("broad"):
        return ChangeSet(broad=True)
    return ChangeSet(
        machines=frozenset(data.get("machines", [])),
        data_points=frozenset(data.get("data_points", [])),
        kinds=frozenset(data.get("kinds", [])),
    )
