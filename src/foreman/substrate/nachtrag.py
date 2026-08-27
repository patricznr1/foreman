# ============================================================
#  FOREMAN — substrate/nachtrag.py
#  Zweck: Bringt den ALTBESTAND der Spiegelung auf die erweiterte Formulierung.
#         `backfill.py` kann das nicht: Es wählt Zeilen mit `substrate_ref IS
#         NULL` und baut den Text aus der GESPEICHERTEN payload. Beides trifft
#         hier nicht zu — die Altzeilen sind längst gespiegelt, und ihre payload
#         trägt den Freitext gar nicht, den der neue Satz braucht.
#  Architektur-Einordnung: Betreiber-Werkzeug (CLI), Schicht 2. Kein Endpunkt —
#         ein Vorgang, der Erinnerungen löscht, wird angestossen, nicht ausgelöst.
#  Was es tut, je Zeile und in dieser Reihenfolge:
#    1. payload aus der QUELLTABELLE anreichern (description bzw. message,
#       NER-maskiert wie im Live-Pfad),
#    2. die alte Erinnerung im Gedächtnis LÖSCHEN (`forget`),
#    3. `substrate_ref = NULL` setzen und sofort committen.
#  Danach holt `backfill.py` die Spiegelung mit dem neuen Text nach — dieselbe
#  Formulierung wie der Live-Pfad, weil beide `substrate/content.py` benutzen.
#  WARUM LÖSCHEN STATT ÜBERSCHREIBEN: Die Gegenstelle kennt kein Ersetzen. Bliebe
#         die alte Erinnerung liegen, stünde derselbe Vorgang zweimal im
#         Gedächtnis — einmal mit, einmal ohne Grund. In einer Trefferliste
#         verdrängen sich die beiden gegenseitig, und die Verdichtung sähe eine
#         Wiederholung, wo keine ist. Genau die Wiederholung ist aber das Signal,
#         auf das es bei "hatten wir das schon mal" ankommt (§12.4).
#  EIN 404 BEIM LÖSCHEN IST KEIN FEHLSCHLAG: Liegt unter der Kennung nichts
#         mehr, ist das Ziel erreicht. Als Wegstörung behandelt käme die Zeile
#         in jedem künftigen Lauf wieder, dauerhaft — die Kennung taucht ja nie
#         wieder auf. Sie wird deshalb GETRENNT gezählt (`schon_geloescht`), denn
#         ihre Zahl sagt, wie weit Bestand und Gedächtnis auseinanderliefen.
#  REIHENFOLGE IST TRAGEND: Erst löschen, dann die Referenz aufheben. Bricht der
#         Lauf dazwischen ab, zeigt die Zeile auf eine gelöschte Erinnerung —
#         der Nachtrag greift beim nächsten Lauf erneut und das Löschen ist
#         wirkungslos wiederholbar. Umgekehrt entstünde eine verwaiste
#         Erinnerung, die niemand mehr zuordnen kann.
# ============================================================
from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any, NamedTuple

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from foreman.config import get_settings
from foreman.core.redact import PresidioRedactor, Redactor
from foreman.db.models import Alarm, MaintenanceEvent, SemanticEvent
from foreman.substrate.client import SubstrateClient, SubstrateNotFoundError

logger = logging.getLogger(__name__)


class Quelle(NamedTuple):
    """Wie eine gespiegelte Zeile zu ihrer Quellzeile zurückfindet.

    ZWEI WEGE, und der zweite ist der eigentliche Grund für diese Klasse: Zeilen
    aus der Zeit vor der Notiz-Spiegelung tragen **kein** `source_id` — der
    Rückweg wurde erst mit ihr eingeführt. Gegen die laufende Instanz erhoben
    (25.08.2026): alle 44 Altzeilen sind ohne Rückweg. Ein Nachtrag, der nur
    `source_id` kennt, erreicht damit genau die Zeilen nicht, für die er gebaut ist.
    """

    modell: type[Any]
    freitext: str  # Spalte in der Quelltabelle
    zeitspalte: str  # Zeitpunkt-Spalte im Modell …
    zeitschluessel: str  # … und ihr Gegenstück in der payload
    kennspalte: str  # unterscheidendes Merkmal im Modell …
    kennschluessel: str  # … und in der payload
    # Wie die Quellzeile in der Nutzlast heisst. Dieselben Bezeichner, die der
    # Live-Pfad schreibt — sonst entstuenden zwei Schreibweisen fuer dieselbe
    # Herkunft, und ein Leser muesste beide kennen.
    source_type: str


