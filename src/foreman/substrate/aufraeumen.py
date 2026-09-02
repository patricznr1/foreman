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
#  WAS NICHT ANGEFASST WIRD, in drei Stufen:
#         (1) Ableitungen des Systems (Empfehlung, Ereigniskette). Sie haben keine
#             Quellzeile im Archiv-Sinn und sind deshalb auch nicht verwaist; ob
#             sie überhaupt in die Archiv-Suche gehören, ist eine eigene Frage und
#             wird hier nicht nebenbei entschieden.
#         (2) Alles, was auf EINEM der beiden Wege auffindbar ist — gespeicherter
#             Rückweg ODER Maschine + Zeitpunkt + Art. Der Rückweg ist dabei keine
#             Sackgasse: Löst die gespeicherte Kennung nicht mehr auf, wird die
#             Merkmalssuche trotzdem versucht (`nachtrag._quellzeile`). Sonst
#             löschte gerade der Bestand, für den dieses Werkzeug gebaut ist —
#             neu aufgebaute Quelltabellen vergeben neue Kennungen.
#         (3) Alles, wo MEHRERE Quellzeilen passen. Dann existiert die Quelle
#             nicht nur, sie existiert doppelt; das ist das Gegenteil von
#             verwaist. `_quellzustand` trennt diesen Fall ausdrücklich ab —
#             „ich ordne nichts zu" ist nicht „es gibt nichts".
#  REIHENFOLGE: Erst die Erinnerung löschen, dann die Zeile. Bricht der Lauf
#         dazwischen ab, bleibt eine Zeile ohne Erinnerung zurück — der nächste
#         Lauf räumt sie ab (ihr `forget` läuft in ein 404 und gilt als erledigt).
#         Umgekehrt bliebe eine Erinnerung ohne jeden Bezug übrig, die niemand
#         mehr findet.
# ============================================================
from __future__ import annotations

import argparse
import asyncio
import enum
import logging
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from foreman.config import get_settings
from foreman.db.models import SemanticEvent
from foreman.substrate.client import SubstrateClient, SubstrateNotFoundError
from foreman.substrate.nachtrag import (
    ANREICHERUNG,
    Quelle,
    _ueber_merkmale,
    _ueber_rueckweg,
)

logger = logging.getLogger(__name__)


class Quellzustand(enum.Enum):
    """Was über die Quellzeile einer Spiegelung feststeht.

    WARUM DREI WERTE UND NICHT ZWEI: `nachtrag._quellzeile` beantwortet die Frage
    „WELCHE Zeile beschreibt diese Spiegelung?" und darf mit „lässt sich nicht
    sagen" antworten — der Nachtrag überspringt die Zeile dann, was nichts kostet.
    Hier steht eine andere Frage: „Gibt es ÜBERHAUPT noch eine Zeile?" Wer darauf
    dieselbe Antwort verwendet, liest „ich ordne nichts zu" als „es gibt nichts" —
    und löscht unwiederbringlich, wo er nur unsicher war.

    Der Fall ist im Bestand belegt: Passen zwei Quellzeilen auf dieselben Merkmale
    (dieselbe Maschine, derselbe Zeitpunkt, dieselbe Art — etwa nach einem doppelt
    eingelesenen Import), gibt `_quellzeile` nichts zurück. Die Quelle existiert
    dann nicht nur, sie existiert doppelt.
    """

    GEFUNDEN = "gefunden"
    MEHRDEUTIG = "mehrdeutig"
    VERWAIST = "verwaist"


async def _quellzustand(
    session: AsyncSession, quelle: Quelle, payload: dict[str, object]
) -> Quellzustand:
    """Prüft BEIDE Wege und trennt „nichts gefunden" von „nicht entscheidbar"."""
    if await _ueber_rueckweg(session, quelle, payload) is not None:
        return Quellzustand.GEFUNDEN

    treffer = await _ueber_merkmale(session, quelle, payload)
    if len(treffer) == 1:
        return Quellzustand.GEFUNDEN
    if treffer:
        return Quellzustand.MEHRDEUTIG
    return Quellzustand.VERWAIST


