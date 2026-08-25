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
from foreman.substrate.client import SubstrateNotFoundError
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


# ──────────────────────────────────────────────────────────────────────
#  Altzeilen OHNE Rückweg — der eigentliche Anwendungsfall
# ──────────────────────────────────────────────────────────────────────


async def _altzeile_ohne_rueckweg(
    session: AsyncSession, machine_id: int, *, beschreibung: str, zeitpunkt: object, ref: str
) -> SemanticEvent:
    """Nutzlast, wie sie vor Einführung von source_id geschrieben wurde.

    Gegen die laufende Instanz erhoben (25.08.2026): So sehen alle 44 Altzeilen
    aus — kein `source_type`, kein `source_id`.
    """
    wartung = MaintenanceEvent(
        machine_id=machine_id, type="lubrication", description=beschreibung, performed_at=zeitpunkt
    )
    session.add(wartung)
    await session.flush()
    zeile = SemanticEvent(
        machine_id=machine_id,
        event_type="maintenance_performed",
        payload={
            "type": "lubrication",
            "machine_id": machine_id,
            "performed_at": zeitpunkt.isoformat(),
            "performed_by": "v1:abc",
        },
        substrate_ref=ref,
    )
    session.add(zeile)
    await session.flush()
    return zeile


async def test_altzeile_ohne_source_id_wird_ueber_merkmale_gefunden(
    db_session: AsyncSession,
) -> None:
    """Der Fall, für den dieses Werkzeug überhaupt gebaut ist.

    Der Rückweg `source_id` kam erst mit der Notiz-Spiegelung. Ein Nachtrag, der
    nur ihn kennt, erreicht genau die Zeilen nicht, die er erreichen soll — der
    erste Trockenlauf gegen die Instanz meldete deshalb 44 von 44 als
    unauffindbar. Ersatzweise identifizieren Maschine, Zeitpunkt und Art die
    Quellzeile.
    """
    import datetime as _dt

    machine_id = await _maschine(db_session)
    zeitpunkt = _dt.datetime(2026, 6, 5, 18, 47, 17, 894280, tzinfo=_dt.UTC)
    zeile = await _altzeile_ohne_rueckweg(
        db_session,
        machine_id,
        beschreibung="Ersatzfett genommen, nicht spezifikationskonform.",
        zeitpunkt=zeitpunkt,
        ref="alt-ohne-rueckweg",
    )
    substrat = _Substrat()

    stats = await nachtragen(db_session, substrat, _Redactor())

    assert stats.angereichert == 1, "die Altzeile wurde nicht gefunden"
    assert stats.quelle_fehlt == 0
    danach = await _lade(db_session, zeile.id)
    assert "nicht spezifikationskonform" in danach.payload["description"]
    assert danach.substrate_ref is None


async def test_mehrdeutige_merkmale_ordnen_nichts_zu(db_session: AsyncSession) -> None:
    """Aufbau-Kontrolle zum Ersatzweg — die wichtigere Hälfte.

    Passen mehrere Quellzeilen auf dieselben Merkmale, wird KEINE genommen. Eine
    falsch zugeordnete Beschreibung wäre schlimmer als eine fehlende: Sie schriebe
    einem Vorgang den Grund eines anderen zu, und später könnte das niemand mehr
    auseinanderhalten. Ohne diesen Test bliebe offen, ob der Ersatzweg auf
    Eindeutigkeit prüft oder einfach den ersten Treffer nimmt.
    """
    import datetime as _dt

    machine_id = await _maschine(db_session)
    zeitpunkt = _dt.datetime(2026, 6, 5, 12, 0, tzinfo=_dt.UTC)
    # ZWEI Wartungen mit identischen Merkmalen, verschiedene Beschreibungen.
    for text in ("Erste Beschreibung.", "Zweite Beschreibung."):
        db_session.add(
            MaintenanceEvent(
                machine_id=machine_id,
                type="lubrication",
                description=text,
                performed_at=zeitpunkt,
            )
        )
    await db_session.flush()
    zeile = SemanticEvent(
        machine_id=machine_id,
        event_type="maintenance_performed",
        payload={
            "type": "lubrication",
            "machine_id": machine_id,
            "performed_at": zeitpunkt.isoformat(),
        },
        substrate_ref="alt-mehrdeutig",
    )
    db_session.add(zeile)
    await db_session.flush()
    substrat = _Substrat()

    stats = await nachtragen(db_session, substrat, _Redactor())

    assert stats.quelle_fehlt == 1
    assert stats.angereichert == 0
    assert substrat.geloescht == []
    danach = await _lade(db_session, zeile.id)
    assert danach.substrate_ref == "alt-mehrdeutig"
    assert "description" not in danach.payload


