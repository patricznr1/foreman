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
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from foreman.config import get_settings
from foreman.core.redact import PresidioRedactor, Redactor
from foreman.db.models import Alarm, MaintenanceEvent, SemanticEvent
from foreman.substrate.client import SubstrateClient

logger = logging.getLogger(__name__)

# event_type → (Quelltabelle, Spalte mit dem Freitext, Zielschlüssel in der payload)
ANREICHERUNG: dict[str, tuple[type[Any], str, str]] = {
    "maintenance_performed": (MaintenanceEvent, "description", "description"),
    "alarm_raised": (Alarm, "message", "message"),
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
        self.loeschen_fehlgeschlagen = 0

    def __str__(self) -> str:
        return (
            f"geprüft={self.geprueft} angereichert={self.angereichert} "
            f"ohne_freitext={self.ohne_freitext} quelle_fehlt={self.quelle_fehlt} "
            f"schon_vollständig={self.bereits_vollstaendig} gelöscht={self.geloescht} "
            f"löschen_fehlgeschlagen={self.loeschen_fehlgeschlagen}"
        )


async def _quelltext(
    session: AsyncSession, modell: type[Any], spalte: str, quell_id: Any
) -> str | None:
    """Liest den Freitext aus der Quellzeile. None, wenn die Zeile fehlt."""
    if quell_id is None:
        return None
    zeile = await session.get(modell, quell_id)
    if zeile is None:
        return None
    wert = getattr(zeile, spalte, None)
    return wert if isinstance(wert, str) else None


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
        modell, spalte, schluessel = ANREICHERUNG[zeile.event_type]
        payload = dict(zeile.payload or {})

        if payload.get(schluessel) is not None:
            # Schon angereichert — ein zweiter Lauf fasst sie nicht an.
            stats.bereits_vollstaendig += 1
            continue

        roh = await _quelltext(session, modell, spalte, payload.get("source_id"))
        if roh is None:
            # Quellzeile weg oder Feld leer: KEIN erfundener Text. Die Zeile
            # behält ihre bisherige, gültige Spiegelung — sie zu löschen wäre
            # ein Verlust ohne Gewinn.
            stats.quelle_fehlt += 1
            continue
        if not roh.strip():
            stats.ohne_freitext += 1
            continue

        payload[schluessel] = redactor.redact_person_names(roh)
        stats.angereichert += 1

        if trockenlauf:
            continue

        # 1. Alte Erinnerung löschen — VOR dem Aufheben der Referenz.
        alte_ref = zeile.substrate_ref
        if alte_ref and substrate is not None:
            try:
                await substrate.forget(alte_ref)
                stats.geloescht += 1
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