ANREICHERUNG: dict[str, Quelle] = {
    "maintenance_performed": Quelle(
        MaintenanceEvent,
        "description",
        "performed_at",
        "performed_at",
        "type",
        "type",
        "maintenance",
    ),
    "alarm_raised": Quelle(Alarm, "message", "raised_at", "raised_at", "code", "code", "alarm"),
}


class NachtragStats:
    """Zähler eines Laufs. Getrennt, weil sie Verschiedenes messen."""

    def __init__(self) -> None:
        self.geprueft = 0
        self.angereichert = 0
        self.ohne_freitext = 0
        self.quelle_fehlt = 0
        self.bereits_vollstaendig = 0
        self.geloescht = 0
        # GETRENNT von `geloescht`: Beide Fälle führen weiter, aber sie bedeuten
        # Verschiedenes. Zusammengerechnet wäre hinterher nicht feststellbar, wie
        # viele Referenzen ins Leere zeigten — und genau das ist der Hinweis
        # darauf, dass Bestand und Gedächtnis auseinandergelaufen sind.
        self.schon_geloescht = 0
        self.loeschen_fehlgeschlagen = 0

    def __str__(self) -> str:
        return (
            f"geprüft={self.geprueft} angereichert={self.angereichert} "
            f"ohne_freitext={self.ohne_freitext} quelle_fehlt={self.quelle_fehlt} "
            f"schon_vollständig={self.bereits_vollstaendig} gelöscht={self.geloescht} "
            f"schon_gelöscht={self.schon_geloescht} "
            f"löschen_fehlgeschlagen={self.loeschen_fehlgeschlagen}"
        )


def _als_zeitpunkt(wert: Any) -> datetime | None:
    """Liest den Zeitpunkt aus der payload — dort steht er als ISO-Zeichenkette."""
    if isinstance(wert, datetime):
        return wert
    if not isinstance(wert, str):
        return None
    try:
        return datetime.fromisoformat(wert)
    except ValueError:
        return None


async def _ueber_rueckweg(
    session: AsyncSession, quelle: Quelle, payload: Mapping[str, Any]
) -> Any | None:
    """Die Quellzeile über die gespeicherte Kennung — oder None."""
    quell_id = payload.get("source_id")
    if quell_id is None:
        return None
    return await session.get(quelle.modell, quell_id)


async def _ueber_merkmale(
    session: AsyncSession, quelle: Quelle, payload: Mapping[str, Any]
) -> Sequence[Any]:
    """ALLE Quellzeilen, auf die Maschine, Zeitpunkt und Art passen.

    Gibt die Liste zurück, nicht das Ergebnis — wie viele es sind, ist eine
    Information, die der Aufrufer braucht: „keine" und „mehrere" sind
    verschiedene Lagen, und wer sie zusammenwirft, verwechselt „ich ordne nichts
    zu" mit „es gibt nichts" (siehe `aufraeumen._quellzustand`).
    """
    zeitpunkt = _als_zeitpunkt(payload.get(quelle.zeitschluessel))
    maschine = payload.get("machine_id")
    kennung = payload.get(quelle.kennschluessel)
    if zeitpunkt is None or maschine is None:
        return []

    return (
        (
            await session.execute(
                select(quelle.modell).where(
                    quelle.modell.machine_id == maschine,
                    getattr(quelle.modell, quelle.zeitspalte) == zeitpunkt,
                    getattr(quelle.modell, quelle.kennspalte) == kennung,
                )
            )
        )
        .scalars()
        .all()
    )