# ──────────────────────────────────────────────────────────────────────
#  Eine bereits fortgeschaffte Erinnerung blockiert die Zeile nicht
# ──────────────────────────────────────────────────────────────────────


class _SubstratOhneEintrag:
    """Gegenstelle, die für eine Kennung meldet: hier liegt nichts (mehr)."""

    def __init__(self, *, nicht_da: str) -> None:
        self.geloescht: list[str] = []
        self._nicht_da = nicht_da

    async def forget(self, entry_id: str) -> None:
        if entry_id == self._nicht_da:
            raise SubstrateNotFoundError("❌ unter dieser Kennung liegt nichts (Test)")
        self.geloescht.append(entry_id)


async def test_bereits_fortgeschaffte_erinnerung_laesst_die_zeile_durchlaufen(
    db_session: AsyncSession,
) -> None:
    """Geprüft wird die WIRKUNG, nicht der Eintritt in den Zweig (B1).

    Ein Test, der nur den Zähler abfragt, belegt nicht, dass der Nachtrag danach
    weiterläuft. Entscheidend ist, was mit der Zeile geschieht: Sie muss ihre
    neue Nutzlast bekommen und für die Neuspiegelung freigegeben sein. Sonst
    dreht sie sich dauerhaft im Kreis — die Kennung taucht ja nie wieder auf.
    """
    machine_id = await _maschine(db_session)
    zeile = await _altzeile_wartung(
        db_session, machine_id, beschreibung="Ersatzfett genommen.", ref="laengst-weg"
    )
    substrat = _SubstratOhneEintrag(nicht_da="laengst-weg")

    stats = await nachtragen(db_session, substrat, _Redactor())

    # Getrennt gezählt: weder Erfolg noch Fehlschlag.
    assert stats.schon_geloescht == 1
    assert stats.geloescht == 0, "in `geloescht` mitgezählt — die Zahl verlöre ihre Aussage"
    assert stats.loeschen_fehlgeschlagen == 0
    assert stats.angereichert == 1

    # Und die Wirkung: Nutzlast angereichert, Referenz aufgehoben.
    danach = await _lade(db_session, zeile.id)
    assert danach.payload["description"].startswith(_Redactor.MARKE)
    assert "Ersatzfett" in danach.payload["description"]
    assert danach.substrate_ref is None, "die Zeile bliebe im Kreis stehen"


async def test_zweiter_lauf_nach_bereits_fortgeschaffter_erinnerung_ist_ruhig(
    db_session: AsyncSession,
) -> None:
    """Die Zeile ist danach erledigt und kommt nicht wieder.

    Das ist die Hälfte der Fehlerzweig-Regel, die dem 404-Zweig seinen Sinn gibt:
    Eine Störung des Weges darf keinen Eintrag verbrauchen — ein erledigter
    Eintrag darf nicht ewig wiederkehren.
    """
    machine_id = await _maschine(db_session)
    await _altzeile_wartung(db_session, machine_id, beschreibung="Ein Grund.", ref="laengst-weg")
    substrat = _SubstratOhneEintrag(nicht_da="laengst-weg")

    await nachtragen(db_session, substrat, _Redactor())
    zweiter = await nachtragen(db_session, substrat, _Redactor())

    assert zweiter.schon_geloescht == 0
    assert zweiter.angereichert == 0
    assert zweiter.bereits_vollstaendig == 1


async def test_stoerung_laesst_die_zeile_weiterhin_unangetastet(
    db_session: AsyncSession,
) -> None:
    """AUFBAU-KONTROLL-ZWILLING zum 404-Fall (B3).

    Ohne ihn wäre die Aussage "eine fortgeschaffte Erinnerung läuft durch" auch
    mit "alles läuft durch" erklärbar. Eine echte Störung muss die Zeile
    weiterhin unberührt lassen, damit der nächste Lauf sie erneut greift.
    """
    machine_id = await _maschine(db_session)
    zeile = await _altzeile_wartung(db_session, machine_id, beschreibung="Ein Grund.", ref="kaputt")

    stats = await nachtragen(db_session, _Substrat(wirft_bei="kaputt"), _Redactor())

    assert stats.loeschen_fehlgeschlagen == 1
    assert stats.schon_geloescht == 0, "eine Störung wurde als erledigt gewertet"
    assert stats.angereichert == 0

    danach = await _lade(db_session, zeile.id)
    assert danach.substrate_ref == "kaputt"
    assert "description" not in danach.payload
