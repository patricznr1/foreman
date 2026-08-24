# ============================================================
#  FOREMAN — tests/unit/test_substrate_nachtrag.py
#  Zweck: Pflicht-Test-Block für den Nachtrag des Spiegel-Altbestands
#         (substrate/nachtrag.py). Schwerpunkt liegt auf dem FEHLERZWEIG: Ein
#         gestörter Löschversuch darf keine Zeile verbrauchen — sonst fiele sie
#         dauerhaft aus jedem künftigen Lauf, mit einer alten Erinnerung, die
#         niemand mehr ersetzt.
#  Architektur-Einordnung: Quality Gate §10.3, Vertrag der Substrat-Brücke §12.4.
# ============================================================
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.db.models import Alarm, Machine, MaintenanceEvent, SemanticEvent
from foreman.substrate.nachtrag import nachtragen

pytestmark = pytest.mark.integration


class _Redactor:
    MARKE = "[MASKIERT]"

    def redact_person_names(self, text_value: str) -> str:
        return f"{self.MARKE}{text_value}"


class _Substrat:
    """Test-Doppel der Gegenstelle. Merkt sich, was gelöscht wurde."""

    def __init__(self, *, wirft_bei: str | None = None) -> None:
        self.geloescht: list[str] = []
        self._wirft_bei = wirft_bei

    async def forget(self, entry_id: str) -> None:
        if entry_id == self._wirft_bei:
            raise RuntimeError("❌ Gegenstelle nicht erreichbar (Test)")
        self.geloescht.append(entry_id)


async def _maschine(session: AsyncSession) -> int:
    maschine = Machine(
        external_id="NACHTRAG-1", label="Nachtrag-Testmaschine", machine_class="servo_axis"
    )
    session.add(maschine)
    await session.flush()
    return maschine.id


async def _altzeile_wartung(
    session: AsyncSession, machine_id: int, *, beschreibung: str | None, ref: str
) -> SemanticEvent:
    """Legt eine Wartung samt Spiegel-Zeile im ALTEN Format an (ohne description)."""
    wartung = MaintenanceEvent(
        machine_id=machine_id,
        type="lubrication",
        description=beschreibung,
        performed_at=__import__("datetime").datetime(2026, 6, 6, tzinfo=__import__("datetime").UTC),
    )
    session.add(wartung)
    await session.flush()
    zeile = SemanticEvent(
        machine_id=machine_id,
        event_type="maintenance_performed",
        payload={
            "source_type": "maintenance",
            "source_id": wartung.id,
            "type": "lubrication",
            "machine_id": machine_id,
            "performed_at": "2026-06-06T00:00:00+00:00",
        },
        substrate_ref=ref,
    )
    session.add(zeile)
    await session.flush()
    return zeile


async def _lade(session: AsyncSession, zeilen_id: int) -> SemanticEvent:
    session.expire_all()
    return (
        await session.execute(select(SemanticEvent).where(SemanticEvent.id == zeilen_id))
    ).scalar_one()


async def test_altzeile_wird_angereichert_und_zur_neuspiegelung_freigegeben(
    db_session: AsyncSession,
) -> None:
    machine_id = await _maschine(db_session)
    zeile = await _altzeile_wartung(
        db_session, machine_id, beschreibung="Ersatzfett, nicht spezifikationskonform.", ref="alt-1"
    )
    substrat = _Substrat()

    stats = await nachtragen(db_session, substrat, _Redactor())

    assert stats.angereichert == 1
    assert stats.geloescht == 1
    assert substrat.geloescht == ["alt-1"]

    danach = await _lade(db_session, zeile.id)
    # Der Freitext ist da und maskiert …
    assert danach.payload["description"].startswith(_Redactor.MARKE)
    assert "nicht spezifikationskonform" in danach.payload["description"]
    # … und die Zeile ist für den Backfill wieder sichtbar.
    assert danach.substrate_ref is None


async def test_zweiter_lauf_fasst_angereicherte_zeilen_nicht_an(
    db_session: AsyncSession,
) -> None:
    """Idempotenz. Ohne sie würde jeder Lauf erneut löschen und neu schreiben."""
    machine_id = await _maschine(db_session)
    await _altzeile_wartung(db_session, machine_id, beschreibung="Ein Grund.", ref="alt-1")
    substrat = _Substrat()

    await nachtragen(db_session, substrat, _Redactor())
    zweiter = await nachtragen(db_session, substrat, _Redactor())

    assert zweiter.angereichert == 0
    assert zweiter.bereits_vollstaendig == 1
    assert substrat.geloescht == ["alt-1"], "beim zweiten Lauf wurde erneut gelöscht"