async def _quellzeile(session: AsyncSession, quelle: Quelle, payload: Mapping[str, Any]) -> Any:
    """Findet die Quellzeile — über den Rückweg, sonst über natürliche Merkmale.

    Der Ersatzweg schlägt NUR zu, wenn genau EINE Zeile passt. Bei mehreren
    bleibt es beim Nichts: Eine falsch zugeordnete Beschreibung wäre schlimmer
    als eine fehlende — sie schriebe einem Vorgang den Grund eines anderen zu,
    und niemand könnte das später auseinanderhalten.

    DER RÜCKWEG IST KEINE SACKGASSE (seit 27.08.2026): Löst die gespeicherte
    Kennung nicht mehr auf, wird die Merkmalssuche trotzdem versucht. Vorher kehrte
    die Funktion bei gesetztem `source_id` sofort zurück — und meldete „keine
    Quellzeile", obwohl Maschine, Zeitpunkt und Art sie eindeutig gefunden hätten.
    Genau diese Lage entsteht, wenn die Quelltabellen neu aufgebaut werden und dabei
    neue Kennungen vergeben: Die Zeile existiert, ihre alte Nummer nicht mehr. Für
    den Nachtrag hiess das ein unnötiges Überspringen; für das Aufräumen hiesse es
    eine Löschung.
    """
    ueber_rueckweg = await _ueber_rueckweg(session, quelle, payload)
    if ueber_rueckweg is not None:
        return ueber_rueckweg

    treffer = await _ueber_merkmale(session, quelle, payload)
    return treffer[0] if len(treffer) == 1 else None


async def nachtragen(
    session: AsyncSession,
    substrate: SubstrateClient | None,
    redactor: Redactor,
    *,
    limit: int | None = None,
    trockenlauf: bool = False,
) -> NachtragStats:
    """Reichert Altzeilen an und hebt ihre Spiegelung auf. Gibt die Zähler zurück."""
    stats = NachtragStats()

    frage = select(SemanticEvent).where(SemanticEvent.event_type.in_(tuple(ANREICHERUNG)))
    if limit is not None:
        frage = frage.limit(limit)
    zeilen = (await session.execute(frage.order_by(SemanticEvent.id))).scalars().all()

    for zeile in zeilen:
        stats.geprueft += 1
        quelle = ANREICHERUNG[zeile.event_type]
        schluessel = quelle.freitext
        payload = dict(zeile.payload or {})

        # VOLLSTÄNDIG heisst: Freitext UND Rückweg. Nur auf den Freitext zu
        # prüfen liess Zeilen zurück, die aus einem früheren Lauf zwar ihre
        # Beschreibung hatten, den Rückweg aber nicht — er kam später dazu. Sie
        # galten als erledigt und wurden nie wieder angefasst (belegt am
        # 25.08.2026: 22 Zeilen). Eine Vollständigkeits-Prüfung, die weniger
        # prüft als der Lauf schreibt, schliesst genau die Zeilen aus, für die
        # der nächste Lauf gebaut wurde.
        fehlt = [f for f in (schluessel, "source_type", "source_id") if payload.get(f) is None]
        if not fehlt:
            stats.bereits_vollstaendig += 1
            continue

        quellzeile = await _quellzeile(session, quelle, payload)
        roh = getattr(quellzeile, quelle.freitext, None) if quellzeile is not None else None
        if not isinstance(roh, str):
            # Quellzeile weg oder Feld leer: KEIN erfundener Text. Die Zeile
            # behält ihre bisherige, gültige Spiegelung — sie zu löschen wäre
            # ein Verlust ohne Gewinn.
            stats.quelle_fehlt += 1
            continue
        if not roh.strip():
            stats.ohne_freitext += 1
            continue

        if payload.get(schluessel) is None:
            payload[schluessel] = redactor.redact_person_names(roh)
        # DEN RUECKWEG MITGEBEN, wenn er fehlt: `source_type`/`source_id` kamen
        # erst mit der Notiz-Spiegelung; Altzeilen tragen sie nicht. Ohne sie ist
        # die entstehende Erinnerung spaeter keiner Quellzeile zuzuordnen — genau
        # der Mangel aus C-060, und er faellt hier ohne Zusatzaufwand weg: Die
        # Quellzeile ist an dieser Stelle bereits gefunden.
        payload.setdefault("source_type", quelle.source_type)
        payload.setdefault("source_id", quellzeile.id)
        stats.angereichert += 1

        if trockenlauf:
            continue

        # 1. Alte Erinnerung löschen — VOR dem Aufheben der Referenz.
        alte_ref = zeile.substrate_ref
        if alte_ref and substrate is not None:
            try:
                await substrate.forget(alte_ref)
                stats.geloescht += 1
            except SubstrateNotFoundError:
                # ZIEL ERREICHT, nicht Fehlschlag: Unter dieser Kennung liegt
                # nichts (mehr). Als Wegstörung behandelt, bliebe die Zeile
                # unangetastet und käme in JEDEM künftigen Lauf wieder — dauerhaft,
                # weil die Kennung nie wieder auftaucht. Das ist die andere Hälfte
                # der Fehlerzweig-Regel: Eine Störung des Weges darf keinen
                # Eintrag verbrauchen, ein erledigter Eintrag darf nicht ewig
                # wiederkehren.
                stats.schon_geloescht += 1
                logger.warning(
                    "⚠️ Erinnerung zu semantic_event=%s ref=%s war bereits fort — "
                    "Zeile wird trotzdem angereichert.",
                    zeile.id,
                    alte_ref,
                )
            except Exception as fehler:
                # Der Weg ist gestört, nicht der Eintrag: Die Zeile bleibt
                # unangetastet und kommt beim nächsten Lauf wieder dran. Sie
                # jetzt anzureichern hiesse, die alte Erinnerung dauerhaft
                # verwaisen zu lassen.
                stats.loeschen_fehlgeschlagen += 1
                stats.angereichert -= 1
                logger.warning(
                    "⚠️ forget fehlgeschlagen für semantic_event=%s ref=%s (%s) — "
                    "Zeile unverändert, nächster Lauf greift erneut.",
                    zeile.id,
                    alte_ref,
                    fehler,
                )
                continue

        # 2. payload schreiben und Referenz aufheben — der Backfill holt sie neu.
        await session.execute(
            update(SemanticEvent)
            .where(SemanticEvent.id == zeile.id)
            .values(payload=payload, substrate_ref=None)
        )
        await session.commit()  # pro Zeile, wie im Backfill

    logger.info("🔁 Nachtrag beendet: %s", stats)
    return stats


