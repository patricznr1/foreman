# ============================================================
#  FOREMAN — tests/unit/test_substrate_aufraeumen.py
#  Zweck: Pflicht-Test-Block für das Entfernen verwaister Spiegelungen
#         (substrate/aufraeumen.py). Der Vorgang ist UNUMKEHRBAR — der
#         Schwerpunkt liegt deshalb auf dem, was NICHT gelöscht werden darf.
#  Architektur-Einordnung: Quality Gate §10.3, Vertrag der Substrat-Brücke §12.4.
# ============================================================
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import Alarm, Machine, MaintenanceEvent, SemanticEvent
from foreman.substrate.aufraeumen import aufraeumen
from foreman.substrate.client import SubstrateNotFoundError

pytestmark = pytest.mark.integration

ZEIT = dt.datetime(2026, 6, 6, tzinfo=dt.UTC)


class _Substrat:
    def __init__(self, *, wirft_bei: str | None = None, nicht_da: str | None = None) -> None:
        self.geloescht: list[str] = []
        self._wirft_bei = wirft_bei
        self._nicht_da = nicht_da

    async def forget(self, entry_id: str) -> None:
        if entry_id == self._wirft_bei:
            raise RuntimeError("❌ Gegenstelle nicht erreichbar (Test)")
        if entry_id == self._nicht_da:
            raise SubstrateNotFoundError("❌ liegt nicht (mehr) vor (Test)")
        self.geloescht.append(entry_id)


async def _maschine(session: AsyncSession) -> int:
    m = Machine(external_id="AUFR-1", label="Aufräum-Testmaschine", machine_class="servo_axis")
    session.add(m)
    await session.flush()
    return m.id


async def _spiegel(
    session: AsyncSession,
    machine_id: int,
    *,
    ref: str,
    mit_quelle: bool,
    ueber_merkmale: bool = False,
) -> SemanticEvent:
    """Eine Spiegelzeile — wahlweise mit lebender Quellzeile oder verwaist."""
    payload: dict = {
        "type": "lubrication",
        "machine_id": machine_id,
        "performed_at": ZEIT.isoformat(),
    }
    if mit_quelle:
        w = MaintenanceEvent(
            machine_id=machine_id, type="lubrication", description="Ein Grund.", performed_at=ZEIT
        )
        session.add(w)
        await session.flush()
        if not ueber_merkmale:
            payload["source_type"] = "maintenance"
            payload["source_id"] = w.id
    else:
        # Kennung, die es nicht gibt — und Merkmale, die auf nichts passen.
        payload["source_type"] = "maintenance"
        payload["source_id"] = 999_999
        payload["performed_at"] = dt.datetime(2020, 1, 1, tzinfo=dt.UTC).isoformat()

    zeile = SemanticEvent(
        machine_id=machine_id,
        event_type="maintenance_performed",
        payload=payload,
        substrate_ref=ref,
    )
    session.add(zeile)
    await session.flush()
    return zeile


async def _anzahl(session: AsyncSession) -> int:
    session.expire_all()
    return int(
        (await session.execute(select(func.count()).select_from(SemanticEvent))).scalar_one()
    )


# ──────────────────────────────────────────────────────────────────────
#  Was NICHT gelöscht werden darf — der Vorgang ist unumkehrbar
# ──────────────────────────────────────────────────────────────────────


async def test_eine_zeile_mit_lebender_quelle_bleibt(db_session: AsyncSession) -> None:
    """Die wichtigste Zusicherung: Was noch einen Bezug hat, bleibt.

    Eine irrtümlich entfernte Spiegelung käme nie wieder — die Quellzeile
    existiert, aber die Erinnerung dazu wäre fort, und kein Lauf legt sie neu an.
    """
    machine_id = await _maschine(db_session)
    await _spiegel(db_session, machine_id, ref="lebt", mit_quelle=True)
    substrat = _Substrat()

    stats = await aufraeumen(db_session, substrat)

    assert stats.mit_quelle == 1
    assert stats.verwaist == 0
    assert substrat.geloescht == []
    assert await _anzahl(db_session) == 1


async def test_auch_ueber_die_merkmalssuche_auffindbar_zaehlt_als_lebend(
    db_session: AsyncSession,
) -> None:
    """AUFBAU-KONTROLLE: BEIDE Suchwege müssen zählen, nicht nur der gespeicherte.

    Altzeilen tragen keinen Rückweg und werden über Maschine, Zeitpunkt und Art
    gefunden. Prüfte das Aufräumen nur den gespeicherten Weg, hielte es genau
    diese Zeilen für verwaist — und löschte den halben Bestand.
    """
    machine_id = await _maschine(db_session)
    await _spiegel(db_session, machine_id, ref="alt", mit_quelle=True, ueber_merkmale=True)
    substrat = _Substrat()

    stats = await aufraeumen(db_session, substrat)

    assert stats.mit_quelle == 1, "eine über Merkmale auffindbare Zeile galt als verwaist"
    assert await _anzahl(db_session) == 1


