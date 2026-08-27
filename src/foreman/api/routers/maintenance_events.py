# ============================================================
#  FOREMAN — api/routers/maintenance_events.py
#  Zweck: CRUD für Wartungsereignisse (/api/v1/maintenance_events), §4.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2).
#  Datenschutz (§8): `performed_by` wird im Schreibpfad zu einem HMAC-Token
#         über die user_id tokenisiert — nie Klartext.
#  Maschinen-Scope (§20.4): jede Route führt `ResourceScopeDep` — ein Wartungs-
#         nachweis gehört zu genau einer Maschine und folgt deren Sichtbarkeit.
#  Identitätsbindung (§19): `performed_by` ist ein Nachweis-Feld (§8, auditiert
#         re-identifizierbar). Default ist die Token-Identität; ein abweichender
#         Wert ist der Nachtrag für eine dritte Person und den aufsichtsführenden
#         Rollen vorbehalten.
# ============================================================
from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from foreman.api.deps import (
    CurrentUser,
    PseudonymizerDep,
    RedactorDep,
    ResourceScopeDep,
    SessionDep,
    SubstrateClientDep,
)
from foreman.core.roles import Role
from foreman.db.models import MaintenanceEvent
from foreman.ingestion.semantic import maskiere, record_semantic_event, wartung_payload
from foreman.schemas.resources import MaintenanceEventCreate, MaintenanceEventRead

router = APIRouter(prefix="/maintenance_events", tags=["maintenance_events"])

# Rollen, die einen Wartungsnachweis für eine dritte Person eintragen dürfen
# (Rollenmatrix 3.1). Ein `worker` trägt ausschließlich für sich selbst ein.
_DELEGATING_ROLES = frozenset({Role.SHIFT_LEAD, Role.TECHNICIAN, Role.MANAGER})


@router.post("", status_code=status.HTTP_201_CREATED, response_model=MaintenanceEventRead)
async def create_maintenance_event(
    body: MaintenanceEventCreate,
    current_user: CurrentUser,
    session: SessionDep,
    pseudo: PseudonymizerDep,
    scope: ResourceScopeDep,
    redactor: RedactorDep,
    substrate: SubstrateClientDep,
) -> MaintenanceEvent:
    # Der Nachweis wird an der Maschine geführt, an der er erbracht wurde — sie muss
    # im Ausschnitt des Eintragenden liegen. Die Rollenfrage darunter (Nachtrag für
    # eine dritte Person) ist eine andere und ersetzt diese nicht.
    await scope.require(body.machine_id)
    data = body.model_dump()
    if data.get("performed_at") is None:
        data.pop("performed_at", None)  # Server-Default greift
    own_id = str(current_user.id)
    # Leer/weggelassen → der eingeloggte Nutzer. Nur ein ABWEICHENDER Wert ist ein
    # Nachtrag für eine dritte Person und damit rollenbeschränkt.
    performed_by = data.pop("performed_by", None) or own_id
    if performed_by != own_id and current_user.role not in _DELEGATING_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Deine Rolle darf Wartungen nur für die eigene Person eintragen",
        )
    obj = MaintenanceEvent(
        **data,
        performed_by=pseudo.tokenize_worker(performed_by),
    )
    session.add(obj)
    await session.flush()  # Schlüssel vor der Spiegelung (§12.4)
    # SPIEGELUNG INS GEDÄCHTNIS (seit 27.08.2026). Vorher entstand hier eine
    # Wartung OHNE Erinnerung: Die Spiegelung kam am 24.08. mit der Schichtnotiz
    # und wurde für diesen Schreibweg nie nachgezogen. Wirkung, an der laufenden
    # Instanz erhoben: Alles, was ein Mensch von Hand einträgt, blieb für die
    # vierte Archiv-Quelle unsichtbar — nur der Adapter-Weg spiegelte.
    #
    # Gespiegelt wird der MASKIERTE Text, nie das Rohfeld (§15.9): Die Quellzeile
    # bleibt unverändert, der Spiegel darf nicht die schwächere Grenze sein.
    # Nutzlast und Maskierung kommen aus `ingestion/semantic.py` — dieselbe
    # Quelle wie der Adapter-Weg.
    await record_semantic_event(
        session,
        machine_id=obj.machine_id,
        event_type="maintenance_performed",
        payload=wartung_payload(obj, maskiere(redactor, obj.description)),
        substrate=substrate,
    )
    await session.refresh(obj)
    return obj


@router.get("", response_model=list[MaintenanceEventRead])
async def list_maintenance_events(
    session: SessionDep,
    scope: ResourceScopeDep,
    machine_id: int | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> Sequence[MaintenanceEvent]:
    """Wartungsereignisse im Maschinen-Ausschnitt des Anfragenden."""
    stmt = await scope.limit_to(
        select(MaintenanceEvent).order_by(MaintenanceEvent.id),
        MaintenanceEvent.machine_id,
        machine_id=machine_id,
    )
    result = await session.scalars(stmt.limit(limit).offset(offset))
    return result.all()


@router.get("/{event_id}", response_model=MaintenanceEventRead)
async def get_maintenance_event(
    event_id: int, session: SessionDep, scope: ResourceScopeDep
) -> MaintenanceEvent:
    """Ein Wartungsereignis — 404 auch für eine Maschine außerhalb des Ausschnitts."""
    obj = await session.get(MaintenanceEvent, event_id)
    if obj is None or not await scope.can_see(obj.machine_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Wartungsereignis nicht gefunden"
        )
    return obj
