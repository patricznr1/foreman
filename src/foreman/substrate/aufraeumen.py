# ============================================================
#  FOREMAN — substrate/aufraeumen.py
#  Zweck: Entfernt Spiegelungen, deren Quellzeile nicht mehr besteht — samt der
#         Erinnerung im Gedächtnis. Betreiber-Werkzeug (CLI), Schicht 2.
#  WARUM ES SIE GIBT (gemessen 26.08.2026): Wird der Datenbestand neu aufgebaut,
#         bleiben die Spiegelungen der alten Zeilen stehen. Sie beschreiben
#         Vorgänge, die niemand mehr nachschlagen kann, belegen aber Plätze in
#         jeder Trefferliste — auf der laufenden Instanz 22 von 44. Ohne sie
#         steigt der Anteil zutreffender Treffer von 0,417 auf 0,562, ohne dass
#         ein einziger zutreffender Treffer verloren geht.
#  WARUM LÖSCHEN STATT FILTERN: Ein Filter im Suchpfad versteckte den Rest, statt
#         ihn zu beseitigen — er bliebe im Gedächtnis, ginge in jede Verdichtung
#         ein und wäre bei jeder späteren Auswertung erneut zu berücksichtigen.
#         Was keinen Bezug mehr hat, gehört entfernt.
#  WAS NICHT ANGEFASST WIRD: Ableitungen des Systems (Empfehlung, Ereigniskette).
#         Sie haben keine Quellzeile im Archiv-Sinn und sind deshalb auch nicht
#         verwaist; ob sie überhaupt in die Archiv-Suche gehören, ist eine eigene
#         Frage und wird hier nicht nebenbei entschieden.
#  REIHENFOLGE: Erst die Erinnerung löschen, dann die Zeile. Bricht der Lauf
#         dazwischen ab, bleibt eine Zeile ohne Erinnerung zurück — der nächste
#         Lauf räumt sie ab (ihr `forget` läuft in ein 404 und gilt als erledigt).
#         Umgekehrt bliebe eine Erinnerung ohne jeden Bezug übrig, die niemand
#         mehr findet.
# ============================================================
from __future__ import annotations

import argparse
import asyncio
import logging
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from foreman.config import get_settings
from foreman.db.models import SemanticEvent
from foreman.substrate.client import SubstrateClient, SubstrateNotFoundError
from foreman.substrate.nachtrag import ANREICHERUNG, _quellzeile

logger = logging.getLogger(__name__)


class AufraeumStats:
    """Zähler eines Laufs. Getrennt, weil sie Verschiedenes messen.

    `verwaist` zählt, was ENTFERNT wurde oder entfernt werden konnte — eine
    gestörte Gegenstelle nimmt ihn zurück und erhöht stattdessen
    `loeschen_fehlgeschlagen`, denn sonst meldete er eine Entfernung, die nicht
    stattfand. Im Trockenlauf gibt es diesen Fall nicht; dort zählt er schlicht
    alle Fundstellen. **Wer Trockenlauf und scharfen Lauf vergleicht, addiert
    deshalb `verwaist + loeschen_fehlgeschlagen`** — diese Summe ist in beiden
    Läufen dieselbe Zahl. `__str__` gibt beide aus, damit der Vergleich nicht
    an einer einzelnen Zahl hängt.
    """

    def __init__(self) -> None:
        self.geprueft = 0
        self.mit_quelle = 0
        self.verwaist = 0
        self.geloescht = 0
        self.schon_fort = 0
        self.loeschen_fehlgeschlagen = 0

    def __str__(self) -> str:
        return (
            f"geprüft={self.geprueft} mit_quelle={self.mit_quelle} "
            f"verwaist={self.verwaist} gelöscht={self.geloescht} "
            f"schon_fort={self.schon_fort} löschen_fehlgeschlagen={self.loeschen_fehlgeschlagen}"
        )


async def aufraeumen(
    session: AsyncSession,
    substrate: SubstrateClient | None,
    *,
    limit: int | None = None,
    trockenlauf: bool = False,
) -> AufraeumStats:
    """Entfernt Spiegelungen ohne Quellzeile. Gibt die Zähler zurück."""
    stats = AufraeumStats()

    frage = select(SemanticEvent).where(SemanticEvent.event_type.in_(tuple(ANREICHERUNG)))
    if limit is not None:
        frage = frage.limit(limit)
    zeilen = (await session.execute(frage.order_by(SemanticEvent.id))).scalars().all()

    for zeile in zeilen:
        stats.geprueft += 1
        quelle = ANREICHERUNG[zeile.event_type]
        payload = dict(zeile.payload or {})

        # Dieselbe Suche wie im Nachtrag — beide Wege, erst der gespeicherte
        # Rückweg, dann die Merkmale. Nur was AUF KEINEM Weg auffindbar ist,
        # gilt als verwaist. Eine Zeile wegen einer zu engen Suche zu löschen
        # wäre der schlimmere Fehler: Sie käme nie wieder.
        if await _quellzeile(session, quelle, payload) is not None:
            stats.mit_quelle += 1
            continue

        stats.verwaist += 1
        if trockenlauf:
            continue

        alte_ref = zeile.substrate_ref
        if alte_ref and substrate is not None:
            try:
                await substrate.forget(alte_ref)
                stats.geloescht += 1
            except SubstrateNotFoundError:
                # Schon fort — das Ziel ist erreicht, die Zeile darf weg.
                stats.schon_fort += 1
                logger.warning(
                    "⚠️ Erinnerung zu semantic_event=%s ref=%s war bereits fort.",
                    zeile.id,
                    alte_ref,
                )
            except Exception as fehler:
                # Störung des Weges: Die Zeile BLEIBT, samt Erinnerung. Sie
                # jetzt zu entfernen liesse eine Erinnerung zurück, die niemand
                # mehr zuordnen kann — schlimmer als der Rest, den sie ersetzt.
                stats.loeschen_fehlgeschlagen += 1
                stats.verwaist -= 1
                logger.warning(
                    "⚠️ forget fehlgeschlagen für semantic_event=%s ref=%s (%s) — "
                    "Zeile bleibt, nächster Lauf greift erneut.",
                    zeile.id,
                    alte_ref,
                    fehler,
                )
                continue

        await session.execute(delete(SemanticEvent).where(SemanticEvent.id == zeile.id))
        await session.commit()  # pro Zeile, wie im Nachtrag

    logger.info("🧹 Aufräumen beendet: %s", stats)
    return stats


def _argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m foreman.substrate.aufraeumen",
        description=(
            "Entfernt Spiegelungen von Wartung und Alarm, deren Quellzeile nicht "
            "mehr besteht — samt der zugehörigen Erinnerung. UNUMKEHRBAR."
        ),
    )
    parser.add_argument("--limit", type=int, default=None, help="Höchstzahl zu prüfender Zeilen.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur zählen, was entfernt würde — kein forget, kein Löschen.",
    )
    parser.add_argument("--db-url", default=None, help="Override der Datenbank-URL.")
    return parser


async def _main(argv: Sequence[str] | None = None) -> int:
    args = _argparser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()

    engine = create_async_engine(args.db_url or settings.database_url)
    fabrik = async_sessionmaker(engine, expire_on_commit=False)
    substrate = None if args.dry_run else SubstrateClient.from_settings(settings)

    try:
        async with fabrik() as session:
            stats = await aufraeumen(session, substrate, limit=args.limit, trockenlauf=args.dry_run)
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