async def test_gestoerte_gegenstelle_verbraucht_die_zeile_nicht(
    db_session: AsyncSession,
) -> None:
    """DER FEHLERZWEIG — die wichtigste Zusicherung dieses Moduls.

    Eine Störung des WEGES (Gegenstelle nicht erreichbar) darf keine Zeile
    verbrauchen. Täte sie es, bliebe die Zeile mit aufgehobener Referenz und
    angereicherter Nutzlast zurück, während die ALTE Erinnerung im Gedächtnis
    weiterlebt — dauerhaft, weil kein Lauf sie je wieder anfasst. Das Ergebnis
    wäre genau die Dublette, die dieses Modul verhindern soll.

    Geprüft wird deshalb nicht nur der Zähler, sondern die AUSWAHL des nächsten
    Laufs: Steht die Zeile wieder drin?
    """
    machine_id = await _maschine(db_session)
    zeile = await _altzeile_wartung(db_session, machine_id, beschreibung="Ein Grund.", ref="kaputt")

    gestoert = await nachtragen(db_session, _Substrat(wirft_bei="kaputt"), _Redactor())

    assert gestoert.loeschen_fehlgeschlagen == 1
    assert gestoert.angereichert == 0, "der Zähler zählt einen Erfolg, den es nicht gab"

    # Die Zeile ist unverändert: Referenz steht, Nutzlast ohne Freitext.
    danach = await _lade(db_session, zeile.id)
    assert danach.substrate_ref == "kaputt"
    assert "description" not in danach.payload

    # Und der nächste Lauf greift sie erneut — mit gesunder Gegenstelle.
    heil = _Substrat()
    zweiter = await nachtragen(db_session, heil, _Redactor())
    assert zweiter.angereichert == 1
    assert heil.geloescht == ["kaputt"]


async def test_fehlende_quellzeile_erfindet_keinen_text(db_session: AsyncSession) -> None:
    """Kein erfundener Inhalt — dieselbe Linie wie im Backfill.

    Zeigt die Nutzlast auf eine Quellzeile, die es nicht mehr gibt, behält die
    Zeile ihre bisherige, gültige Spiegelung. Sie zu löschen wäre ein Verlust
    ohne Gewinn.
    """
    machine_id = await _maschine(db_session)
    zeile = SemanticEvent(
        machine_id=machine_id,
        event_type="maintenance_performed",
        payload={
            "source_type": "maintenance",
            "source_id": 999_999,  # existiert nicht
            "type": "inspection",
            "machine_id": machine_id,
            "performed_at": "2026-06-06T00:00:00+00:00",
        },
        substrate_ref="alt-x",
    )
    db_session.add(zeile)
    await db_session.flush()
    substrat = _Substrat()

    stats = await nachtragen(db_session, substrat, _Redactor())

    assert stats.quelle_fehlt == 1
    assert stats.angereichert == 0
    assert substrat.geloescht == [], "eine Zeile ohne Quelle wurde trotzdem gelöscht"
    danach = await _lade(db_session, zeile.id)
    assert danach.substrate_ref == "alt-x"


async def test_leere_beschreibung_zaehlt_getrennt_und_bleibt_unangetastet(
    db_session: AsyncSession,
) -> None:
    """Aufbau-Kontrolle: `ohne_freitext` und `quelle_fehlt` sind NICHT dasselbe.

    Beide führen zum Überspringen, haben aber verschiedene Ursachen. Ein
    gemeinsamer Zähler verwischte, ob Quellen fehlen (ein Datenproblem) oder ob
    Vorgänge schlicht unkommentiert sind (normal).
    """
    machine_id = await _maschine(db_session)
    await _altzeile_wartung(db_session, machine_id, beschreibung="   ", ref="alt-leer")
    substrat = _Substrat()

    stats = await nachtragen(db_session, substrat, _Redactor())

    assert stats.ohne_freitext == 1
    assert stats.quelle_fehlt == 0
    assert substrat.geloescht == []


async def test_trockenlauf_schreibt_nichts_und_loescht_nichts(db_session: AsyncSession) -> None:
    machine_id = await _maschine(db_session)
    zeile = await _altzeile_wartung(db_session, machine_id, beschreibung="Ein Grund.", ref="alt-1")
    substrat = _Substrat()

    stats = await nachtragen(db_session, substrat, _Redactor(), trockenlauf=True)

    assert stats.angereichert == 1  # gezählt …
    assert substrat.geloescht == []  # … aber nichts getan.
    danach = await _lade(db_session, zeile.id)
    assert danach.substrate_ref == "alt-1"
    assert "description" not in danach.payload


async def test_alarm_wird_ebenso_angereichert(db_session: AsyncSession) -> None:
    """Der zweite Ereignistyp — sonst bliebe offen, ob das Verzeichnis wirkt."""
    machine_id = await _maschine(db_session)
    alarm = Alarm(
        machine_id=machine_id,
        code="AXIS_VIB_WARN",
        message="Lagerschwingung über Warnschwelle",
        severity="warning",
        category="hardware",
        raised_at=__import__("datetime").datetime(2026, 6, 19, tzinfo=__import__("datetime").UTC),
    )
    db_session.add(alarm)
    await db_session.flush()
    zeile = SemanticEvent(
        machine_id=machine_id,
        event_type="alarm_raised",
        payload={
            "source_type": "alarm",
            "source_id": alarm.id,
            "code": "AXIS_VIB_WARN",
            "severity": "warning",
            "category": "hardware",
            "machine_id": machine_id,
            "raised_at": "2026-06-19T00:00:00+00:00",
        },
        substrate_ref="alt-a",
    )
    db_session.add(zeile)
    await db_session.flush()

    stats = await nachtragen(db_session, _Substrat(), _Redactor())

    assert stats.angereichert == 1
    danach = await _lade(db_session, zeile.id)
    assert "Lagerschwingung" in danach.payload["message"]
