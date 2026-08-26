# ══════════════════════════════════════════════════════════════
# FOREMAN — Betriebsprotokolle tragen keinen Personenbezug
# §8 und §11.1: keine PII in Logs — als Test eingefordert, nicht nur zugesagt.
# ══════════════════════════════════════════════════════════════
"""Hält die Zusage „keine PII in Logs" an der Stelle fest, wo sie gilt.

WARUM DAS EIN EIGENER TEST IST. Eine E-Mail-Adresse ist ein personenbezogenes
Datum (Art. 4 Nr. 1 DSGVO). Betriebsprotokolle haben eine eigene Aufbewahrung
außerhalb des Löschkonzepts der Anwendung — was dort landet, ist mit den Mitteln
der Anwendung nicht mehr zu entfernen. Eine Zusage im Kommentar hält das nicht;
ein Test, der die erzeugte Zeile liest, hält es.

WARUM OHNE DATENBANK. Geprüft wird die Protokollzeile, nicht der Schreibpfad.
Der Anlagevorgang wird deshalb durch einen Doppelgänger ersetzt und nur die
Ausgabe betrachtet — der Test läuft damit überall.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest

from foreman.core.roles import Role
from foreman.db import provisioning


class _SessionAttrappe:
    """Genügt dem Anlagepfad, ohne eine Datenbank zu berühren."""

    async def __aenter__(self) -> _SessionAttrappe:
        return self

    async def __aexit__(self, *_ausnahme: object) -> None:
        return None

    async def commit(self) -> None:
        return None


class _EngineAttrappe:
    async def dispose(self) -> None:
        return None


EMAIL = "vorname.nachname@beispiel-werk.de"


@pytest.fixture
def protokollzeilen(monkeypatch: pytest.MonkeyPatch) -> Iterator[list[str]]:
    """Führt den Anlagevorgang aus und sammelt die erzeugten Protokollzeilen.

    BEWUSST NICHT `caplog`. Dessen Sammler hängt am Wurzel-Logger, und
    `logging_setup.setup_logging` räumt genau dort auf (`root.handlers.clear()`),
    damit die Einrichtung wiederholbar bleibt. Sobald ein anderer Test der Suite
    die Protokollierung einrichtet, ist `caplog` für den Rest der Sitzung leer —
    dieser Test war einzeln grün und in der Suite still wirkungslos, bis der
    Kontrollpunkt unten es gefangen hat.

    Der Sammler hängt deshalb unmittelbar am betroffenen Logger und wird danach
    wieder entfernt.
    """

    class _Nutzer:
        id = 4711

    async def _create_user(_session: object, **_felder: object) -> _Nutzer:
        return _Nutzer()

    monkeypatch.setattr(provisioning, "create_user", _create_user)
    monkeypatch.setattr(provisioning, "create_async_engine", lambda *_a, **_k: _EngineAttrappe())
    monkeypatch.setattr(
        provisioning, "async_sessionmaker", lambda *_a, **_k: lambda: _SessionAttrappe()
    )

    zeilen: list[str] = []

    class _Sammler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            zeilen.append(record.getMessage())

    handler = _Sammler()
    logger = provisioning.logger
    vorheriger_pegel = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        yield zeilen
    finally:
        logger.removeHandler(handler)
        logger.setLevel(vorheriger_pegel)


async def test_die_anlage_protokolliert_keine_mailadresse(
    protokollzeilen: list[str],
) -> None:
    """Die erzeugte Zeile nennt weder die Adresse noch ihren lokalen Teil.

    Der lokale Teil wird eigens geprüft: Eine auf die Domäne gekürzte Adresse wäre
    zulässig, der Name davor ist der Personenbezug. Wer nur auf die vollständige
    Adresse prüft, übersieht genau die halbe Kürzung.
    """
    nutzer_id = await provisioning._run(
        email=EMAIL, role=Role.WORKER, password="supersecret1", db_url=None
    )

    ausgabe = "\n".join(protokollzeilen)
    assert nutzer_id == 4711, "Der Anlagepfad selbst muss unverändert durchlaufen."
    assert ausgabe.strip(), "Es wurde gar nichts protokolliert — dann prüft der Test nichts."
    assert EMAIL not in ausgabe
    assert "vorname.nachname" not in ausgabe


async def test_die_anlage_protokolliert_weiterhin_kennung_und_rolle(
    protokollzeilen: list[str],
) -> None:
    """Zwilling: Der Vorgang bleibt nachvollziehbar.

    Ohne ihn wäre der Test darüber am einfachsten dadurch zu erfüllen, gar nichts
    mehr zu protokollieren — und der Betrieb verlöre die Spur, wer wann mit welcher
    Rolle angelegt wurde. Kennung und Rolle sind kein Personenbezug.
    """
    await provisioning._run(email=EMAIL, role=Role.WORKER, password="supersecret1", db_url=None)

    ausgabe = "\n".join(protokollzeilen)
    assert "4711" in ausgabe
    assert Role.WORKER.value in ausgabe
