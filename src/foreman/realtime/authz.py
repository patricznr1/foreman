# ============================================================
#  FOREMAN — realtime/authz.py
#  Zweck: Abo-Autorisierung des Live-Push-Layers (F5, Vorgabe 2). Beim subscribe
#         prüft der Hub nicht nur WER (Authentifizierung), sondern OB die Rolle
#         dieses Thema sehen darf — sonst hörte ein authentifizierter Client jedes
#         Maschinen-Thema mit (PII-Pfad). default-deny: alles, was nicht explizit
#         erlaubt ist, wird abgelehnt.
#  Rollenmatrix (Designstudie 3.1): `manager`/`technician` lesen unrestricted
#         (Manager flottenweit, Techniker maschinenweit für Diagnose); `shift_lead`
#         nur seine Linien (assigned_line_ids); `worker` nur seine Maschinen
#         (assigned_machine_ids). Das Flotten-/Cockpit-Thema (overview) sehen nur
#         manager + shift_lead. Rollen-IDs sind englisch (wie users.role-Default
#         „worker"); die UI-Labels (Werker/Schichtleiter/…) sind deutsch.
#  Architektur-Einordnung: Live-Push-Layer (F5), Autorisierungs-Schicht über den
#         Themen (topics) + dem Read-Modell. Hängt am Read-Pfad (Machine/DataPoint),
#         nicht am Transport.
#  Konvention (§6): Type Hints überall, deutsche Kommentare, englische Bezeichner.
# ============================================================
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import DataPoint, Machine, User
from foreman.realtime.topics import parse_topic

ROLE_WORKER = "worker"
ROLE_SHIFT_LEAD = "shift_lead"
ROLE_TECHNICIAN = "technician"
ROLE_MANAGER = "manager"

# Rollen mit unbeschränktem Lese-Scope (Matrix 3.1).
_UNRESTRICTED_ROLES = frozenset({ROLE_MANAGER, ROLE_TECHNICIAN})
# Rollen, die das Flotten-/Cockpit-Thema sehen dürfen (Matrix 3.1: A nur Manager +
# Schichtleiter; Werker/Techniker arbeiten maschinen-/trendzentriert).
_OVERVIEW_ROLES = frozenset({ROLE_MANAGER, ROLE_SHIFT_LEAD})


async def can_subscribe(session: AsyncSession, user: User, topic: str) -> bool:
    """Entscheidet, ob `user` `topic` abonnieren darf (default-deny)."""
    kind, entity_id = parse_topic(topic)
    if kind == "overview":
        return user.role in _OVERVIEW_ROLES
    if kind == "machine" and entity_id is not None:
        return await _can_see_machine(session, user, entity_id)
    if kind == "trend" and entity_id is not None:
        machine_id = await _machine_of_data_point(session, entity_id)
        return machine_id is not None and await _can_see_machine(session, user, machine_id)
    return False


async def _can_see_machine(session: AsyncSession, user: User, machine_id: int) -> bool:
    """Scope-Prüfung pro Maschine entlang der Rollenmatrix (default-deny)."""
    if user.role in _UNRESTRICTED_ROLES:
        return True
    if user.role == ROLE_WORKER:
        return machine_id in user.assigned_machine_ids
    if user.role == ROLE_SHIFT_LEAD:
        machine = await session.get(Machine, machine_id)
        if machine is None or machine.line_id is None:
            return False
        return machine.line_id in user.assigned_line_ids
    return False


async def _machine_of_data_point(session: AsyncSession, data_point_id: int) -> int | None:
    """Löst einen Datenpunkt auf seine Maschine auf (None, wenn unbekannt)."""
    data_point = await session.get(DataPoint, data_point_id)
    return data_point.machine_id if data_point is not None else None


async def overview_scope(session: AsyncSession, user: User) -> list[int] | None:
    """Maschinen-Scope des Overview-Themas (geteilt von WS-Push + HTTP-Route).

    manager = ganze Flotte (None = kein Filter); sonst (shift_lead, die einzige
    weitere overview-berechtigte Rolle) die Maschinen seiner zugewiesenen Linien.
    """
    if user.role == ROLE_MANAGER:
        return None
    result = await session.scalars(
        select(Machine.id).where(Machine.line_id.in_(user.assigned_line_ids))
    )
    return list(result.all())
