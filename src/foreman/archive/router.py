# ============================================================
#  FOREMAN — archive/router.py
#  Zweck: Read-only HTTP-Route der quellenübergreifenden Archiv-Suche (Paket 1b)
#         unter GET /api/v1/archive/search — durchsucht Notizen + Wartung + Alarme
#         im Wortlaut (Wartung/Alarm) bzw. hybrid (Notiz), per RRF zu einem Rang
#         fusioniert, mit Quellen-Filter. ADDITIV — der alte
#         GET /api/v1/worker_notes/search (1a) bleibt unverändert.
#  Architektur-Einordnung: HTTP-Schicht (Schicht 2). Auth-pflichtig, KEINE
#         Schreibwirkung. Graceful: Embedding-Ausfall → Notiz-Volltext trägt,
#         Wartung/Alarm unberührt; kein 503, solange Volltext liefern kann.
#  Vertrag (für Paket 1c): flache `list[ArchiveHit]`, Reihenfolge = RRF-Rang,
#         KEIN Score-Feld.
# ============================================================
from __future__ import annotations

from typing import cast

from fastapi import APIRouter, HTTPException, Query, status

from foreman.api.deps import (
    EmbeddingProviderDep,
    ResourceScopeDep,
    SessionDep,
    SettingsDep,
    SubstrateClientDep,
)
from foreman.archive.schemas import ArchiveHit, SourceType
from foreman.archive.search import ALL_SOURCES, search_archive
from foreman.notes.search import DEFAULT_SEARCH_K

router = APIRouter(prefix="/archive", tags=["archive_search"])


def _parse_sources(raw: list[str] | None) -> tuple[SourceType, ...] | None:
    """Normalisiert den `sources`-Param: wiederholbar (`?sources=note&sources=alarm`)
    ODER CSV (`?sources=note,alarm`). Leer/fehlend → None (→ alle drei Quellen).
    Unbekannte Quelle → 422."""
    if not raw:
        return None
    parsed: list[str] = []
    for chunk in raw:
        parsed.extend(part.strip().lower() for part in chunk.split(",") if part.strip())
    if not parsed:
        return None
    invalid = sorted({source for source in parsed if source not in ALL_SOURCES})
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            # Die erlaubten Quellen kommen aus ALL_SOURCES, nicht aus einer
            # zweiten Aufzaehlung im Text: Sonst laufen Pruefung und Meldung
            # auseinander, und der Aufrufer bekommt eine Liste, in der eine
            # gueltige Quelle fehlt.
            detail=(
                f"Unbekannte Quelle(n): {', '.join(invalid)}. Erlaubt: {', '.join(ALL_SOURCES)}."
            ),
        )
    # Reihenfolge-erhaltende Deduplizierung; gegen ALL_SOURCES validiert.
    deduped = list(dict.fromkeys(parsed))
    return cast("tuple[SourceType, ...]", tuple(deduped))


# Quellen-Filter-Parameter als Modul-Singleton — hält den `Query()`-Aufruf aus dem
# Funktions-Default heraus (vermeidet B008 bei mehrzeiliger Wrappung) und erlaubt eine
# ausführliche OpenAPI-Beschreibung.
_SOURCES_QUERY = Query(
    default=None,
    description=(
        f"Quellen-Auswahl ({', '.join(ALL_SOURCES)}); wiederholbar oder CSV. "
        "Fehlt der Parameter, werden alle Quellen durchsucht. Ob das Gedächtnis "
        "tatsächlich befragt wird, entscheidet zusätzlich der Betreiber-Schalter."
    ),
)


@router.get("/search", response_model=list[ArchiveHit])
async def search_archive_endpoint(
    session: SessionDep,
    provider: EmbeddingProviderDep,
    settings: SettingsDep,
    substrate: SubstrateClientDep,
    scope: ResourceScopeDep,
    q: str = Query(min_length=1, description="Such-Anfrage (Freitext)."),
    machine_id: int | None = Query(default=None, description="Optionaler Maschinen-Filter."),
    sources: list[str] | None = _SOURCES_QUERY,
    k: int = Query(default=DEFAULT_SEARCH_K, ge=1, le=50, description="Maximale Trefferzahl."),
) -> list[ArchiveHit]:
    """Archiv-Suche über die abgelegten Berichte, Wartungen und Alarme (read-only).

    Durchsucht die gewählten Quellen nach Wortlaut (Wartung/Alarm) bzw. zugleich nach
    Wortlaut und Bedeutung (Notizen) und ordnet die Treffer nach Relevanz. Über den
    Quellen-Filter lassen sich einzelne Quellen aus- oder einblenden (Default: alle).

    Gesucht wird ausschließlich im Maschinen-Ausschnitt des Anfragenden (§20.4), und
    zwar in JEDER Quelle einzeln — sonst läge der Durchgriff in der Quelle, die
    niemand für sich geprüft hat.
    """
    erlaubte_maschinen = await scope.for_query(machine_id)
    selected = _parse_sources(sources)
    # Das Gedaechtnis nur, wenn es EINGESCHALTET ist — sonst bleibt der Schalter
    # wirkungslos, egal was der Aufrufer als Quelle waehlt. Der Client wird nur
    # dann durchgereicht; ohne ihn ist der vierte Strom strukturell still.
    substrat = substrate if settings.archive_substrate_enabled else None
    return await search_archive(
        provider,
        session,
        q,
        machine_id=machine_id,
        scope=erlaubte_maschinen,
        sources=selected,
        k=k,
        max_distance=settings.archive_vector_max_distance,
        substrate=substrat,
        substrate_k=settings.archive_substrate_k if settings.archive_substrate_enabled else 0,
    )