def _argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m foreman.substrate.nachtrag",
        description=(
            "Reichert die Spiegelung von Wartung und Alarm um ihren Freitext an. "
            "Löscht die alte Erinnerung und hebt substrate_ref auf; danach "
            "'python -m foreman.substrate.backfill' laufen lassen."
        ),
    )
    parser.add_argument("--limit", type=int, default=None, help="Höchstzahl zu prüfender Zeilen.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur zählen, was angereichert würde — kein forget, kein Schreibvorgang.",
    )
    parser.add_argument("--db-url", default=None, help="Override der Datenbank-URL.")
    return parser


async def _main(argv: Sequence[str] | None = None) -> int:
    args = _argparser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()

    engine = create_async_engine(args.db_url or settings.database_url)
    fabrik = async_sessionmaker(engine, expire_on_commit=False)
    substrate = SubstrateClient.from_settings(settings) if not args.dry_run else None
    if substrate is None and not args.dry_run:
        logger.error("❌ Kein Substrat konfiguriert — ohne Gegenstelle kein Nachtrag.")
        return 2

    try:
        async with fabrik() as session:
            stats = await nachtragen(
                session,
                substrate,
                PresidioRedactor(),
                limit=args.limit,
                trockenlauf=args.dry_run,
            )
    finally:
        await engine.dispose()

    if stats.loeschen_fehlgeschlagen:
        logger.warning(
            "⚠️ %s Zeilen unverändert — erneut laufen lassen.", stats.loeschen_fehlgeschlagen
        )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return asyncio.run(_main(argv))


if __name__ == "__main__":
    raise SystemExit(main())