async def test_gestoerte_gegenstelle_laesst_die_zeile_stehen(db_session: AsyncSession) -> None:
    """DER FEHLERZWEIG: Eine Störung des Weges darf nichts halb erledigen.

    Die Zeile jetzt zu entfernen liesse eine Erinnerung zurück, die niemand mehr
    zuordnen kann — schlimmer als der Rest, den sie ersetzt.
    """
    machine_id = await _maschine(db_session)
    await _spiegel(db_session, machine_id, ref="kaputt", mit_quelle=False)

    stats = await aufraeumen(db_session, _Substrat(wirft_bei="kaputt"))

    assert stats.loeschen_fehlgeschlagen == 1
    assert stats.verwaist == 0, "der Zähler meldet eine Entfernung, die nicht stattfand"
    assert await _anzahl(db_session) == 1

    # Und der nächste Lauf greift sie erneut.
    heil = _Substrat()
    zweiter = await aufraeumen(db_session, heil)
    assert zweiter.geloescht == 1
    assert heil.geloescht == ["kaputt"]
    assert await _anzahl(db_session) == 0


# ──────────────────────────────────────────────────────────────────────
#  Was entfernt wird
# ──────────────────────────────────────────────────────────────────────


async def test_verwaiste_zeile_wird_samt_erinnerung_entfernt(db_session: AsyncSession) -> None:
    """Der Zweck: Vorgänge, die niemand mehr nachschlagen kann, belegen keine Plätze."""
    machine_id = await _maschine(db_session)
    await _spiegel(db_session, machine_id, ref="verwaist", mit_quelle=False)
    substrat = _Substrat()

    stats = await aufraeumen(db_session, substrat)

    assert stats.verwaist == 1
    assert stats.geloescht == 1
    assert substrat.geloescht == ["verwaist"]
    assert await _anzahl(db_session) == 0


async def test_bereits_fortgeschaffte_erinnerung_raeumt_die_zeile_trotzdem_ab(
    db_session: AsyncSession,
) -> None:
    """Ein 404 heisst: Ziel erreicht. Die Zeile darf weg.

    Als Störung behandelt bliebe sie dauerhaft stehen — die Kennung taucht ja nie
    wieder auf.
    """
    machine_id = await _maschine(db_session)
    await _spiegel(db_session, machine_id, ref="schon-fort", mit_quelle=False)

    stats = await aufraeumen(db_session, _Substrat(nicht_da="schon-fort"))

    assert stats.schon_fort == 1
    assert stats.geloescht == 0
    assert await _anzahl(db_session) == 0


async def test_trockenlauf_zaehlt_nur(db_session: AsyncSession) -> None:
    """Vor einem unumkehrbaren Vorgang muss sich ansehen lassen, was er tun würde."""
    machine_id = await _maschine(db_session)
    await _spiegel(db_session, machine_id, ref="verwaist", mit_quelle=False)
    substrat = _Substrat()

    stats = await aufraeumen(db_session, substrat, trockenlauf=True)

    assert stats.verwaist == 1
    assert substrat.geloescht == []
    assert await _anzahl(db_session) == 1


async def test_ableitungen_des_systems_werden_nicht_angefasst(db_session: AsyncSession) -> None:
    """Empfehlung und Ereigniskette haben keine Quellzeile im Archiv-Sinn.

    Sie sind deshalb auch nicht verwaist. Ob sie überhaupt in die Archiv-Suche
    gehören, ist eine eigene Frage — sie hier nebenbei mitzulöschen hiesse, sie
    stillschweigend zu entscheiden.
    """
    machine_id = await _maschine(db_session)
    for art in ("failure_recommendation", "event_chain_reconstructed"):
        db_session.add(
            SemanticEvent(
                machine_id=machine_id,
                event_type=art,
                payload={"machine_id": machine_id},
                substrate_ref=f"ref-{art}",
            )
        )
    await db_session.flush()
    substrat = _Substrat()

    stats = await aufraeumen(db_session, substrat)

    assert stats.geprueft == 0, "eine Ableitung wurde geprüft"
    assert substrat.geloescht == []
    assert await _anzahl(db_session) == 2


async def test_alarme_werden_ebenso_geraeumt(db_session: AsyncSession) -> None:
    """Der zweite Ereignistyp — sonst bliebe offen, ob das Verzeichnis wirkt."""
    machine_id = await _maschine(db_session)
    alarm = Alarm(
        machine_id=machine_id,
        code="AXIS_VIB_WARN",
        message="Lagerschwingung",
        severity="warning",
        category="hardware",
        raised_at=ZEIT,
    )
    db_session.add(alarm)
    await db_session.flush()
    lebt = SemanticEvent(
        machine_id=machine_id,
        event_type="alarm_raised",
        payload={
            "source_type": "alarm",
            "source_id": alarm.id,
            "code": "AXIS_VIB_WARN",
            "machine_id": machine_id,
            "raised_at": ZEIT.isoformat(),
        },
        substrate_ref="alarm-lebt",
    )
    tot = SemanticEvent(
        machine_id=machine_id,
        event_type="alarm_raised",
        payload={
            "source_type": "alarm",
            "source_id": 999_999,
            "code": "AXIS_VIB_WARN",
            "machine_id": machine_id,
            "raised_at": dt.datetime(2020, 1, 1, tzinfo=dt.UTC).isoformat(),
        },
        substrate_ref="alarm-tot",
    )
    db_session.add_all([lebt, tot])
    await db_session.flush()
    substrat = _Substrat()

    stats = await aufraeumen(db_session, substrat)

    assert stats.mit_quelle == 1
    assert stats.verwaist == 1
    assert substrat.geloescht == ["alarm-tot"]
    assert await _anzahl(db_session) == 1
