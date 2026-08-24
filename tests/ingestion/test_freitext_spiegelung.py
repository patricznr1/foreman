# ============================================================
#  FOREMAN — tests/ingestion/test_freitext_spiegelung.py
#  Zweck: Der Freitext von Wartung und Alarm geht in die Spiegelung — und zwar
#         NER-MASKIERT, obwohl die Quellzeile es nicht ist (§15.9, offener
#         Befund). Geprüft wird die geschriebene semantic_events-Zeile, denn der
#         Nachtrag liest genau sie; nur was dort steht, kann er rekonstruieren
#         (§12.4, Invariante von substrate/content.py).
#  Architektur-Einordnung: Quality Gate §10.3, Vertrag der Substrat-Brücke §12.4.
# ============================================================
from __future__ import annotations

import json

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from foreman.adapters.simulation.adapter import SimulationAdapter
from foreman.adapters.simulation.scenario import load_scenario_by_name
from foreman.core.pseudonymize import Pseudonymizer
from foreman.ingestion.service import IngestionService
from foreman.substrate.content import baue_inhalt

pytestmark = pytest.mark.integration

SZENARIO = "minimal_bearing_drift"  # 1 Wartung, 1 Alarm, 2 Notizen — klein und schnell


class _MarkierenderRedactor:
    """Test-Doppel, das JEDEN Text erkennbar zeichnet.

    Warum nicht der FakeRedactor mit seiner Namensliste: Die Wartungsbeschreibung
    des Szenarios enthält keinen Namen. Ein Test gegen eine Namensliste wäre dort
    grün, ohne dass der Text die Maskierung je gesehen hätte — er prüfte die
    Abwesenheit von etwas, das ohnehin nie da war. Diese Marke belegt die
    VERDRAHTUNG: Steht sie in der gespiegelten Nutzlast, ist der Text durch den
    Redactor gelaufen; fehlt sie, nicht.
    """

    MARKE = "[MASKIERT]"

    def redact_person_names(self, text_value: str) -> str:
        return f"{self.MARKE}{text_value}"


async def _payload(conn: asyncpg.Connection, event_type: str) -> dict:
    roh = await conn.fetchval(
        "SELECT payload FROM semantic_events WHERE event_type = $1 LIMIT 1", event_type
    )
    assert roh is not None, f"keine semantic_events-Zeile für {event_type}"
    return json.loads(roh) if isinstance(roh, str) else roh


async def _ingest(db_session: AsyncSession, pseudonymizer: Pseudonymizer, redactor: object) -> None:
    adapter = SimulationAdapter(load_scenario_by_name(SZENARIO), seed=1)
    await IngestionService(db_session, pseudonymizer=pseudonymizer, redactor=redactor).ingest(
        adapter
    )


async def test_wartungsbeschreibung_laeuft_durch_die_maskierung(
    db_session: AsyncSession, raw_conn: asyncpg.Connection, pseudonymizer: Pseudonymizer
) -> None:
    """Der Vorgangsgrund kommt an — und er kommt maskiert an.

    Beides gehört in EINEN Test, weil beides an derselben Nutzlast hängt: Ein
    Test, der nur das Ankommen prüft, bliebe grün, wenn der Klartext ankäme.
    """
    await _ingest(db_session, pseudonymizer, _MarkierenderRedactor())
    payload = await _payload(raw_conn, "maintenance_performed")

    beschreibung = payload["description"]
    assert beschreibung is not None, "die Beschreibung fehlt in der Spiegelung"
    # Der Inhalt ist da …
    assert "Schmierstoff" in beschreibung
    # … und er ist durch die Maskierung gelaufen.
    assert beschreibung.startswith(_MarkierenderRedactor.MARKE)

    # Der Satz, den der Nachtrag aus genau dieser Zeile baut, trägt ihn ebenfalls.
    assert baue_inhalt("maintenance_performed", payload).endswith(beschreibung)


async def test_alarmmeldung_laeuft_durch_die_maskierung(
    db_session: AsyncSession, raw_conn: asyncpg.Connection, pseudonymizer: Pseudonymizer
) -> None:
    await _ingest(db_session, pseudonymizer, _MarkierenderRedactor())
    payload = await _payload(raw_conn, "alarm_raised")

    meldung = payload["message"]
    assert meldung is not None, "die Meldung fehlt in der Spiegelung"
    assert "Warnschwelle" in meldung
    assert meldung.startswith(_MarkierenderRedactor.MARKE)
    assert baue_inhalt("alarm_raised", payload).endswith(meldung)


async def test_der_gebaute_satz_traegt_den_grund_nicht_nur_die_struktur(
    db_session: AsyncSession, raw_conn: asyncpg.Connection, pseudonymizer: Pseudonymizer
) -> None:
    """Der eigentliche Zweck: Das Gedächtnis bekommt einen beschreibenden Satz.

    ANLASS (gemessen, Register C-050): Solange nur die Struktur gespiegelt wurde,
    lautete eine Wartungserinnerung „Wartung (lubrication) an Maschine 1
    durchgeführt" — und die vierte Archiv-Quelle brachte auf keiner von 18
    Goldset-Anfragen einen zusätzlichen zutreffenden Treffer. Der Grund eines
    Degradationsverlaufs lebt ausschliesslich im Freitext (§12.5,
    Beobachtungsgrenze); ohne ihn kann das Gedächtnis ihn nie kennen.

    Geprüft wird deshalb, dass der Satz LÄNGER ist als sein Strukturteil — nicht
    nur, dass ein Feld existiert.
    """
    await _ingest(db_session, pseudonymizer, _MarkierenderRedactor())

    for event_type, feld in (("maintenance_performed", "description"), ("alarm_raised", "message")):
        payload = await _payload(raw_conn, event_type)
        mit_freitext = baue_inhalt(event_type, payload)
        ohne_freitext = baue_inhalt(event_type, {k: v for k, v in payload.items() if k != feld})
        assert len(mit_freitext) > len(ohne_freitext), (
            f"{event_type}: der Freitext schlägt sich nicht im Satz nieder"
        )
        assert mit_freitext.startswith(ohne_freitext), (
            f"{event_type}: der bisherige Satz ist nicht mehr der Anfang — "
            "Altbestand und Neubestand liefen auseinander"
        )