class AufraeumStats:
    """Zähler eines Laufs. Getrennt, weil sie Verschiedenes messen.

    `mit_quelle`, `mehrdeutig` und `verwaist` teilen die geprüften Zeilen
    vollständig auf: Nur die letzte Gruppe wird angefasst.

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
        self.mehrdeutig = 0
        self.verwaist = 0
        self.geloescht = 0
        self.nicht_auffindbar = 0
        self.loeschen_fehlgeschlagen = 0

    def __str__(self) -> str:
        return (
            f"geprüft={self.geprueft} mit_quelle={self.mit_quelle} "
            f"mehrdeutig={self.mehrdeutig} "
            f"verwaist={self.verwaist} gelöscht={self.geloescht} "
            f"nicht_auffindbar={self.nicht_auffindbar} "
            f"löschen_fehlgeschlagen={self.loeschen_fehlgeschlagen}"
        )


async def aufraeumen(
    session: AsyncSession,
    substrate: SubstrateClient | None,
    *,
    limit: int | None = None,
    trockenlauf: bool = False,
) -> AufraeumStats:
    """Entfernt Spiegelungen ohne Quellzeile. Gibt die Zähler zurück."""
    # Ein scharfer Lauf ohne Gegenstelle löschte die Zeilen und liesse ihre
    # Erinnerungen zurück — ohne Rückweg, von niemandem mehr auffindbar, und
    # kein Zähler wiese darauf hin. Über `_main` ist dieser Zustand unerreichbar
    # (dort hängt `substrate is None` an `--dry-run`); ein Aufrufer, der die
    # Funktion direkt benutzt, kann ihn aber herstellen. Ein Vorgang, der Daten
    # unumkehrbar entfernt, verlässt sich nicht auf seinen einzigen heutigen
    # Aufrufer.
    if substrate is None and not trockenlauf:
        raise ValueError(
            "❌ Scharfer Lauf ohne Gegenstelle: Die Zeilen würden gelöscht, "
            "ihre Erinnerungen blieben zurück. Entweder eine Gegenstelle "
            "übergeben oder trockenlauf=True setzen."
        )

    stats = AufraeumStats()

    frage = select(SemanticEvent).where(SemanticEvent.event_type.in_(tuple(ANREICHERUNG)))
    if limit is not None:
        frage = frage.limit(limit)
    zeilen = (await session.execute(frage.order_by(SemanticEvent.id))).scalars().all()

    for zeile in zeilen:
        stats.geprueft += 1
        quelle = ANREICHERUNG[zeile.event_type]
        payload = dict(zeile.payload or {})

        # Beide Wege, erst der gespeicherte Rückweg, dann die Merkmale — und die
        # Antwort ist DREIWERTIG. Gelöscht wird ausschliesslich bei VERWAIST.
        # Eine Zeile wegen einer zu engen oder einer nicht entscheidbaren Suche
        # zu löschen wäre der schlimmere Fehler: Sie käme nie wieder.
        zustand = await _quellzustand(session, quelle, payload)
        if zustand is Quellzustand.GEFUNDEN:
            stats.mit_quelle += 1
            continue
        if zustand is Quellzustand.MEHRDEUTIG:
            # Mehrere Quellzeilen passen. Die Quelle existiert dann nicht nur,
            # sie existiert doppelt — das ist das Gegenteil von verwaist.
            stats.mehrdeutig += 1
            logger.warning(
                "⚠️ semantic_event=%s: mehrere Quellzeilen passen auf dieselben "
                "Merkmale — bleibt stehen, von Hand zu klären.",
                zeile.id,
            )
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
                # NICHT AUFFINDBAR — und das ist NICHT dasselbe wie „fort". Die
                # Gegenstelle meldet 404 auch für eine abgewiesene Löschung.
                # Die Zeile geht trotzdem weg: Sie ist verwaist, ihre Quellzeile
                # existiert nicht mehr, und sie stehen zu lassen hiesse, sie in
                # JEDEM künftigen Lauf erneut zu prüfen — dauerhaft, weil die
                # Kennung nie wieder auftaucht.
                # WAS DAS KOSTET, offen benannt: Lebt der Eintrag drüben weiter,
                # ist er danach über FOREMAN nicht mehr auffindbar. Deshalb steht
                # der Rückweg in der Meldung — sie ist die einzige Spur, die
                # bleibt.
                stats.nicht_auffindbar += 1
                logger.warning(
                    "⚠️ semantic_event=%s ref=%s: Gegenstelle meldet nicht auffindbar. "
                    "KEIN Beleg der Löschung — Rückweg wird hier verworfen.",
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
